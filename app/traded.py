"""Dashboard → Traded: what the bot bought and sold in the last 3 US sessions, one line per strategy.

A session is a New York trading day whose open has passed. Fills are grouped by the New York date they were booked
(Webull fills and fills settled inside the bot). Each strategy line combines its lots per side and symbol; the tag says
why (the signal's new state, a top-up, a move, a stop). A strategy whose buys that day filled for less than 90% of what
its signal's lots asked for (top-ups the same day included) gets a note."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import db, markethours as mh
from . import strategies as S
from .config import DISPLAY_TZ

TZ = ZoneInfo(DISPLAY_TZ)
SESSIONS = 3
EXIT_STATES = {"out", "flat", "cash", "off", "exit", "none"}


def sessions(now: datetime, n: int = SESSIONS) -> list[date]:
    """The last n New York trading days whose open has passed (today included once the market has opened)."""
    d = now.astimezone(mh.NY).date()
    out = []
    for _ in range(30):
        b = mh.session_bounds(d)
        if b and b[0] <= now:
            out.append(d)
            if len(out) == n:
                break
        d -= timedelta(days=1)
    return out


def _why(reason: str | None, to_state: str | None, side: str) -> str:
    if reason == "signal":
        st = (to_state or "").lower()
        if st in EXIT_STATES:
            return "signal · exit"
        return f"signal · {st}" if st else "signal"
    if reason == "rebalance":
        return "top-up" if side == "BUY" else "resize"
    return {"move": "move", "stop": "stop & sell", "withdraw": "withdraw", "money": "new money", "invest": "new money"}.get(
        reason or "", reason or "")


def build(mode: str, now: datetime) -> dict:
    days = sessions(now)
    if not days:
        return {"days": []}
    t0 = int(mh.session_bounds(days[-1])[0].timestamp()) - 6 * 3600
    rows = db.rows(
        "SELECT o.id, o.strategy, o.symbol, o.side, o.applied_qty q, o.applied_value v, COALESCE(o.fee,0) fee, o.cross_with, "
        "COALESCE(o.updated_at, o.submitted_at) t, p.reason, s.to_state "
        "FROM orders o LEFT JOIN plans p ON p.id=o.plan_id LEFT JOIN signals s ON s.id=p.signal_id "
        "WHERE o.mode=? AND o.applied_qty>0 AND COALESCE(o.updated_at, o.submitted_at)>=? ORDER BY t", (mode, t0))
    planned = db.rows(
        "SELECT o.strategy, o.symbol, o.scheduled_at t, o.qty, o.plan_qty, o.limit_price "
        "FROM orders o JOIN plans p ON p.id=o.plan_id WHERE o.mode=? AND o.side='BUY' AND p.reason='signal' "
        "AND COALESCE(o.retry,0)=0 AND o.scheduled_at>=?", (mode, t0))
    by_day = {d: [] for d in days}
    for r in rows:
        d = datetime.fromtimestamp(r["t"], mh.NY).date()
        if d in by_day:
            by_day[d].append(r)
    out = []
    last_trade = next((d for d in days if by_day[d]), None)
    for d in days:
        fl = by_day[d]
        strat: dict = {}
        for r in fl:
            st = strat.setdefault(r["strategy"], {"legs": {}, "why": [], "value": 0.0})
            leg = st["legs"].setdefault((r["side"], r["symbol"]), {"side": r["side"], "symbol": r["symbol"], "qty": 0.0, "value": 0.0,
                                                                   "inside": 0.0})
            leg["qty"] += r["q"]
            leg["value"] += r["v"]
            if r["cross_with"]:
                leg["inside"] += r["q"]
            st["value"] += r["v"]
            w = _why(r["reason"], r["to_state"], r["side"])
            if w and w not in st["why"]:
                st["why"].append(w)
        # buys that filled for less than they asked
        px = {}
        for r in fl:
            if r["side"] == "BUY" and r["q"]:
                a = px.setdefault(r["symbol"], [0.0, 0.0])
                a[0] += r["v"]
                a[1] += r["q"]
        short = {}
        for p in planned:
            if datetime.fromtimestamp(p["t"] or 0, mh.NY).date() != d:
                continue
            price = p["limit_price"] or (px[p["symbol"]][0] / px[p["symbol"]][1] if p["symbol"] in px else None)
            if price:
                short.setdefault(p["strategy"], [0.0, 0.0])[0] += (p["plan_qty"] or p["qty"] or 0) * price
        for sid, a in short.items():
            a[1] = sum(r["v"] for r in fl if r["strategy"] == sid and r["side"] == "BUY")
        lines = []
        for sid, st in strat.items():
            s = S.get(sid)
            legs = sorted(st["legs"].values(), key=lambda x: -x["value"])
            for g in legs:
                g["avg"] = g["value"] / g["qty"] if g["qty"] else None
                g["qty"] = round(g["qty"], 4)
                g["value"] = round(g["value"], 2)
                g["inside"] = round(g["inside"], 4)
            lines.append({"id": sid, "name": s.name if s else sid, "color": s.color if s else None, "value": round(st["value"], 2),
                          "legs": legs, "why": st["why"]})
        lines.sort(key=lambda x: -x["value"])
        notes = []
        for sid, (want, got) in short.items():
            if want > 50 and got < 0.9 * want:
                s = S.get(sid)
                notes.append({"id": sid, "name": s.name if s else sid, "pct": round(100 * got / want)})
        notes.sort(key=lambda x: x["pct"])
        ts = [r["t"] for r in fl]
        out.append({"date": d.isoformat(), "label": d.strftime("%a %-d %b"), "fills": len(fl),
                    "inside": sum(1 for r in fl if r["cross_with"]),
                    "bought": round(sum(r["v"] for r in fl if r["side"] == "BUY"), 2),
                    "sold": round(sum(r["v"] for r in fl if r["side"] == "SELL"), 2),
                    "fees": round(sum(r["fee"] for r in fl), 2),
                    "from": datetime.fromtimestamp(min(ts), TZ).strftime("%H:%M") if ts else None,
                    "to": datetime.fromtimestamp(max(ts), TZ).strftime("%H:%M") if ts else None,
                    "last": d == last_trade, "strategies": lines, "short": notes})
    return {"days": out, "at": int(time.time())}
