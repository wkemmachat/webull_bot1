"""Dip zones: how far each strategy is below its own backtest high today, as a percentile of its underwater days.

Research (27 Oct 2026, the bot's own code, 2016–2026 and from 2008): buying when a strategy was deeper under water than on
70–80% of its past days led to better 6–12 month results for most strategies (smaller further falls, more often up a year
later). It is a statistic, not a promise: in 2008 deep dips kept falling.

  pct      share of the window's days (last 10 years of the backtest) that were LESS deep than today (0 = at a new high)
  zone     "dip"  for 70 ≤ pct < 80     ("Buy zone", green)
           "deep" for pct ≥ 80          ("Strong buy zone", solid dark green; LINE alert + Home banner on entry)
Refreshed once a day after the US close (and on start when missing). LINE fires when a strategy enters ≥ 80 and is armed
again only after it climbs back above the 70th percentile.
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from . import db, notify
from . import strategies as S

log = logging.getLogger("dip")
DIP, DEEP = 70.0, 80.0
WINDOW_YEARS = 10
MAX_AGE_S = 5 * 86400          # older than this (bot off for days): not shown


def zone_of(pct):
    if pct is None:
        return None
    return "deep" if pct >= DEEP else ("dip" if pct >= DIP else None)


def from_series(t, v) -> dict | None:
    """t: dates, v: backtest values (oldest first). Underwater is measured from the all-time high of the whole series;
    the percentile uses the last WINDOW_YEARS years."""
    s = pd.Series(np.asarray(v, dtype=float), index=pd.to_datetime(t)).dropna()
    s = s[s > 0]
    if len(s) < 60:
        return None
    depth = -(s / s.cummax() - 1.0)                       # 0 at a high, 0.25 = 25 % below it
    win = depth[depth.index >= depth.index[-1] - pd.DateOffset(years=WINDOW_YEARS)]
    cur = float(win.iloc[-1])
    pct = float(round((win.values < cur - 1e-12).mean() * 100)) if cur > 1e-9 else 0.0   # whole numbers: badge and zone agree
    q = {p: float(np.percentile(win.values, p)) for p in (70, 80, 90)}
    return {"depth": round(-cur * 100, 1), "pct": pct, "zone": zone_of(pct),
            "p70": round(-q[70] * 100, 1), "p80": round(-q[80] * 100, 1), "p90": round(-q[90] * 100, 1),
            "day": str(s.index[-1].date()), "from": str(win.index[0].date()),
            "years": round((win.index[-1] - win.index[0]).days / 365.25, 1)}


def compute(s, now=None) -> dict | None:
    from . import backtest
    r = backtest.run(strat=s, now=now)
    if not r.get("ok"):
        return None
    ser = r["series"]
    t = pd.to_datetime(ser["t"], unit="s")
    return from_series(t, ser["strategy"])


def get(sid) -> dict | None:
    x = db.get_state(f"dip:{sid}")
    if not x or time.time() - (x.get("at") or 0) > MAX_AGE_S:
        return None
    return {k: x.get(k) for k in ("depth", "pct", "zone", "p70", "p80", "p90", "day", "from", "years")}


def refresh_all(now=None, send=True) -> dict:
    out = {}
    for s in S.all_instances():
        try:
            d = compute(s, now)
        except Exception as e:                            # never stops the daily jobs
            log.warning("dip %s: %s", s.id, e)
            continue
        if not d:
            continue
        old = db.get_state(f"dip:{s.id}") or {}
        alerted = bool(old.get("alerted"))
        new_deep = d["pct"] >= DEEP and not alerted
        if d["pct"] < DIP:
            alerted = False                               # armed again once it is out of the dip zones
        if new_deep and (s.row or {}).get("control") != "stopped":
            alerted = True
            txt = (f"{s.name} is {d['depth']:.0f}% below its backtest high: deeper than {d['pct']:.0f}% of its days in the last "
                   f"{d['years']:g} years (80th percentile = {d['p80']:.0f}%, 90th = {d['p90']:.0f}%). In the backtests, money added "
                   "in this zone was more often up a year later — not a promise; dips can go deeper first.")
            db.add_event("info", "strategy", f"{s.name}: strong buy zone ({d['pct']:.0f}th percentile, {d['depth']:.0f}%)", txt, strategy=s.id)
            if send:
                notify.send("dip", f"Strong buy zone · {s.name}\n{txt}", strategy=s.id)
        elif new_deep:
            alerted = True                                # stopped: no message, but do not fire later for the same dip
        db.set_state(f"dip:{s.id}", {**d, "at": int(time.time()), "alerted": alerted})
        out[s.id] = d
    return out


def missing() -> bool:
    return not any(db.get_state(f"dip:{s.id}") for s in S.all_instances())
