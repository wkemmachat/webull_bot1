"""Prices: hourly COMEX futures for the metals strategies, daily ETF bars for the regimes, live quotes.

Sources
  yahoo  Yahoo Finance through yfinance (free, no key). GC=F / SI=F hourly (~10 min delayed),
         ETF daily bars, and 1-minute quotes incl. pre/after market.
  csv    offline files data/csv/<SYMBOL>_<tf>.csv with columns t,o,h,l,c,v (t = unix seconds or ISO);
         used by the tests and for demos without internet.
Everything downloaded is stored in the `bars` table, so a restart or a short outage costs nothing.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import db
from .config import CSV_DIR, DATA_SOURCE

log = logging.getLogger("marketdata")
NY = ZoneInfo("America/New_York")
FUTURES = {"GC": "GC=F", "SI": "SI=F"}
_lock = threading.Lock()
_qcache: dict = {}


class DataError(Exception):
    pass


def source() -> str:
    return DATA_SOURCE


def yahoo_ticker(sym: str) -> str:
    s = str(sym)
    if s.isdigit() and len(s) <= 5:             # Hong Kong code (7234 → 7234.HK)
        return f"{int(s):04d}.HK"
    return FUTURES.get(sym, sym)


# ---------------------------------------------------------------- download
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["o", "h", "l", "c", "v"]].astype(float)
    df = df[(df.c > 0) & (df.h >= df.l)]
    return df[~df.index.duplicated(keep="last")].sort_index()


def _csv(sym: str, tf: str) -> pd.DataFrame:
    p = CSV_DIR / f"{sym}_{tf}.csv"
    if not p.exists():
        raise DataError(f"No offline file {p.name}")
    df = pd.read_csv(p)
    t = df["t"]
    df.index = pd.to_datetime(t, unit="s", utc=True) if np.issubdtype(t.dtype, np.number) else pd.to_datetime(t, utc=True)
    return _clean(df)


def fetch(sym: str, tf: str, days: int) -> pd.DataFrame:
    """tf '1h' (index = bar start, UTC) or '1d' (index = trading date at 00:00 UTC)."""
    if source() == "csv":
        df = _csv(sym, tf)
        now = pd.Timestamp(now_utc())
        return df[df.index <= now]
    import yfinance as yf
    t = yf.Ticker(yahoo_ticker(sym))
    if tf == "1h":
        h = t.history(period=f"{min(int(days), 729)}d", interval="1h", auto_adjust=False, prepost=True, actions=False)
    else:
        h = t.history(period=f"{max(1, math.ceil(days / 365))}y" if days > 365 else f"{days}d", interval="1d",
                      auto_adjust=False, actions=False)
    if h is None or h.empty:
        raise DataError(f"Yahoo returned no {tf} data for {yahoo_ticker(sym)}")
    h = h.rename(columns={"Open": "o", "High": "h", "Low": "l", "Close": "c", "Volume": "v"})
    idx = h.index
    if tf == "1d":
        h.index = pd.to_datetime([d.strftime("%Y-%m-%d") for d in idx]).tz_localize("UTC")
    else:
        if idx.tz is None:
            idx = idx.tz_localize("America/New_York")
        h.index = idx.tz_convert("UTC")
    return _clean(h)


def update(sym: str, tf: str) -> int:
    """Download what is missing and store it. Returns the number of bars received."""
    have = db.one("SELECT COUNT(*) n, MAX(t) mx FROM bars WHERE symbol=? AND tf=?", (sym, tf))
    if tf == "1h":
        days = 730 if (have["n"] or 0) < 2000 else max(7, math.ceil((time.time() - (have["mx"] or 0)) / 86400) + 2)
    else:
        days = 365 * 6 if (have["n"] or 0) < 300 else max(10, math.ceil((time.time() - (have["mx"] or 0)) / 86400) + 5)
    df = fetch(sym, tf, days)
    with db.tx() as c:
        c.executemany("INSERT INTO bars(symbol,tf,t,o,h,l,c,v) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(symbol,tf,t) DO UPDATE "
                      "SET o=excluded.o,h=excluded.h,l=excluded.l,c=excluded.c,v=excluded.v",
                      [(sym, tf, int(t.timestamp()), r.o, r.h, r.l, r.c, r.v) for t, r in df.iterrows()])
    db.set_state(f"data_updated:{sym}:{tf}", int(time.time()))
    return len(df)


def load(sym: str, tf: str) -> pd.DataFrame:
    r = db.rows("SELECT t,o,h,l,c,v FROM bars WHERE symbol=? AND tf=? ORDER BY t", (sym, tf))
    if not r:
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    df = pd.DataFrame(r)
    df.index = pd.to_datetime(df.pop("t"), unit="s", utc=True)
    return df


def last_update(sym: str, tf: str) -> int | None:
    return db.get_state(f"data_updated:{sym}:{tf}")


# ---------------------------------------------------------------- clock (tests can freeze it)
_clock = {"now": None}


def now_utc() -> datetime:
    return _clock["now"] or datetime.now(timezone.utc)


def set_clock(dt: datetime | None):
    _clock["now"] = dt


_early = threading.local()       # backtests only: earlier bars to put in front of a symbol's history (this thread)


def set_early(m: dict | None):
    """Backtests: {symbol: daily bars} used before the symbol's first stored bar (e.g. a 2x ETF built from its index
    before it existed). Per thread, so the bot's own evaluations never see it."""
    _early.m = m


def daily_closed(sym: str, now: datetime | None = None) -> pd.DataFrame:
    """Daily bars whose session has finished: today's row is dropped until 16:05 New York."""
    df = load(sym, "1d")
    ext = (getattr(_early, "m", None) or {}).get(sym)
    if ext is not None and not ext.empty:
        df = pd.concat([ext[ext.index < df.index[0]], df]) if not df.empty else ext
    if df.empty:
        return df
    now = now or now_utc()
    ny = now.astimezone(NY)
    today = pd.Timestamp(ny.date()).tz_localize("UTC")
    if ny.time() < datetime.strptime("16:05", "%H:%M").time():
        df = df[df.index < today]
    else:
        df = df[df.index <= today]
    return df


# ---------------------------------------------------------------- quotes
def quote(sym: str, max_age: int = 60) -> dict:
    """Last price (incl. pre/after market) from Yahoo, cached; in csv mode the last stored close."""
    hit = _qcache.get(sym)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    if source() == "csv":
        r = db.one("SELECT c, t FROM bars WHERE symbol=? AND tf IN ('1d','1h') AND t<=? ORDER BY t DESC LIMIT 1",
                   (sym, int(now_utc().timestamp())))
        if not r:
            for tf in ("1d", "1h"):
                try:
                    df = _csv(sym, tf)
                    df = df[df.index <= pd.Timestamp(now_utc())]
                    if len(df):
                        r = {"c": df["c"].iloc[-1], "t": int(df.index[-1].timestamp())}
                        break
                except DataError:
                    continue
        if not r:
            raise DataError(f"No price for {sym}")
        q = {"price": float(r["c"]), "bid": None, "ask": None, "time": int(r["t"]), "source": "csv"}
    else:
        import yfinance as yf
        h = _minutes(sym, max_age)
        if h is None or h.empty:
            h = yf.Ticker(yahoo_ticker(sym)).history(period="5d", interval="1d")
        if h is None or h.empty:
            raise DataError(f"No price for {sym}")
        q = {"price": float(h["Close"].iloc[-1]), "bid": None, "ask": None, "time": int(h.index[-1].timestamp()),
             "source": "yahoo"}
    _qcache[sym] = (time.time(), q)
    return q


_m1cache: dict = {}


def _minutes(sym: str, max_age: int = 60):
    """Yahoo 1-minute bars of the last days (pre/after market included), cached: one download per symbol per minute serves
    both the price quote and today's chart bar."""
    hit = _m1cache.get(sym)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    import yfinance as yf
    h = yf.Ticker(yahoo_ticker(sym)).history(period="5d", interval="1m", prepost=True, auto_adjust=False)
    _m1cache[sym] = (time.time(), h)
    return h


_tbcache: dict = {}


def today_bar(sym: str, max_age: int = 60) -> dict | None:
    """Today's regular-session bar so far (09:30 New York → now): {time, open, high, low, close}, or None before the open,
    on a market holiday or with no data. Charts only: the bot's decisions still use closed daily bars."""
    now = now_utc()
    ny = now.astimezone(NY)
    from . import markethours as mh
    b = mh.session_bounds(ny.date())
    if not b or now < b[0]:
        return None
    day = pd.Timestamp(ny.date()).tz_localize("UTC")
    hit = _tbcache.get(sym)
    if hit and time.time() - hit[0] < max_age and hit[1] == day:
        return hit[2]
    bar = None
    try:
        if source() == "csv":
            df = _csv(sym, "1d")
            if day in df.index:
                r = df.loc[day]
                bar = {"open": float(r.o), "high": float(r.h), "low": float(r.l), "close": float(r.c)}
        else:
            h = _minutes(sym, max_age)
            if h is not None and not h.empty:
                idx = h.index.tz_localize("America/New_York") if h.index.tz is None else h.index
                h = h[(idx >= b[0]) & (idx <= b[1])]
                if not h.empty:
                    bar = {"open": float(h["Open"].iloc[0]), "high": float(h["High"].max()), "low": float(h["Low"].min()),
                           "close": float(h["Close"].iloc[-1])}
    except Exception as e:  # a chart must never break on this
        log.warning("today bar %s: %s", sym, e)
    if bar:
        bar = {"time": int(day.timestamp()), **{k: round(v, 4) for k, v in bar.items()},
               "closed": now >= b[1]}
    _tbcache[sym] = (time.time(), day, bar)
    return bar


def add_today_bars(spec: dict) -> dict:
    """Strategy charts: put today's bar so far after the last closed daily bar of each daily chart ('SYM · 1D'), drawn
    lighter, so the chart shows where the price is now. It is not part of the signal until the close."""
    daily = [c for c in (spec or {}).get("charts") or [] if (c.get("title") or "").endswith(" · 1D") and c.get("candles")]
    syms = sorted({c["title"].split(" · ")[0] for c in daily})
    bars = dict(zip(syms, _pool().map(today_bar, syms))) if len(syms) > 1 else {x: today_bar(x) for x in syms}
    for c in daily:
        cs = c["candles"]
        bar = bars.get(c["title"].split(" · ")[0])
        if not bar or bar["time"] <= cs[-1]["time"]:
            continue
        up = bar["close"] >= bar["open"]
        col = "rgba(38,166,154,.45)" if up else "rgba(239,83,80,.45)"
        cs.append({**{k: bar[k] for k in ("time", "open", "high", "low", "close")}, "color": col, "wickColor": col,
                   "borderColor": "#26A69A" if up else "#EF5350", "today": "closed" if bar["closed"] else "live"})
    return spec


def set_quote(sym: str, price: float):
    """Tests: force a price."""
    _qcache[sym] = (time.time() + 10 ** 9, {"price": float(price), "bid": None, "ask": None, "time": int(time.time()),
                                            "source": "test"})


def clear_quotes():
    _qcache.clear()


_pool_ = None


def _pool():
    global _pool_
    if _pool_ is None:
        from concurrent.futures import ThreadPoolExecutor
        _pool_ = ThreadPoolExecutor(max_workers=8, thread_name_prefix="quotes")
    return _pool_


def _price(s):
    try:
        return quote(s)["price"]
    except Exception as e:  # a missing price must never break a page
        log.warning("quote %s: %s", s, e)
        return None


def prices(symbols) -> dict:
    """Last prices. Symbols not in the 1-minute cache are downloaded at the same time, not one after another."""
    syms = list(dict.fromkeys(s for s in symbols if s))
    cold = [s for s in syms if not (_qcache.get(s) and time.time() - _qcache[s][0] < 60)]
    if len(cold) > 1 and source() != "csv":
        list(_pool().map(_price, cold))                   # fills the cache
    return {s: _price(s) for s in syms}


def usdthb() -> float | None:
    try:
        return quote("THB=X", max_age=3600)["price"]
    except Exception:
        return None


def ny_date(dt: datetime) -> str:
    return dt.astimezone(NY).strftime("%Y-%m-%d")


def days_ago(n: int) -> datetime:
    return now_utc() - timedelta(days=n)
