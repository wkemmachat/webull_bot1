"""Data for the C2-7 Momentum basket: weekly Nasdaq-100 market-cap rankings, the momentum pick list, stock prices.

Rankings: the research's weekly file (28 Oct 2016 – 23 Oct 2026, app/research/c27) plus the bot's own weekly ranking
(every weekend after the Friday close: Yahoo market cap of the Nasdaq-100 members), stored in the c27_rank table.
Prices: the research's daily total-return prices for the names that were ever in the top 20, extended with Yahoo.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import db, marketdata as md
from .config import BASE_DIR

log = logging.getLogger("basket")
NY = ZoneInfo("America/New_York")
DIR = BASE_DIR / "app" / "research" / "c27"
_mem: dict = {}
_lock = threading.Lock()


def _cached(key, fn, ttl=3600):
    with _lock:
        hit = _mem.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    v = fn()
    with _lock:
        _mem[key] = (time.time(), v)
    return v


def clear_cache():
    with _lock:
        _mem.clear()


# ---------------------------------------------------------------- rankings
def members() -> list:
    return [x.strip() for x in (DIR / "members.txt").read_text().splitlines() if x.strip() and not x.startswith("#")]


def _bundled_ranks():
    df = pd.read_csv(DIR / "rank_weekly.csv.gz")
    df["week"] = pd.to_datetime(df["week"]).dt.date
    return df.rename(columns={"mcap_busd": "mcap"})


def ranks() -> pd.DataFrame:
    """week (date of the Friday), rank, symbol, mcap ($bn). The bot's own weeks replace the research's for the same Friday."""
    def build():
        a = _bundled_ranks()
        rows = db.rows("SELECT week, rank, symbol, mcap FROM c27_rank ORDER BY week, rank")
        if rows:
            b = pd.DataFrame(rows)
            b["week"] = pd.to_datetime(b["week"]).dt.date
            a = pd.concat([a[~a["week"].isin(set(b["week"]))], b], ignore_index=True)
        return a.sort_values(["week", "rank"]).reset_index(drop=True)
    stamp = db.one("SELECT COUNT(*) n, MAX(week) w FROM c27_rank")
    return _cached(f"ranks:{stamp['n']}:{stamp['w']}", build, ttl=6 * 3600)


def weeks() -> list:
    return sorted(ranks()["week"].unique())


def ranking_for(day) -> tuple:
    """(Friday, [(symbol, mcap), …] largest first) in force for a decision made after the close of `day`:
    the last ranking Friday on or before that day."""
    r = ranks()
    ws = [w for w in weeks() if w <= day]
    if not ws:
        return None, []
    w = ws[-1]
    sub = r[r["week"] == w].sort_values("rank")
    return w, list(zip(sub["symbol"], sub["mcap"].astype(float)))


def update_live(now=None) -> int:
    """Weekend job: rank the Nasdaq-100 members by Yahoo market cap for the last Friday close. Returns rows stored."""
    if md.source() == "csv":
        return 0
    now = now or md.now_utc()
    ny = now.astimezone(NY).date()
    friday = ny - timedelta(days=(ny.weekday() - 4) % 7)
    if friday == ny and now.astimezone(NY).hour < 17:
        friday -= timedelta(days=7)
    import yfinance as yf
    caps = []
    for s in members():
        try:
            fi = yf.Ticker(s).fast_info
            mc = fi.get("market_cap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
            if mc:
                caps.append((s, float(mc) / 1e9))
        except Exception as e:
            log.warning("market cap %s: %s", s, e)
    if len(caps) < 50:
        raise RuntimeError(f"only {len(caps)} market caps from Yahoo")
    caps.sort(key=lambda x: -x[1])
    with db.tx() as c:
        c.execute("DELETE FROM c27_rank WHERE week=?", (str(friday),))
        c.executemany("INSERT INTO c27_rank(week,rank,symbol,mcap,created_at) VALUES(?,?,?,?,?)",
                      [(str(friday), i + 1, s, round(m, 2), int(time.time())) for i, (s, m) in enumerate(caps[:50])])
    clear_cache()
    db.add_event("info", "data", "Nasdaq-100 ranking updated", f"Week of {friday}: " + ", ".join(s for s, _ in caps[:12]))
    return min(50, len(caps))


# ---------------------------------------------------------------- prices
def _bundled_prices():
    df = pd.read_csv(DIR / "prices.csv.gz")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    out = {}
    for s, g in df.groupby("symbol"):
        out[s] = g.set_index("date")[["open", "close"]].rename(columns={"open": "o", "close": "c"})
    return out


def bundled_prices():
    return _cached("bundled_prices", _bundled_prices, ttl=24 * 3600)


def prices(sym) -> pd.DataFrame:
    """Daily total-return open/close (index = date): the research's prices, then Yahoo after they end (linked by ratio)."""
    def build():
        from . import backtest
        b = bundled_prices().get(sym)
        y = backtest.daily_tr(sym)
        if y is not None and not y.empty:
            y = y[["o", "c"]].copy()
            y.index = [pd.Timestamp(t).date() for t in y.index]
        if b is None or b.empty:
            return y if y is not None else pd.DataFrame(columns=["o", "c"])
        if y is None or y.empty:
            return b
        last = b.index[-1]
        after = y[y.index > last]
        if after.empty or last not in y.index:
            return b
        k = b.loc[last, "c"] / y.loc[last, "c"]
        return pd.concat([b, after * k])
    return _cached(f"px:{sym}:{md.source()}", build, ttl=3 * 3600)


def momentum_list(day, pool=12, hold=7, lookback=126, ranking=None):
    """The buy list for decisions after the close of `day`: the `hold` strongest (total return over `lookback` trading days,
    measured at the ranking Friday's close) of the `pool` largest. Returns (friday, picks, table rows)."""
    w, rk = ranking or ranking_for(day)
    if not rk:
        return None, [], []
    top = rk[:pool]
    rows = []
    for i, (s, mc) in enumerate(top):
        px = prices(s)
        mom = None
        if px is not None and not px.empty:
            c = px["c"][px.index <= w]
            if len(c) > lookback:
                mom = float(c.iloc[-1] / c.iloc[-1 - lookback] - 1)
        rows.append({"rank": i + 1, "symbol": s, "mcap": mc, "mom": mom})
    ok = [r for r in rows if r["mom"] is not None]
    best = sorted(ok, key=lambda r: -r["mom"])[:hold]
    keep = {r["symbol"] for r in best}
    picks = [r["symbol"] for r in rows if r["symbol"] in keep]           # largest first (the buying order)
    for r in rows:
        r["picked"] = r["symbol"] in keep
    return w, picks, rows
