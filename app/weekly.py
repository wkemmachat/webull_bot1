"""Weekly Live report (LINE, Saturday morning Bangkok) and trading costs.

For each strategy with money in the mode:
  real      the week's time-weighted return of its real value (money added or taken out is not a gain or loss), and $
  backtest  the same strategy's backtest over the same days (bot code, real fee) — the gap shows whether Live follows it
Trading this week and since the first Live order:
  fees      what Webull charged (booked per fill)
  vs open   each fill against that day's opening price, which is where the daily backtests fill: the real cost of
            trading (spread, limit offset, timing, retries). Positive = cost (paid more on a buy / got less on a sell).
Reports are kept (last 26 per mode) and shown on the Portfolio page.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta

import pandas as pd

from . import brokers, db, ledger, marketdata as md, notify, perf
from . import strategies as S
from .markethours import NY

log = logging.getLogger("weekly")
KEEP = 26


def week_window(now: datetime) -> tuple[date, date]:
    """Monday – Friday (New York) of the current week; on a weekend the week that just ended."""
    d = now.astimezone(NY).date()
    if d.weekday() >= 5:
        d -= timedelta(days=d.weekday() - 4)
    start = d - timedelta(days=d.weekday())
    return start, min(d, start + timedelta(days=4))


def _span(days: list, vals: list, start: date, end: date):
    """(value before the week, value at the end of the week) from a dated series; None when the week has no data."""
    base = endv = None
    for d, v in zip(days, vals):
        if d < start:
            base = v
        if d <= end:
            endv = v
    if endv is None:
        return None
    if base is None:                                # started during the week: from its first value
        base = next((v for d, v in zip(days, vals) if d >= start), None)
    return (base, endv) if base else None


def _real(mode, sid, start, end):
    """(week return, $ result, first day used when the money started during the week else None)."""
    days, idx = perf.live_index(mode, sid)
    sp = _span(days, idx, start, end)
    first = None
    if sp and not any(d < start for d in days):
        first = next((d for d in days if d >= start), None)
    cl = perf._closes(mode, sid)
    usd = None
    if cl:
        before = [x for x in cl if x[0] < start]
        upto = [x for x in cl if x[0] <= end]
        if upto:
            a = before[-1] if before else next((x for x in cl if x[0] >= start), None)
            b = upto[-1]
            if a:
                usd = (b[1] - a[1]) - (b[2] - a[2]) if before else b[1] - b[2]
    return (sp[1] / sp[0] - 1 if sp else None), usd, first


def _backtest(s, start, end):
    from . import backtest
    try:
        r = backtest.run(strat=s)
    except Exception as e:
        log.warning("weekly backtest %s: %s", s.id, e)
        return None
    if not r.get("ok"):
        return None
    days = [datetime.utcfromtimestamp(t).date() for t in r["series"]["t"]]
    sp = _span(days, r["series"]["strategy"], start, end)
    return sp[1] / sp[0] - 1 if sp else None


_opens: dict = {}


def day_open(sym: str, d: date) -> float | None:
    """That day's regular-session opening price (stored daily bars, else a fresh download)."""
    key = (sym, d)
    if key in _opens:
        return _opens[key]
    px = None
    ts = pd.Timestamp(d).tz_localize("UTC")
    for getter in (lambda: md.load(sym, "1d"), lambda: md.fetch(sym, "1d", 40)):
        try:
            df = getter()
        except Exception as e:
            log.info("open %s %s: %s", sym, d, e)
            continue
        if df is not None and not df.empty and ts in df.index:
            px = float(df.loc[ts, "o"])
            break
    _opens[key] = px
    return px


def fills(mode, since_ts: int, until_ts: int | None = None, sid: str | None = None) -> list:
    q = ("SELECT id, strategy, symbol, side, applied_qty q, applied_value v, COALESCE(fee,0) fee, submitted_at, updated_at "
         "FROM orders WHERE mode=? AND applied_qty>0 AND COALESCE(submitted_at, updated_at)>=?")
    args = [mode, since_ts]
    if until_ts:
        q += " AND COALESCE(submitted_at, updated_at)<=?"
        args.append(until_ts)
    if sid:
        q += " AND strategy=?"
        args.append(sid)
    out = []
    for r in db.rows(q + " ORDER BY submitted_at", args):
        t = r["submitted_at"] or r["updated_at"]
        d = datetime.fromtimestamp(t, NY).date()
        avg = r["v"] / r["q"] if r["q"] else None
        ref = day_open(r["symbol"], d)
        cost = None
        if ref and avg:
            cost = (avg - ref) * r["q"] if r["side"] == "BUY" else (ref - avg) * r["q"]
        out.append({"id": r["id"], "strategy": r["strategy"], "symbol": r["symbol"], "side": r["side"], "qty": r["q"],
                    "avg": avg, "value": r["v"], "fee": r["fee"], "day": str(d), "open": ref, "cost": cost,
                    "cost_pct": cost / (ref * r["q"]) if cost is not None and ref else None})
    return out


def cost_summary(fl: list) -> dict:
    traded = sum(f["value"] for f in fl)
    fees = sum(f["fee"] for f in fl)
    known = [f for f in fl if f["cost"] is not None]
    cost = sum(f["cost"] for f in known)
    base = sum(f["open"] * f["qty"] for f in known)
    return {"fills": len(fl), "traded": round(traded, 2), "fees": round(fees, 2), "fee_pct": fees / traded if traded else None,
            "cost": round(cost, 2), "cost_pct": cost / base if base else None, "unknown": len(fl) - len(known)}


def build(mode: str, now: datetime | None = None) -> dict:
    now = now or md.now_utc()
    start, end = week_window(now)
    t0 = int(datetime.combine(start, datetime.min.time(), NY).timestamp())
    t1 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), NY).timestamp())
    rows = []
    for s in S.all_instances():
        v = ledger.value(mode, s.id)
        if abs(v["value"]) < 0.5 and not v["positions"]:
            continue
        real, usd, first = _real(mode, s.id, start, end)
        bt = _backtest(s, first + timedelta(days=1) if first else start, end)   # same days as the real money
        rows.append({"id": s.id, "name": s.name, "color": s.color, "value": round(v["value"], 2), "real": real,
                     "usd": round(usd, 2) if usd is not None else None, "backtest": bt,
                     "gap": (real - bt) if real is not None and bt is not None else None})
    rows.sort(key=lambda r: -r["value"])
    acc_ret, acc_usd, _ = _real(mode, "*", start, end)
    wk = fills(mode, t0, t1)
    for f in wk:
        st = S.get(f["strategy"])
        f["name"] = st.name if st else f["strategy"]
    first = db.one("SELECT MIN(submitted_at) t FROM orders WHERE mode=? AND applied_qty>0", (mode,))
    all_f = fills(mode, int(first["t"] or 0)) if first and first["t"] else []
    by = {}
    for f in all_f:
        by.setdefault(f["strategy"], []).append(f)
    since = [{"id": k, "name": (S.get(k).name if S.get(k) else k), **cost_summary(v)} for k, v in by.items()]
    since.sort(key=lambda r: -r["traded"])
    worst = max((f for f in wk if f["cost_pct"] is not None), key=lambda f: f["cost_pct"], default=None)
    return {"mode": mode, "week": f"{start.isoformat()}", "from": str(start), "to": str(end), "at": int(time.time()),
            "value": round(sum(r["value"] for r in rows), 2), "ret": acc_ret, "usd": round(acc_usd, 2) if acc_usd is not None else None,
            "strategies": rows, "fills": wk, "week_costs": cost_summary(wk), "since": since,
            "since_costs": cost_summary(all_f), "since_from": datetime.fromtimestamp(first["t"], NY).date().isoformat()
            if first and first["t"] else None, "worst": worst}


def _p(x, d=1, sign=True):
    if x is None:
        return "—"
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def text(r: dict) -> str:
    a, b = date.fromisoformat(r["from"]), date.fromisoformat(r["to"])
    head = f"Weekly report · {brokers.MODE_LABEL.get(r['mode'], r['mode'])} · {a.day} {a:%b} – {b.day} {b:%b}"
    lines = [head, f"Strategies ${r['value']:,.0f} · this week {_p(r['ret'])}"
             + (f" ({'+' if r['usd'] >= 0 else '−'}${abs(r['usd']):,.0f})" if r["usd"] is not None else "")
             + " · money added or taken out not counted", "", "Real vs backtest this week:"]
    for s in r["strategies"]:
        gap = f" · gap {s['gap'] * 100:+.1f} pts".replace("-", "−") if s["gap"] is not None else ""
        lines.append(f"• {s['name']}: {_p(s['real'])} vs {_p(s['backtest'])}{gap}")
    wc, sc = r["week_costs"], r["since_costs"]
    lines += ["", f"Trading this week: {wc['fills']} fill(s), ${wc['traded']:,.0f} traded"
              + (f" · fees ${wc['fees']:,.2f} ({_p(wc['fee_pct'], 3, False)})" if wc["fills"] else "")
              + (f" · vs the open {'+' if wc['cost'] >= 0 else '−'}${abs(wc['cost']):,.2f} ({_p(wc['cost_pct'], 2)})"
                 if wc["fills"] and wc["cost_pct"] is not None else "")]
    w = r.get("worst")
    if w and w["cost_pct"] and w["cost_pct"] > 0.002:
        lines.append(f"Costliest fill: {w['name']} {w['side'].lower()} {brokers.qty_text(round(w['qty'], 4))} {w['symbol']} "
                     f"@ ${w['avg']:,.2f} vs open ${w['open']:,.2f} ({_p(w['cost_pct'], 2)})")
    if sc["fills"]:
        lines.append(f"Since {r['since_from']}: fees ${sc['fees']:,.2f} · vs the open "
                     f"{'+' if sc['cost'] >= 0 else '−'}${abs(sc['cost']):,.2f} ({_p(sc['cost_pct'], 2)}) on ${sc['traded']:,.0f} traded")
    lines.append("(+ = cost: paid above the open on buys, below it on sells. The daily backtests fill at the open.)")
    return "\n".join(lines)


def stored(mode) -> list:
    return db.get_state(f"weekly:{mode}") or []


def send(mode: str, now: datetime | None = None, line: bool = True) -> dict:
    r = build(mode, now)
    r["text"] = text(r)
    keep = [x for x in stored(mode) if x.get("week") != r["week"]]
    db.set_state(f"weekly:{mode}", ([{k: v for k, v in r.items() if k != "fills"} | {"fills": r["fills"][-60:]}] + keep)[:KEEP])
    if line:
        notify.send("weekly", r["text"])
    return r


def modes_to_report(settings=None) -> list:
    on = brokers.enabled_modes(settings)
    real = [m for m in on if m != "paper"]
    return real or on


def job(now: datetime):
    """Saturday from 09:00 Bangkok (after Friday's US close), once per week, for the modes that are on."""
    for m in modes_to_report():
        if any(abs(ledger.value(m, s.id)["value"]) > 0.5 for s in S.all_instances()):
            try:
                send(m, now)
            except Exception as e:
                log.exception("weekly report %s", m)
                db.add_event("error", "server", "Weekly report failed", str(e)[:300], mode=m)
