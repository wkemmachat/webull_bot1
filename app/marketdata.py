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
        h = yf.Ticker(yahoo_ticker(sym)).history(period="5d", interval="1m", prepost=True)
        if h is None or h.empty:
            h = yf.Ticker(yahoo_ticker(sym)).history(period="5d", interval="1d")
        if h is None or h.empty:
            raise DataError(f"No price for {sym}")
        q = {"price": float(h["Close"].iloc[-1]), "bid": None, "ask": None, "time": int(h.index[-1].timestamp()),
             "source": "yahoo"}
    _qcache[sym] = (time.time(), q)
    return q


def set_quote(sym: str, price: float):
    """Tests: force a price."""
    _qcache[sym] = (time.time() + 10 ** 9, {"price": float(price), "bid": None, "ask": None, "time": int(time.time()),
                                            "source": "test"})


def clear_quotes():
    _qcache.clear()


def prices(symbols) -> dict:
    out = {}
    for s in symbols:
        if not s:
            continue
        try:
            out[s] = quote(s)["price"]
        except Exception as e:  # a missing price must never break a page
            log.warning("quote %s: %s", s, e)
            out[s] = None
    return out


def usdthb() -> float | None:
    try:
        return quote("THB=X", max_age=3600)["price"]
    except Exception:
        return None


def ny_date(dt: datetime) -> str:
    return dt.astimezone(NY).strftime("%Y-%m-%d")


def days_ago(n: int) -> datetime:
    return now_utc() - timedelta(days=n)
