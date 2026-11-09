"""Order history: every order the bot has sent (Orders page and each strategy page), with what is needed to check it against
Webull later: the bot's order no., the client order id the bot gave Webull, Webull's order no., limit, qty, fills, fee and why
it was sent.

Shown: orders that were sent (or settled inside the bot between two strategies). Not shown: lots still waiting to be sent
("scheduled": see the plan cards and Next orders) and lots skipped before sending (too small, or the target changed).

result filter
  filled      some or all shares filled (filled, or "partial" = part filled, the rest cancelled)
  none        nothing filled and the order is finished (cancelled, refused / failed)
  working     sent and waiting at Webull (sending, submitted, unknown)

check(oid) asks Webull for one order and compares status, filled shares, average price and fee with the bot's record.
"""
from __future__ import annotations

import time

from . import brokers, db
from . import strategies as S

SHOWN = ("sending", "submitted", "unknown", "filled", "partial", "cancelled", "failed")
WORKING = ("sending", "submitted", "unknown")
QTY_TOL = 1e-6
PRICE_TOL = 0.005          # $ per share
FEE_TOL = 0.011            # $ (Webull rounds fees to the cent)

_RETRIED = ("EXISTS(SELECT 1 FROM orders r WHERE r.plan_id=o.plan_id AND r.step=o.step AND r.symbol=o.symbol "
            "AND r.side=o.side AND r.retry=o.retry+1)")


def _where(mode, sid=None, side=None, days=None, result=None):
    q, a = [f"o.mode=?", f"o.status IN ({','.join('?' * len(SHOWN))})"], [mode, *SHOWN]
    if sid:
        q.append("o.strategy=?")
        a.append(sid)
    if side in ("BUY", "SELL"):
        q.append("o.side=?")
        a.append(side)
    if days:
        q.append("COALESCE(o.submitted_at, o.updated_at)>=?")
        a.append(int(time.time() - float(days) * 86400))
    if result == "filled":
        q.append("COALESCE(o.filled_qty,0)>0")
    elif result == "none":
        q.append(f"COALESCE(o.filled_qty,0)<=0 AND o.status NOT IN ({','.join('?' * len(WORKING))})")
        a.extend(WORKING)
    elif result == "working":
        q.append(f"o.status IN ({','.join('?' * len(WORKING))})")
        a.extend(WORKING)
    return " AND ".join(q), a


def _result(o) -> str:
    if o["status"] in WORKING:
        return "working"
    if o["cross_with"]:
        return "inside"
    f, q = o["filled_qty"] or 0, o["qty"] or o["plan_qty"] or 0
    if f > 0:
        return "filled" if o["status"] == "filled" or f >= q - QTY_TOL else "part"
    return "refused" if o["status"] == "failed" else "cancelled"


def stats(mode, sid=None, side=None, days=None) -> dict:
    w, a = _where(mode, sid, side, days)
    r = db.one(f"SELECT COUNT(*) n, SUM(o.cross_with IS NOT NULL AND o.cross_with<>'') inside, "
               f"SUM(COALESCE(o.filled_qty,0)>0) filled, "
               f"SUM(o.status IN ({','.join('?' * len(WORKING))})) working, "
               f"SUM({_RETRIED}) retried, "
               f"SUM(CASE WHEN o.side='BUY' THEN COALESCE(o.filled_qty,0)*COALESCE(o.avg_price,0) ELSE 0 END) bought, "
               f"SUM(CASE WHEN o.side='SELL' THEN COALESCE(o.filled_qty,0)*COALESCE(o.avg_price,0) ELSE 0 END) sold, "
               f"SUM(COALESCE(o.fee,0)) fees FROM orders o WHERE {w}", (*WORKING, *a))
    n, filled, working = r["n"] or 0, r["filled"] or 0, r["working"] or 0
    return {"orders": n, "inside": r["inside"] or 0, "webull": n - (r["inside"] or 0), "filled": filled, "working": working,
            "not_filled": n - filled - working, "retried": r["retried"] or 0, "bought": round(r["bought"] or 0, 2),
            "sold": round(r["sold"] or 0, 2), "fees": round(r["fees"] or 0, 2)}


def history(mode, sid=None, side=None, days=None, result=None, limit=50, offset=0) -> dict:
    w, a = _where(mode, sid, side, days, result)
    total = db.one(f"SELECT COUNT(*) n FROM orders o WHERE {w}", tuple(a))["n"]
    rows = db.rows(f"SELECT o.id, o.plan_id, o.strategy, o.step, o.lot, o.lots, o.symbol, o.side, o.qty, o.plan_qty, o.limit_price, "
                   f"o.session, o.status, o.client_order_id, o.broker_order_id, o.submitted_at, o.updated_at, o.filled_qty, "
                   f"o.avg_price, o.fee, o.error, o.retry, o.cross_with, p.reason, p.note, {_RETRIED} AS retried "
                   f"FROM orders o LEFT JOIN plans p ON p.id=o.plan_id WHERE {w} "
                   f"ORDER BY COALESCE(o.submitted_at, o.updated_at) DESC, o.id DESC LIMIT ? OFFSET ?",
                   (*a, int(limit), int(offset)))
    names = {r["id"]: r for r in S.rows(include_archived=True)}
    for r in rows:
        x = names.get(r["strategy"]) or {}
        r["name"], r["color"] = x.get("name", r["strategy"]), x.get("color")
        r["t"] = r["submitted_at"] or r["updated_at"]
        r["value"] = round((r["filled_qty"] or 0) * (r["avg_price"] or 0), 2)
        r["result"] = _result(r)
        r["retried"] = bool(r["retried"])
        if r["cross_with"]:
            r["cross_name"] = (names.get(r["cross_with"]) or {}).get("name", r["cross_with"])
    return {"rows": rows, "total": total, "limit": int(limit), "offset": int(offset),
            "stats": stats(mode, sid, side, days)}


CSV_COLS = ["bot_order_id", "plan_id", "sent_bangkok", "last_update_bangkok", "strategy_id", "strategy", "symbol", "side", "lot",
            "retry", "order_type", "limit_price_usd", "session", "qty", "filled_qty", "avg_fill_price_usd", "value_usd", "fee_usd",
            "status", "result", "webull_order_no", "client_order_id", "inside_with", "plan_reason", "note_or_error"]


def csv_rows(mode, sid=None, side=None, days=None, result=None):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .config import DISPLAY_TZ
    TZ = ZoneInfo(DISPLAY_TZ)
    ts = lambda t: datetime.fromtimestamp(t, TZ).strftime("%Y-%m-%d %H:%M:%S") if t else ""
    d = history(mode, sid, side, days, result, limit=1_000_000)
    for r in d["rows"]:
        yield [r["id"], r["plan_id"], ts(r["submitted_at"]), ts(r["updated_at"]), r["strategy"], r["name"], r["symbol"], r["side"],
               f"{r['lot']}/{r['lots']}", r["retry"] or 0, "inside" if r["cross_with"] else ("limit" if r["limit_price"] else "market"),
               r["limit_price"] or "", r["session"] or "", r["qty"] if r["qty"] is not None else r["plan_qty"], r["filled_qty"] or 0,
               r["avg_price"] or "", r["value"], round(r["fee"] or 0, 4), r["status"], r["result"], r["broker_order_id"] or "",
               r["client_order_id"] or "", r["cross_name"] if r["cross_with"] else "", r["reason"] or "", r["error"] or ""]


def check(oid: int) -> dict:
    """Ask Webull for one order and compare it with the bot's record. Read-only: it never changes the books."""
    o = db.one("SELECT * FROM orders WHERE id=?", (int(oid),))
    if not o:
        raise ValueError("No such order")
    bot = {"status": o["status"], "filled_qty": o["filled_qty"] or 0, "avg_price": o["avg_price"], "fee": round(o["fee"] or 0, 4)}
    if o.get("cross_with"):
        return {"id": o["id"], "ok": True, "inside": True, "bot": bot, "diffs": [],
                "note": "Settled inside the bot with another strategy: there is no Webull order to check."}
    if not o.get("client_order_id"):
        return {"id": o["id"], "ok": None, "bot": bot, "diffs": [], "note": "Never reached Webull (no order id): nothing to check."}
    try:
        wb = brokers.get(o["mode"]).order(o["client_order_id"])
    except brokers.BrokerError as e:
        return {"id": o["id"], "ok": None, "bot": bot, "diffs": [], "error": str(e)[:300]}
    w_status = str(wb.get("status") or "").upper()
    diffs = []
    wf, bf = float(wb.get("filled_qty") or 0), float(bot["filled_qty"])
    if abs(wf - bf) > QTY_TOL:
        diffs.append({"field": "filled shares", "bot": bf, "webull": wf})
    if wf > 0 and wb.get("avg_price") is not None and bot["avg_price"] is not None \
            and abs(float(wb["avg_price"]) - float(bot["avg_price"])) > PRICE_TOL:
        diffs.append({"field": "average price", "bot": bot["avg_price"], "webull": wb["avg_price"]})
    if abs(float(wb.get("fee") or 0) - float(bot["fee"])) > FEE_TOL:
        diffs.append({"field": "fee", "bot": bot["fee"], "webull": round(float(wb.get("fee") or 0), 4)})
    open_bot, open_wb = o["status"] in WORKING, w_status in ("PENDING", "SUBMITTED", "PARTIAL_FILLED", "WORKING")
    if open_bot != open_wb:
        diffs.append({"field": "status", "bot": o["status"], "webull": w_status})
    return {"id": o["id"], "ok": not diffs, "bot": bot, "diffs": diffs,
            "webull": {"status": w_status, "filled_qty": wf, "avg_price": wb.get("avg_price"), "fee": round(float(wb.get("fee") or 0), 4)},
            "checked_at": int(time.time())}
