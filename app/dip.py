"""Dip zones: how far each strategy is below its own backtest high today, as a percentile of its underwater days.

Research (27 Oct 2026, the bot's own code, 2016–2026 and from 2008): buying when a strategy was deeper under water than on
70–80% of its past days led to better 6–12 month results for most strategies (smaller further falls, more often up a year
later). It is a statistic, not a promise: in 2008 deep dips kept falling.

  pct      share of the window's days (last 20 years of the backtest, or all it has) that were LESS deep than today
           (0 = at a new high). 10 years until 28 Oct 2026; 20 years since, at your choice (stricter: 2008 counts too).
  zone     "dip"  for 70 ≤ pct < 80     ("Buy zone", green)
           "deep" for pct ≥ 80          ("Strong buy zone", solid dark green; LINE alert + Home banner on entry)
Refreshed once a day after the US close (and on start when missing). LINE fires when a strategy enters ≥ 80 and is armed
again only after it climbs back above the 70th percentile.

Deep-fall warning (6 Nov 2026): the same backtest also gives today's fall below the strategy's high next to its worst fall in
the last 10 years BEFORE this one (the current fall is left out, so a new record shows as more than 100%). LINE warns once
when the fall reaches 75% of that worst, and once more when it goes past it (100%); armed again after a new high.
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
WARN_LEVELS = (75, 100)          # % of the worst 10-year fall: "near its worst", "deeper than its worst"
WORST_YEARS = 10
VERSION = 2                      # bump when the backtests behind these numbers change (2: gold & silver from 2008, 7 Nov 2026)
WORST_MIN_YEARS = 5              # shorter backtests (the 4-hour metals: about 2 years of hourly data) get no warning
WINDOW_YEARS = 20
MAX_AGE_S = 5 * 86400          # older than this (bot off for days): not shown


def ordinal(n) -> str:
    n = int(round(n))
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


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
            "years": round((win.index[-1] - win.index[0]).days / 365.25, 1), **worst_before(s)}


def _worst(v):
    """(worst fall as a fraction ≤ 0, its peak date, its trough date) of a value series."""
    if len(v) < 2:
        return 0.0, None, None
    dd = v / v.cummax() - 1.0
    k = dd.idxmin()
    if dd[k] >= 0:
        return 0.0, None, None
    return float(dd[k]), str(v[:k].idxmax().date()), str(k.date())


def worst_before(s) -> dict:
    """Today's fall next to the worst fall before it: in the last WORST_YEARS years and in the whole backtest. Only days up
    to the current high count, so today's fall is never compared with itself."""
    pk = s.cummax()
    peak = s.index[np.where(s.values >= pk.values[-1] - 1e-12)[0][-1]]          # the last day at the high
    before = s[s.index <= peak]
    w10, a10, b10 = _worst(before[before.index >= s.index[-1] - pd.DateOffset(years=WORST_YEARS)])
    wall, aall, ball = _worst(before)
    cur = float(s.iloc[-1] / s.max() - 1.0)
    yrs10 = round(min(WORST_YEARS, (s.index[-1] - s.index[0]).days / 365.25), 1)
    return {"peak_day": str(peak.date()), "worst10": round(w10 * 100, 1), "worst10_from": a10, "worst10_to": b10,
            "worst10_years": yrs10, "worst_all": round(wall * 100, 1), "worst_all_from": aall, "worst_all_to": ball,
            "of_worst": round(cur / w10 * 100) if w10 < -1e-9 else None}


def warn_level(of_worst, years=None):
    """The highest warning level reached (75 or 100), or 0. None when the backtest is too short to say."""
    if years is not None and years < WORST_MIN_YEARS:
        return None
    return max([lv for lv in WARN_LEVELS if of_worst is not None and of_worst >= lv] or [0])


def money_fall(mode, sid) -> dict | None:
    """Your own money in the strategy: how far it is below its high since you started (money added or taken out is left
    out), from the same time-weighted index as the real return on the strategy cards (perf.real_index)."""
    from . import ledger, perf
    v = ledger.value(mode, sid)
    if (v["value"] or 0) < 0.5:
        return None
    r = perf.real_return(mode, sid, v["value"], v["net_in"] or 0)
    if not r:
        return None
    return {"fall": round(r["fall"] * 100, 1), "high_day": r["high_day"], "since": r["since"], "ret": round(r["ret"] * 100, 1)}


def compute(s, now=None) -> dict | None:
    from . import backtest
    r = backtest.run(strat=s, now=now)
    if not r.get("ok"):
        log.warning("dip %s: backtest failed (%s); its numbers stay as they were until the next try", s.id, r.get("error"))
        return None
    ser = r["series"]
    t = pd.to_datetime(ser["t"], unit="s")
    return from_series(t, ser["strategy"])


KEYS = ("depth", "pct", "zone", "p70", "p80", "p90", "day", "from", "years", "peak_day", "worst10", "worst10_from", "worst10_to",
        "worst10_years", "worst_all", "worst_all_from", "worst_all_to", "of_worst")


def get(sid) -> dict | None:
    x = db.get_state(f"dip:{sid}")
    if not x or time.time() - (x.get("at") or 0) > MAX_AGE_S:
        return None
    out = {k: x.get(k) for k in KEYS}
    out["warn"] = warn_level(out.get("of_worst"), out.get("worst10_years"))
    return out


def fall_text(s, d, mode_money=None) -> str:
    """The deep-fall warning message (LINE and the event log)."""
    def mon(day):
        return pd.Timestamp(day).strftime("%-d %b %Y") if day else "?"
    from .brokers import MODE_LABEL
    lv = warn_level(d.get("of_worst"))
    head = (f"deeper than its worst fall in the last {d['worst10_years']:g} years" if lv >= 100
            else f"{d['of_worst']}% of the way to its worst fall in the last {d['worst10_years']:g} years")
    t = (f"{s.name} is {abs(d['depth']):.1f}% below its backtest high of {mon(d['peak_day'])}: {head}. "
         f"Worst fall in those years: {d['worst10']:.1f}% ({mon(d['worst10_from'])} – {mon(d['worst10_to'])})")
    if d.get("worst_all") is not None and d["worst_all"] < d["worst10"] - 0.05:
        t += f"; whole backtest {d['worst_all']:.1f}% ({mon(d['worst_all_from'])} – {mon(d['worst_all_to'])})"
    t += "."
    for mode, m in (mode_money or {}).items():
        t += f" Your money ({MODE_LABEL.get(mode, mode)}): {m['fall']:.1f}% below its high" + (f" of {mon(m['high_day'])}" if m.get("high_day") else "") + "."
    t += (" The rules do not change on their own; this is a warning to check you are still comfortable holding it. "
          "There is no stop on top of the strategy's own exit (a stop was tested on 6 Nov 2026 and cut returns without "
          "making the worst falls smaller: Help → Design decisions). The way to take less risk is to hold less in it.")
    return t


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
            db.add_event("info", "strategy", f"{s.name}: strong buy zone ({ordinal(d['pct'])} percentile, {d['depth']:.0f}%)", txt, strategy=s.id)
            if send:
                notify.send("dip", f"Strong buy zone · {s.name}\n{txt}", strategy=s.id)
        elif new_deep:
            alerted = True                                # stopped: no message, but do not fire later for the same dip
        # deep-fall warning: once at 75% of the worst 10-year fall and once past it, per fall (armed again at a new high)
        lv = warn_level(d.get("of_worst"), d.get("worst10_years")) or 0
        warned = old.get("warned", 0) if old.get("warned_peak") == d.get("peak_day") else 0
        if lv > warned:
            money = {}
            for mode in ("live", "test", "paper"):
                try:
                    m = money_fall(mode, s.id)
                except Exception:
                    m = None
                if m:
                    money[mode] = m
            txt = fall_text(s, d, money)
            title = "Deeper than its worst fall" if lv >= 100 else "Near its worst fall"
            db.add_event("warn", "strategy", f"{s.name}: {title.lower()} ({d['depth']:.0f}% vs worst {d['worst10']:.0f}%)", txt, strategy=s.id)
            if send and (s.row or {}).get("control") != "stopped":
                notify.send("drawdown", f"⚠ {title} · {s.name}\n{txt}", strategy=s.id)
            warned = lv
        db.set_state(f"dip:{s.id}", {**d, "at": int(time.time()), "alerted": alerted, "win": WINDOW_YEARS, "v": VERSION,
                                     "warned": warned, "warned_peak": d.get("peak_day")})
        out[s.id] = d
    return out


def missing() -> bool:
    """Nothing stored yet, or stored with another window (the window changed: recompute on start, not at the next close)."""
    st = [db.get_state(f"dip:{s.id}") for s in S.all_instances()]
    return not any(st) or any(x and (x.get("win", 10) != WINDOW_YEARS or "worst10" not in x or x.get("v", 1) != VERSION) for x in st)
