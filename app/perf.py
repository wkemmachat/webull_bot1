"""Real results per strategy and the falls to expect.

Daily P&L: the bot records every strategy's value and net money in every 30 minutes (table `equity`). The last record of
each US trading day is that day's close. Profit/loss of a day = value change minus money added (plus money withdrawn) that
day, so adding money never looks like profit.

Drawdowns ("falls"): the depth below the previous high, how long the fall took, how long until a new high (time
underwater), from the strategy's backtest (long history) and from its real values in the mode you are looking at
(a time-weighted index, so deposits and withdrawals do not count as gains or losses).
"""
from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

from . import db, ledger, marketdata as md, markethours as mh
from . import strategies as S

NY = ZoneInfo("America/New_York")


# ---------------------------------------------------------------- daily P&L
def _closes(mode, sid, since_days=None):
    """[(NY date, value, capital, t)] — the last record of each US trading day (plus today so far)."""
    since = int(md.now_utc().timestamp() - since_days * 86400) if since_days else 0
    rows = db.rows("SELECT t, value, capital FROM equity WHERE mode=? AND strategy=? AND t>=? ORDER BY t", (mode, sid, since))
    by_day = {}
    for r in rows:
        d = datetime.fromtimestamp(r["t"], NY).date()
        by_day[d] = (d, float(r["value"] or 0), float(r["capital"] or 0), r["t"])
    today = md.now_utc().astimezone(NY).date()
    return [v for d, v in sorted(by_day.items()) if mh.is_trading_day(d) or d == today]


def daily(mode, sid, limit=None) -> dict:
    cl = _closes(mode, sid)
    today = md.now_utc().astimezone(NY).date()
    out, prev = [], None
    for d, v, c, t in cl:
        if prev is None:
            if c <= 0 and v <= 0:
                continue
            flow, base = c, c
            pnl = v - c
        else:
            flow = c - prev[2]
            pnl = v - prev[1] - flow
            base = prev[1] + max(flow, 0.0)
        if prev is None or abs(pnl) > 0.004 or abs(flow) > 0.004 or v > 0.004:
            out.append({"date": d.isoformat(), "value": round(v, 2), "pnl": round(pnl, 2), "pct": (pnl / base) if base > 0.5 else None,
                        "flow": round(flow, 2), "total": round(v - c, 2), "net_in": round(c, 2), "today": d == today})
        prev = (d, v, c)
    out.reverse()
    days = [r for r in out if not r["today"]]
    stats = None
    if days:
        p = [r["pnl"] for r in days]
        stats = {"days": len(days), "up": sum(1 for x in p if x > 0.004), "down": sum(1 for x in p if x < -0.004),
                 "best": max(days, key=lambda r: r["pnl"]), "worst": min(days, key=lambda r: r["pnl"]),
                 "sum": round(sum(p), 2)}
    return {"rows": out[:limit] if limit else out, "stats": stats}


def today_pnl(mode, sid, value_now=None, net_now=None) -> dict | None:
    """Profit/loss of the current US session since the last close (money moved today left out). Outside a session
    (weekend, holiday, before the open) it is the last completed session's result, marked live=False."""
    cl = _closes(mode, sid, since_days=12)
    now_ny = md.now_utc().astimezone(NY)
    today = now_ny.date()
    in_session = mh.is_trading_day(today) and now_ny.strftime("%H:%M") >= "09:30"
    if not in_session:
        done = [x for x in cl if x[0] < today]
        if len(done) < 2:
            return None
        a, b = done[-2], done[-1]
        flow = b[2] - a[2]
        pnl = b[1] - a[1] - flow
        base = a[1] + max(flow, 0.0)
        return {"pnl": round(pnl, 2), "pct": (pnl / base) if base > 0.5 else None, "since": a[0].isoformat(), "day": b[0].isoformat(),
                "live": False}
    prev = next((x for x in reversed(cl) if x[0] < today), None)
    if prev is None:
        return None
    if value_now is None or net_now is None:
        v = ledger.value(mode, sid)
        value_now, net_now = v["value"], v["net_in"] or 0
    flow = net_now - prev[2]
    pnl = value_now - prev[1] - flow
    base = prev[1] + max(flow, 0.0)
    return {"pnl": round(pnl, 2), "pct": (pnl / base) if base > 0.5 else None, "since": prev[0].isoformat(), "day": today.isoformat(),
            "live": True}


def daily_csv(mode, sid) -> str:
    s = S.get(sid)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date (US)", "strategy", "mode", "value at close", "P&L that day", "P&L %", "money in (+) / out (-)",
                "total P&L since start", "net money in"])
    for r in reversed(daily(mode, sid)["rows"]):
        w.writerow([r["date"] + (" (so far)" if r["today"] else ""), s.name if s else sid, mode, f"{r['value']:.2f}", f"{r['pnl']:.2f}",
                    f"{r['pct'] * 100:.2f}" if r["pct"] is not None else "", f"{r['flow']:.2f}", f"{r['total']:.2f}", f"{r['net_in']:.2f}"])
    return buf.getvalue()


# ---------------------------------------------------------------- drawdowns
def drawdowns(days: list, values: list, top: int = 5) -> dict | None:
    """days: datetime.date list, values: index/equity values. Depth, length and recovery of the falls."""
    v = np.asarray(values, dtype=float)
    if len(v) < 2 or not np.all(np.isfinite(v)) or v.min() <= 0:
        return None
    peak = np.maximum.accumulate(v)
    dd = v / peak - 1
    eps, i, n = [], 0, len(v)
    while i < n:
        if dd[i] < -1e-9:
            s = i - 1                                    # the peak day
            j = i
            while j < n and dd[j] < -1e-9:
                j += 1
            seg = dd[i:j]
            k = i + int(np.argmin(seg))
            rec = j if j < n else None
            eps.append({"depth": round(float(dd[k]) * 100, 2), "peak": str(days[s]), "trough": str(days[k]),
                        "recovered": str(days[rec]) if rec is not None else None,
                        "days_down": (days[k] - days[s]).days, "days_under": ((days[rec] if rec is not None else days[-1]) - days[s]).days,
                        "days_to_recover": (days[rec] - days[k]).days if rec is not None else None, "ongoing": rec is None})
            i = j
        else:
            i += 1
    span = (days[-1] - days[0]).days or 1
    worst = min(eps, key=lambda e: e["depth"]) if eps else None
    longest = max(eps, key=lambda e: e["days_under"]) if eps else None
    under = sum(1 for x in dd if x < -1e-9) / len(dd)
    cur = eps[-1] if eps and eps[-1]["ongoing"] else None
    return {"from": str(days[0]), "to": str(days[-1]), "years": round(span / 365.25, 1),
            "worst": worst, "longest": longest, "current": {"depth": round(float(dd[-1]) * 100, 2), "since": cur["peak"] if cur else None,
                                                             "days": cur["days_under"] if cur else 0},
            "top": sorted(eps, key=lambda e: e["depth"])[:top], "pct_under": round(under * 100, 1),
            "count_10": sum(1 for e in eps if e["depth"] <= -10), "count_20": sum(1 for e in eps if e["depth"] <= -20),
            "count_30": sum(1 for e in eps if e["depth"] <= -30),
            "median_days_under_10": int(np.median([e["days_under"] for e in eps if e["depth"] <= -10])) if any(e["depth"] <= -10 for e in eps) else None}


def _weekly_underwater(days, values, max_points=520):
    v = np.asarray(values, dtype=float)
    dd = v / np.maximum.accumulate(v) - 1
    step = max(1, len(v) // max_points)
    idx = list(range(0, len(v), step))
    if idx[-1] != len(v) - 1:
        idx.append(len(v) - 1)
    # keep each window's lowest point so the deepest falls are drawn at their true depth
    out = []
    for a, b in zip(idx, idx[1:] + [len(v)]):
        seg = dd[a:max(b, a + 1)]
        k = a + int(np.argmin(seg))
        out.append([str(days[k]), round(float(dd[k]) * 100, 2)])
    return out


def live_index(mode, sid):
    """Time-weighted index of the real values: deposits and withdrawals are not gains or losses."""
    cl = _closes(mode, sid)
    days, idx, prev, x = [], [], None, 1.0
    for d, v, c, t in cl:
        if prev is None:
            if v <= 0:
                continue
        else:
            flow = c - prev[2]
            base = prev[1] + max(flow, 0.0)
            if base > 0.5:
                x *= 1 + (v - prev[1] - flow) / base
        days.append(d)
        idx.append(x)
        prev = (d, v, c)
    return days, idx


def strategy_risk(sid, mode) -> dict:
    """Falls of one strategy: its backtest history, its real values, and the research's worst fall."""
    from . import backtest, expected
    s = S.get(sid)
    if not s:
        raise KeyError(sid)
    out = {"strategy": sid, "name": s.name, "family": s.family}
    try:
        r = backtest.run(sid)
    except Exception as e:                                       # a failed backtest never breaks the page
        r = {"ok": False, "error": str(e)}
    if r.get("ok"):
        days = [datetime.fromtimestamp(t, timezone.utc).date() for t in r["series"]["t"]]
        vals = r["series"]["strategy"]
        bt = drawdowns(days, vals)
        if bt:
            bt["underwater"] = _weekly_underwater(days, vals)
            bt["source"] = "Backtest on real prices"
            bt["built"] = (r.get("data") or {}).get("built") or {}       # {symbol: first real day}: earlier prices built from the index
            ten = [i for i, d in enumerate(days) if d >= date(days[-1].year - 10, days[-1].month, min(days[-1].day, 28))]
            if ten and ten[0] > 0:
                b10 = drawdowns(days[ten[0]:], vals[ten[0]:], top=1)
                bt["ten"] = {k: b10[k] for k in ("worst", "longest", "pct_under")} if b10 else None
        out["backtest"] = bt
        db.set_state(f"ddsum:{sid}", {"at": int(time.time()), "worst": bt["worst"] if bt else None, "longest": bt["longest"] if bt else None,
                                      "from": bt["from"] if bt else None})
    else:
        out["backtest"] = None
        out["backtest_error"] = r.get("error")
    d, x = live_index(mode, sid)
    out["live"] = drawdowns(d, x, top=3) if len(d) >= 2 else None
    if out["live"]:
        out["live"]["underwater"] = _weekly_underwater(d, x)
    spec = expected.load_file()["strategies"].get(sid) or {}
    rs = spec.get("research") or {}
    out["research"] = {"maxdd": rs.get("maxdd") or (spec.get("expect") or {}).get("maxdd"), "source": rs.get("source"),
                       "period": rs.get("period")} if spec else None
    return out


def card_summary(sid) -> dict | None:
    """Worst fall and longest time underwater from the last backtest the bot ran (for the strategy cards)."""
    x = db.get_state(f"ddsum:{sid}")
    if not x or not x.get("worst"):
        return None
    return {"worst": x["worst"]["depth"], "longest_days": x["longest"]["days_under"] if x.get("longest") else None, "from": x.get("from")}
