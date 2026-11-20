"""Good time to add money? What happened a year after a strategy was this deep below its high, from its own backtest.

Research 20 Nov 2026 (project doc "When to add money", scripts /home/claude/dd_study): on days a strategy was deeper under
water than on 85% of its own PAST days (no look-ahead: each day is ranked only against the days before it, after a 3-year
warm-up), the Nasdaq/S&P strategies were more often up a year later, by more, and fell less first (ROM · Split 2C: the
30 times it reached the zone since 2010 were all higher a year later, typically +51%; any day +40%). Gold, silver and
USD · SMH: no edge (deep falls kept falling). Waiting for the zone with money you would add anyway cost more than it saved
(worse 52–75% of the time over 2 years), so the zone is for extra money kept aside.

  verdict   good   in the zone it was up more often AND by more AND fell less first, ≥ 90% of the times it got there were up
            safer  up more often and fell less first, ≥ 85% of the times up, but not by more
            mixed  about as good as any day (60%+ of the times up)
            none   no edge, or fewer than 6 separate falls to judge from
Stored per strategy after each US close (with the dip zones); LINE "Good time to add money" at the 85th percentile for good
and safer strategies, once per fall (armed again under the 70th).
"""
from __future__ import annotations

import bisect
import logging

import numpy as np
import pandas as pd

log = logging.getLogger("addmoney")
ZONE = 85.0            # percentile where the add window opens (the alert)
WARM = 756             # sessions before a day's percentile counts (3 years)
AHEAD = 252            # a year later
GAP = 20               # sessions out of the zone that make the next visit a new fall
WAIT_H = 504           # "wait for the zone" vs "add now": result 2 years after the decision
MIN_ENTRIES = 6
VERSION = 1


def past_pct(v: np.ndarray):
    """(depth ≥ 0, percentile of each day's depth among the days BEFORE it; NaN in the warm-up; 0 at a high)."""
    depth = -(v / np.maximum.accumulate(v) - 1.0)
    n, pct, srt = len(v), np.full(len(v), np.nan), []
    for i in range(n):
        if i >= WARM:
            pct[i] = 0.0 if depth[i] < 1e-9 else bisect.bisect_left(srt, depth[i] - 1e-12) / len(srt) * 100
        bisect.insort(srt, depth[i])
    return depth, pct


def _stats(f, fall, idx) -> dict | None:
    if len(idx) < 20:
        return None
    r, fl = f[idx], fall[idx]
    q = lambda x, p: round(float(np.percentile(x, p)), 4)
    return {"days": int(len(idx)), "up": round(float((r > 0).mean()), 4), "med": q(r, 50), "p10": q(r, 10), "p90": q(r, 90),
            "fall_med": q(fl, 50), "fall_p10": q(fl, 10)}


def _wait_cost(v, pct, thr=80.0) -> dict | None:
    """Add now vs wait for the thr-th percentile (at most a year, then add anyway): value 2 years after the decision."""
    n = len(v)
    d, waited = [], []
    for t in range(WARM, n - WAIT_H, 5):
        j = next((k for k in range(t, min(n, t + AHEAD)) if pct[k] >= thr), min(n - 1, t + AHEAD))
        d.append(v[t] / v[j] - 1.0)                   # (v_end / v_j) ÷ (v_end / v_t) − 1: > 0 = waiting was better
        waited.append(j - t)
    if len(d) < 50:
        return None
    d = np.array(d)
    return {"worse": round(float((d < 0).mean()), 3), "better": round(float((d > 0).mean()), 3), "mean": round(float(d.mean()), 4),
            "wait_days": int(np.median(waited)), "never": round(float(np.mean(np.array(waited) >= AHEAD)), 3)}


def verdict(z, a, entries) -> str:
    if not z or not a or len(entries) < MIN_ENTRIES:
        return "none"
    share = sum(1 for e in entries if e[1] > 0) / len(entries)
    up_ok, fall_ok = z["up"] >= a["up"], z["fall_p10"] >= a["fall_p10"]
    better = z["med"] >= a["med"] and (z["med"] >= a["med"] + 0.02 or z["up"] >= a["up"] + 0.02)
    if up_ok and fall_ok and better and share >= 0.9:
        return "good"
    if up_ok and fall_ok and share >= 0.85:
        return "safer"
    if z["up"] >= a["up"] - 0.03 and z["med"] >= 0.8 * a["med"] and share >= 0.6:
        return "mixed"
    return "none"


def from_series(t, v) -> dict | None:
    """t: dates, v: the strategy's backtest values (oldest first)."""
    s = pd.Series(np.asarray(v, dtype=float), index=pd.to_datetime(t)).dropna()
    s = s[s > 0]
    if len(s) < WARM + AHEAD + 40:
        return None
    v = s.values
    n = len(v)
    depth, pct = past_pct(v)
    f, fall = np.full(n, np.nan), np.full(n, np.nan)
    lo = pd.Series(v[::-1]).rolling(AHEAD + 1, min_periods=1).min().values[::-1]     # lowest value from i to i+AHEAD
    f[:n - AHEAD] = v[AHEAD:] / v[:n - AHEAD] - 1.0
    fall[:n - AHEAD] = lo[:n - AHEAD] / v[:n - AHEAD] - 1.0
    ok = ~np.isnan(f) & ~np.isnan(pct)
    zi, ai = np.where(ok & (pct >= ZONE))[0], np.where(ok)[0]
    firsts = [int(zi[0])] + [int(zi[j]) for j in range(1, len(zi)) if zi[j] - zi[j - 1] > GAP] if len(zi) else []
    entries = [(str(s.index[i].date()), round(float(f[i]), 4)) for i in firsts]
    z, a = _stats(f, fall, zi), _stats(f, fall, ai)
    # the window and depths the Buy-zone badge uses (dip.py: last 20 years, today included), for the gauge
    from .dip import WINDOW_YEARS
    win = depth[s.index >= s.index[-1] - pd.DateOffset(years=WINDOW_YEARS)]
    out = {"v": VERSION, "verdict": verdict(z, a, entries), "zone": ZONE, "zone_depth": round(-float(np.percentile(win, ZONE)) * 100, 1),
           "buy_depth": round(-float(np.percentile(win, 70)) * 100, 1), "since": str(s.index[ai[0]].date()) if len(ai) else None,
           "entries": entries, "n": len(entries), "up_n": sum(1 for e in entries if e[1] > 0),
           "entry_med": round(float(np.median([e[1] for e in entries])), 4) if entries else None,
           "entry_worst": round(min(e[1] for e in entries), 4) if entries else None,
           "zone_days": z, "any_day": a, "wait": _wait_cost(v, pct)}
    return out


def compute(s, now=None) -> dict | None:
    from . import backtest
    r = backtest.run(strat=s, now=now)
    if not r.get("ok"):
        return None
    ser = r["series"]
    return from_series(pd.to_datetime(ser["t"], unit="s"), ser["strategy"])


def get(sid) -> dict | None:
    from . import db, dip
    x = db.get_state(f"add:{sid}")
    if not x or x.get("v") != VERSION:
        return None
    d = dip.get(sid)
    out = dict(x, sid=sid)
    out["now"] = {"pct": d["pct"], "depth": d["depth"], "day": d["day"], "worst10": d.get("worst10"), "of_worst": d.get("of_worst")} if d else None
    out["in_zone"] = bool(d and d["pct"] >= ZONE)
    out["label"] = label(out["verdict"], out["in_zone"])
    return out


def brief(sid) -> dict | None:
    """The few fields the Dashboard list needs."""
    x = get(sid)
    if not x:
        return None
    z = x.get("zone_days") or {}
    return {"verdict": x["verdict"], "in_zone": x["in_zone"], "label": x["label"], "n": x["n"], "up_n": x["up_n"],
            "entry_med": x["entry_med"], "entry_worst": x["entry_worst"], "typical": z.get("med"), "bad": z.get("p10")}


def label(verdict_, in_zone) -> str:
    if verdict_ == "none":
        return "No signal"
    if not in_zone:
        return "Not yet"
    return {"good": "Good time", "safer": "OK, safer", "mixed": "Mixed"}[verdict_]


def usd(x) -> str:
    return f"${x:,.0f}"


def line_text(name, x, d) -> str:
    z = x["zone_days"]
    every = " — every time" if x["up_n"] == x["n"] else ""
    head = "▲ Good time to add money" if x["verdict"] == "good" else "▲ OK time to add money (safer, not bigger)"
    return (f"{head} · {name}\n{name} is {abs(d['depth']):.0f}% below its high ({d['pct']:.0f}th percentile). The last {x['n']} times "
            f"it got this cheap, it was higher a year later {x['up_n']} of {x['n']} times{every}.\n"
            f"$1,000 added then → typically {usd(1000 * (1 + z['med']))} a year later (bad year {usd(1000 * (1 + z['p10']))}). "
            f"It may dip first, typically to {usd(1000 * (1 + z['fall_med']))}.\n"
            "For extra money you keep aside. History of its backtest, not a promise.")
