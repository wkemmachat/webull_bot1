"""Profit & loss page: since start and month by month, for one trading mode.

Numbers (all from the bot's own records, never from Webull's statement):
  day        the last equity record of each US trading day for all strategies together (strategy '*'), plus now from live
             prices. P&L of a day = value change − money moved in or out that day (as the Daily P&L tab).
  month      calendar months of the US trading day (New York date). start = value at the previous month's last day, put in =
             money moved in − out, profit / loss = sum of its days, end = value at its last day: start + put in + P&L = end.
  return     time-weighted: the day returns P&L ÷ (value before + money put in that day) chained, so a deposit is never a gain.
             Not annualised (the page says so while the record is under a year).
  held       the same money bought and held in the same ETFs (the Dashboard's "vs buy & hold" line), same formulas.
  since      the Dashboard's Since start number exactly (views.pnl_breakdown 'all'): the latest month is that total minus the
             earlier months, so every view adds up.
  strategy   each strategy's own Daily P&L rows by month; its latest month is again its since-start P&L minus the earlier
             months, so the strategy rows add up to the month totals (a timing row shows any small gap).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from . import db, marketdata as md, markethours as mh, perf, views

NY = perf.NY


def _days(mode):
    """[(NY date, value, capital, bench)] — the last record of each US trading day for all strategies together."""
    rows = db.rows("SELECT t, value, capital, bench FROM equity WHERE mode=? AND strategy='*' ORDER BY t", (mode,))
    by_day = {}
    for r in rows:
        d = datetime.fromtimestamp(r["t"], NY).date()
        by_day[d] = (d, float(r["value"] or 0), float(r["capital"] or 0), float(r["bench"]) if r["bench"] is not None else None)
    today = md.now_utc().astimezone(NY).date()
    out = [v for d, v in sorted(by_day.items()) if mh.is_trading_day(d) and d != today]
    while out and out[0][2] <= 0.5 and out[0][1] <= 0.5:            # before the first money
        out.pop(0)
    return out, by_day.get(today), today


def _fees(mode):
    out = {}
    try:
        rows = db.rows("SELECT COALESCE(updated_at, submitted_at) t, fee FROM orders WHERE mode=? AND COALESCE(fee,0)<>0", (mode,))
    except Exception:
        return out
    for r in rows:
        if r["t"]:
            m = datetime.fromtimestamp(r["t"], NY).strftime("%Y-%m")
            out[m] = out.get(m, 0.0) + float(r["fee"] or 0)
    return out


def build(mode):
    b = views.pnl_breakdown(mode, "all")
    rows = b["rows"]
    live_v = sum(r["value"] for r in rows)
    live_c = sum(r["net_in"] for r in rows)
    days, today_rec, today = _days(mode)
    bench_now = today_rec[3] if today_rec else (days[-1][3] if days else None)
    if rows and (abs(live_v) > 0.5 or abs(live_c) > 0.5):
        days.append((today, live_v, live_c, bench_now))           # now, from live prices: = the Dashboard's Since start
    out = {"mode": mode, "days": [], "months": [], "strategies": [], "since": None, "fees_total": 0.0, "timing": {}}
    if not days:
        return out
    fees = _fees(mode)
    prev = (None, 0.0, 0.0, 0.0)
    months = {}
    for d, v, c, bn in days:
        flow = c - prev[2]
        pnl = v - prev[1] - flow
        base = prev[1] + max(flow, 0.0)
        r = pnl / base if base > 0.5 else 0.0
        if bn is not None and prev[3] is not None:
            bp = bn - prev[3] - flow
            bbase = prev[3] + max(flow, 0.0)
            br = bp / bbase if bbase > 0.5 else 0.0
        else:
            bp, br = None, None
        live = d == today
        out["days"].append({"d": d.isoformat(), "v": round(v, 2), "c": round(c, 2), "b": round(bn, 2) if bn is not None else None,
                            "pnl": round(pnl, 2), "flow": round(flow, 2), "r": r, "live": live})
        k = d.strftime("%Y-%m")
        m = months.setdefault(k, {"m": k, "start": prev[1], "start_b": prev[3], "flow": 0.0, "pnl": 0.0, "f": 1.0, "bf": 1.0, "bpnl": 0.0,
                                  "bok": True, "up": 0, "down": 0, "best": None, "worst": None, "days": 0, "first": d.isoformat()})
        m["flow"] += flow
        m["pnl"] += pnl
        m["f"] *= 1 + r
        if br is None:
            m["bok"] = False
        else:
            m["bf"] *= 1 + br
            m["bpnl"] += bp
        if not live:
            m["days"] += 1
            if pnl > 0.004:
                m["up"] += 1
            elif pnl < -0.004:
                m["down"] += 1
            if m["best"] is None or pnl > m["best"]["pnl"]:
                m["best"] = {"d": d.isoformat(), "pnl": round(pnl, 2)}
            if m["worst"] is None or pnl < m["worst"]["pnl"]:
                m["worst"] = {"d": d.isoformat(), "pnl": round(pnl, 2)}
        m["end"], m["last"], m["live"] = v, d.isoformat(), live
        prev = (d, v, c, bn)
    f_all, bf_all, b_ok = 1.0, 1.0, True
    for k in sorted(months):
        m = months[k]
        f_all *= m["f"]
        if m["bok"]:
            bf_all *= m["bf"]
        else:
            b_ok = False
        out["months"].append({"m": k, "start": round(m["start"], 2), "flow": round(m["flow"], 2), "pnl": round(m["pnl"], 2),
                              "end": round(m["end"], 2), "ret": m["f"] - 1, "held_ret": (m["bf"] - 1) if m["bok"] else None,
                              "held_pnl": round(m["bpnl"], 2) if m["bok"] else None, "up": m["up"], "down": m["down"],
                              "days": m["days"], "best": m["best"], "worst": m["worst"], "first": m["first"], "last": m["last"],
                              "to_date": m["live"], "fees": round(fees.get(k, 0.0), 2)})
    last = days[-1]
    total = b["total"] if b["total"] is not None else round(last[1] - last[2], 2)
    held = (last[3] - last[2]) if last[3] is not None else None
    n_days = sum(m["days"] for m in out["months"])
    out["since"] = {"first": days[0][0].isoformat(), "last": last[0].isoformat(), "put_in": round(last[2], 2), "worth": round(last[1], 2),
                    "pnl": total, "ret": f_all - 1, "held_pnl": round(held, 2) if held is not None else None,
                    "held_ret": (bf_all - 1) if b_ok else None, "days": n_days,
                    "up": sum(m["up"] for m in out["months"]), "down": sum(m["down"] for m in out["months"]),
                    "years": round(((days[-1][0] - days[0][0]).days) / 365.25, 2)}
    out["fees_total"] = round(sum(fees.values()), 2)
    # each strategy by month; its latest month closes the gap to its since-start P&L (= the Dashboard row)
    keys = [m["m"] for m in out["months"]]
    tot_by_m = {k: 0.0 for k in keys}
    for r in rows:
        d = perf.daily(mode, r["id"])
        by = {}
        for x in d["rows"]:
            k = x["date"][:7]
            by[k] = by.get(k, 0.0) + (x["pnl"] or 0.0)
        mine = [k for k in keys if k in by] or keys[-1:]
        lastk = keys[-1]
        earlier = sum(v for k, v in by.items() if k != lastk)
        by[lastk] = (r["pnl"] or 0.0) - earlier
        for k in keys:
            tot_by_m[k] += by.get(k, 0.0)
        out["strategies"].append({"id": r["id"], "name": r["name"], "color": r["color"], "pnl": r["pnl"], "pct": r.get("pct"),
                                  "value": r["value"], "no_money": r.get("no_money", False), "control": r.get("control"),
                                  "months": {k: round(v, 2) for k, v in by.items() if k in keys and abs(v) >= 0.005}, "active_months": mine})
    gap = {k: round(next(m["pnl"] for m in out["months"] if m["m"] == k) - tot_by_m[k], 2) for k in keys}
    out["timing"] = {k: v for k, v in gap.items() if abs(v) >= 1}
    out["strategies"].sort(key=lambda s: s["pnl"] or 0)
    return out


def csv_text(mode):
    rep = build(mode)
    buf = io.StringIO()
    w = csv.writer(buf)
    names = [s["name"] for s in rep["strategies"]]
    w.writerow(["month", "start_usd", "put_in_usd", "pnl_usd", "return_pct", "held_instead_pct", "end_usd", "fees_usd", "up_days", "down_days"] + names)
    for m in rep["months"]:
        w.writerow([m["m"], m["start"], m["flow"], m["pnl"], round(m["ret"] * 100, 3),
                    "" if m["held_ret"] is None else round(m["held_ret"] * 100, 3), m["end"], m["fees"], m["up"], m["down"]]
                   + [s["months"].get(m["m"], 0) for s in rep["strategies"]])
    s = rep["since"]
    if s:
        w.writerow(["since_start", 0, s["put_in"], s["pnl"], round(s["ret"] * 100, 3),
                    "" if s["held_ret"] is None else round(s["held_ret"] * 100, 3), s["worth"], rep["fees_total"], s["up"], s["down"]]
                   + [x["pnl"] for x in rep["strategies"]])
    return buf.getvalue()
