"""What each strategy will buy or sell at the next US open (or is trading now).

After the US close a strategy that changes its target gets a plan whose lots wait for the next open. Sells are exact
(shares are fixed when the plan is made). Buys are sized when each lot is sent, so the shares shown here are an estimate
from the latest price: target weight × the strategy's money − what it already holds, the same sum the plan uses.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import db, execution, ledger, marketdata as md, notify
from . import brokers
from . import strategies as S

NY = ZoneInfo("America/New_York")


def _why(sid, created):
    r = db.one("SELECT text, to_state, t FROM signals WHERE strategy=? AND t<=? ORDER BY t DESC LIMIT 1", (sid, created + 60))
    return (r["text"] or r["to_state"]) if r else None


def next_orders(mode, sid=None) -> dict:
    plans = [p for p in execution.plans_view(mode, limit=100, sid=sid) if p["status"] == "active"]
    out, tot_buy, tot_sell, by_sym, warn = [], 0.0, 0.0, {}, []
    blocked = execution.blocked_symbols(mode)
    for p in sorted(plans, key=lambda x: (x["start_at"] or 0, x["name"])):
        s = S.get(p["strategy"])
        L = ledger.get(mode, p["strategy"])
        left = [o for o in p["orders"] if o["status"] == "scheduled"]
        syms = {o["symbol"] for o in p["orders"]} | set(L["holdings"]) | set(p["target"])
        px = md.prices(syms) if syms else {}
        E = ledger.tradable_cash(L) + sum(q * (px.get(k) or 0) for k, q in L["holdings"].items())
        sells, buys = {}, {}
        for o in p["orders"]:
            if o["side"] == "SELL":
                x = sells.setdefault(o["symbol"], {"plan": 0, "filled": 0})
                if (o["retry"] or 0) == 0:
                    x["plan"] += o["plan_qty"] or 0
                x["filled"] += o["filled_qty"] or 0
            else:
                x = buys.setdefault(o["symbol"], {"filled": 0, "value": 0.0})
                x["filled"] += o["filled_qty"] or 0
                x["value"] += (o["filled_qty"] or 0) * (o["avg_price"] or 0)
        items = []
        for sym, x in sorted(sells.items()):
            pr = px.get(sym)
            q = max(0, x["plan"] - x["filled"])
            items.append({"side": "SELL", "symbol": sym, "qty": x["plan"], "left": q, "filled": x["filled"], "price": pr,
                          "value": round(x["plan"] * pr, 2) if pr else None, "exact": True})
            if pr:
                tot_sell += q * pr
                by_sym[sym] = by_sym.get(sym, 0.0) - q * pr
        for sym, x in sorted(buys.items(), key=lambda kv: -(p["target"].get(kv[0], 0))):
            pr = px.get(sym)
            want = p["target"].get(sym, 0) * E - L["holdings"].get(sym, 0) * (pr or 0)
            est = max(0, math.floor(want / pr)) if pr else None
            items.append({"side": "BUY", "symbol": sym, "qty": est, "left": est, "filled": x["filled"], "price": pr,
                          "value": round(max(want, 0), 2) if pr else None, "exact": False, "blocked": sym in blocked})
            if pr and want > 0:
                tot_buy += want
                by_sym[sym] = by_sym.get(sym, 0.0) + want
            if sym in blocked:
                warn.append(f"Webull refuses {sym} ({p['name']}): its buy waits until you fix it (Orders → Try again).")
        if not items:
            continue
        out.append({"plan": p["id"], "strategy": p["strategy"], "name": p["name"], "color": p["color"], "reason": p["reason"],
                    "state": p["state"], "start_at": p["start_at"], "window": p["window"], "lots": p["lots"], "interval": p["interval_min"],
                    "created_at": p["created_at"], "why": _why(p["strategy"], p["created_at"]) if p["reason"] in ("signal", "rebalance") else p["note"],
                    "after": {k: round(v, 4) for k, v in (p["target"] or {}).items() if v > 0.0005}, "items": items,
                    "cash": round(L["cash"], 2), "value": round(E, 2), "family": s.family if s else None, "rounds_left": len({o["lot"] for o in left})})
    nxt = min((r["start_at"] for r in out if r["state"] == "queued" and r["start_at"]), default=None)
    return {"mode": mode, "rows": out, "next_start": nxt, "buys": round(tot_buy, 2), "sells": round(tot_sell, 2),
            "by_symbol": {k: round(v, 2) for k, v in sorted(by_sym.items()) if abs(v) >= 1}, "warnings": warn,
            "shared": [k for k in by_sym if sum(1 for r in out if any(i["symbol"] == k for i in r["items"])) > 1],
            "generated_at": int(time.time())}


def line_text(mode) -> str | None:
    d = next_orders(mode)
    rows = [r for r in d["rows"] if r["state"] == "queued"]
    if not rows:
        return None
    start = datetime.fromtimestamp(d["next_start"], ZoneInfo("Asia/Bangkok")).strftime("%a %d %b %H:%M") if d["next_start"] else "the next open"
    lines = [f"{brokers.MODE_LABEL[mode]} · orders for the next US open ({start} Bangkok):"]
    for r in rows:
        parts = []
        for i in r["items"]:
            if i["side"] == "SELL":
                parts.append(f"sell {i['qty']} {i['symbol']}" + (f" ≈${i['value']:,.0f}" if i["value"] else ""))
            else:
                parts.append(f"buy ≈{i['qty']} {i['symbol']}" + (f" ≈${i['value']:,.0f}" if i["value"] else ""))
        lines.append(f"• {r['name']}: " + ", ".join(parts) + (f" — {r['why']}" if r.get("why") else ""))
    lines.append(f"Buys ≈${d['buys']:,.0f} · sells ≈${d['sells']:,.0f}. Buy shares are estimated from the last price. "
                 "Cancel or start a plan on the Orders page.")
    return "\n".join(lines)


def send_preview(now=None):
    """After the US close: one LINE message per trading mode with the orders waiting for the next open."""
    for mode in brokers.enabled_modes():
        try:
            txt = line_text(mode)
        except Exception as e:
            db.add_event("warn", "orders", "Next-open preview failed", str(e)[:300], mode=mode)
            continue
        if txt:
            notify.send("preview", txt, title="Next US open")
