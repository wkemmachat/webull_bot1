"""COMEX gold (GC) and silver (SI) 4-hour bars for the metals strategies.

Hourly futures bars → remove contract-roll gaps (back-adjust older prices, see rolls.py) → TradingView-aligned
4H bars (session opens 18:00 New York, see bars.py). A 4H bar is used only once it is complete.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

import numpy as np
import pandas as pd

from . import db, marketdata as md
from .bars import last_closed_bucket_end, market_open_ny, next_bucket_end, to_4h
from .rolls import apply_rolls, detect_rolls, find_roll_bar

log = logging.getLogger("metals")
DELAY_MIN = 11          # Yahoo futures lag
MAX_WAIT_MIN = 45
_cache: dict = {}


def delay_min() -> int:
    return 0 if md.source() == "csv" else DELAY_MIN


def last_close(now: datetime):
    """When COMEX last closed (UTC) if it is closed now, else None (weekend, the 17:00-18:00 break)."""
    t = pd.Timestamp(now).tz_convert("America/New_York")
    if market_open_ny(t):
        return None
    for k in range(0, 72):
        h = (t - pd.Timedelta(hours=k)).floor("h")
        if market_open_ny(h):
            return (h + pd.Timedelta(hours=1)).tz_convert("UTC")
    return None


def due(sym: str, now: datetime) -> bool:
    """True when a new 4H bar should be available, or the data is older than 10 minutes.
    While COMEX is closed (weekend, daily break) nothing new can arrive: one download after the close is enough."""
    if md.source() == "csv":
        return True
    last = md.last_update(sym, "1h") or 0
    lc = last_close(now)
    if lc is not None and last >= lc.timestamp() + (DELAY_MIN + 20) * 60:
        return False
    if time.time() - last > 600:
        return True
    end = last_closed_bucket_end(now, delay_min())
    if end is None:
        return False
    within = (pd.Timestamp(now) - end).total_seconds() < (MAX_WAIT_MIN + 20) * 60
    return within and last < end.timestamp() + delay_min() * 60


def track_contract(sym: str):
    """Confirm live rolls from Yahoo's contract code (e.g. GCZ26.CMX), checked at most every 6 hours."""
    if md.source() != "yahoo":
        return
    key = f"contract:{sym}"
    prev = db.get_state(key)
    if prev and time.time() - prev.get("checked", 0) < 6 * 3600:
        return
    try:
        import yfinance as yf
        info = yf.Ticker(md.yahoo_ticker(sym)).info or {}
        code = info.get("underlyingSymbol") or info.get("underlyingExchangeSymbol")
    except Exception as e:
        log.warning("contract lookup %s: %s", sym, e)
        return
    now = int(time.time())
    if not code:
        return
    if prev and prev.get("code") and prev["code"] != code:
        raw1 = md.load(sym, "1h")
        hit = find_roll_bar(raw1, pd.Timestamp(prev["seen_at"] - 3 * 86400, unit="s", tz="UTC"), pd.Timestamp(now, unit="s", tz="UTC"))
        if hit:
            ts, ratio, gap = hit
            t = int(ts.timestamp())
            with db.tx() as c:
                c.execute("DELETE FROM rolls WHERE symbol=? AND source='estimated' AND ABS(t-?) < 20*86400", (sym, t))
                c.execute("INSERT OR REPLACE INTO rolls(symbol,t,ratio,gap,ignored,source,note,detected_at) VALUES(?,?,?,?,0,'contract',?,?)",
                          (sym, t, ratio, gap, f"{prev['code']} → {code}", now))
            db.add_event("info", "data", f"{sym} contract roll", f"{prev['code']} → {code}; gap {gap:+.2%} removed from indicator history")
    db.set_state(key, {"code": code, "seen_at": now, "checked": now})


def update(sym: str) -> int:
    n = md.update(sym, "1h")
    track_contract(sym)
    _cache.pop(sym, None)
    return n


def series(sym: str, now: datetime | None = None) -> dict:
    """{'raw4', 'adj4', 'factor4', 'raw1'} with only completed 4H bars. Cached until new data arrives."""
    now = now or md.now_utc()
    stamp = (md.last_update(sym, "1h"), int(pd.Timestamp(now).timestamp()) // 60)
    hit = _cache.get(sym)
    if hit and hit[0] == stamp:
        return hit[1]
    raw1 = md.load(sym, "1h")
    if raw1.empty:
        raise md.DataError(f"No {sym} data yet")
    known = {r["t"] for r in db.rows("SELECT t FROM rolls WHERE symbol=?", (sym,))}
    confirmed = [r["t"] for r in db.rows("SELECT t FROM rolls WHERE symbol=? AND source!='estimated'", (sym,))]
    new = [(ts, ratio, gap) for ts, ratio, gap in detect_rolls(raw1, sym)
           if int(ts.timestamp()) not in known and all(abs(int(ts.timestamp()) - c) > 20 * 86400 for c in confirmed)]
    if new:
        with db.tx() as c:
            c.executemany("INSERT OR IGNORE INTO rolls(symbol,t,ratio,gap,ignored,source,detected_at) VALUES(?,?,?,?,0,'estimated',?)",
                          [(sym, int(ts.timestamp()), ratio, gap, int(time.time())) for ts, ratio, gap in new])
    rl = [(pd.Timestamp(r["t"], unit="s", tz="UTC"), r["ratio"])
          for r in db.rows("SELECT t, ratio FROM rolls WHERE symbol=? AND ignored=0 ORDER BY t", (sym,))]
    adj1, _ = apply_rolls(raw1, rl)
    raw4, adj4 = to_4h(raw1), to_4h(adj1)
    now_ts = pd.Timestamp(now)
    delay = pd.Timedelta(minutes=delay_min())
    ends = pd.to_datetime(raw4["end"], utc=True)
    last_hour = pd.to_datetime(raw4["last_hour"], utc=True)
    has_last_hour = last_hour >= ends - pd.Timedelta(hours=1)
    next_seen = raw1.index[-1] >= ends
    settled = now_ts >= ends + delay + pd.Timedelta(minutes=15)
    waited_long = now_ts >= ends + pd.Timedelta(minutes=MAX_WAIT_MIN)
    complete = (now_ts >= ends + delay) & ((has_last_hour & (next_seen | settled)) | waited_long)
    if complete.any():
        k = np.where(complete.values)[0][-1]
        raw4c, adj4c = raw4.iloc[:k + 1], adj4.iloc[:k + 1]
    else:
        raw4c, adj4c = raw4.iloc[:0], adj4.iloc[:0]
    out = {"raw1": raw1, "raw4": raw4c, "adj4": adj4c, "factor4": (adj4c["c"] / raw4c["c"]).astype(float),
           "forming": raw4.iloc[len(raw4c):], "rolls": rl}
    _cache[sym] = (stamp, out)
    return out


def next_bar_end(now: datetime | None = None):
    ne = next_bucket_end(now or md.now_utc())
    return int(ne.timestamp()) if ne is not None else None
