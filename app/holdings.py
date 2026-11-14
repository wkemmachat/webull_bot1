"""What each strategy holds now (Dashboard "What your money is in" → By strategy, and Portfolio → Holdings by strategy).

For every strategy: its cash and its shares (symbol, shares, value), today's target, and its cash split by reason:
  waits     money added with "wait for the next buy signal" (stays cash until the strategy's next BUY)
  orders    cash set aside for buy orders already planned for the next open or working at Webull now
  rule      the rest: cash because the strategy's rule says so (out of the market, a cash share, a small leftover)
Then the totals per symbol, the bot's money no strategy has yet, and "Not the bot's": the shares and cash in your Webull
account that the bot does not manage (your own shares, cash not given to the bot, HKD cash). The check at the bottom
compares the bot's shares with Webull's per symbol and adds everything up to the account total.
"""
from __future__ import annotations

import json

from . import db, execution, ledger, marketdata as md
from . import strategies as S

QTY_TOL = 1e-6
SYM_COLOR = {"GLD": "#D4A017", "UGL": "#E8B931", "IAU": "#C99A10", "SLV": "#9AA5B1", "AGQ": "#7D8A97", "USD": "#2E86DE",
             "SMH": "#5DA9F0", "ROM": "#20C997", "IYW": "#63D9B5", "QLD": "#5B8DEF", "QQQ": "#8FB0F5", "TQQQ": "#3E6FD8",
             "SSO": "#34508A", "RXL": "#E07A9B", "DDM": "#8E6CC8", "BIL": "#8FA98F", "SGOV": "#8FA98F"}
CASH_COLOR = "#B8C4BA"


def color(sym: str) -> str:
    if sym in SYM_COLOR:
        return SYM_COLOR[sym]
    from . import exposure
    return exposure.GROUPS.get(exposure.classify(sym, {}, set())[0], exposure.GROUPS["other"])[2]


def _states() -> dict:
    out = {}
    for r in db.rows("SELECT strategy, state, label, target FROM strategy_state"):
        try:
            t = json.loads(r["target"] or "{}")
        except ValueError:
            t = {}
        out[r["strategy"]] = {"state": r["state"], "label": r["label"], "target": {k: float(w) for k, w in t.items() if w}}
    return out


def _orders_cash(mode, sid, prices) -> float:
    """Cash for buy lots planned for the next open or working at Webull now (limit price, else today's price)."""
    tot = 0.0
    for o in db.rows("SELECT symbol, qty, plan_qty, applied_qty, limit_price FROM orders WHERE mode=? AND strategy=? AND side='BUY' "
                     "AND status IN ('scheduled','sending','submitted','unknown') AND COALESCE(cross_with,'')=''", (mode, sid)):
        q = (o["qty"] if o["qty"] is not None else o["plan_qty"] or 0) - (o["applied_qty"] or 0)
        px = o["limit_price"] or prices.get(o["symbol"]) or 0
        tot += max(0.0, q) * px
    return tot


def build(mode: str, acct: dict | None = None, account_error: str | None = None) -> dict:
    states = _states()
    strats = S.all_instances()
    rows, totals = [], {}
    for s in strats:
        v = ledger.value(mode, s.id)
        L = ledger.get(mode, s.id)
        cash = float(v["cash"] or 0)
        pos = {k: {"qty": p["qty"], "value": round(p["value"] or 0, 2), "price": p["price"]}
               for k, p in (v["positions"] or {}).items() if (p.get("qty") or 0) > QTY_TOL}
        total = cash + sum(p["value"] for p in pos.values())
        empty = abs(total) < 0.5 and not pos
        waits = ledger.waiting_cash(L) if (L["hold_cash"] and execution.waiting_for_buy(mode, s, L)) else 0.0
        orders = 0.0 if empty else min(max(cash - waits, 0.0), _orders_cash(mode, s.id, {k: p["price"] for k, p in pos.items()}))
        st = states.get(s.id) or {}
        rows.append({"id": s.id, "name": s.name, "color": s.color, "control": (s.row or {}).get("control"),
                     "state": st.get("state"), "label": st.get("label"), "target": st.get("target") or {},
                     "cash": round(cash, 2), "waits": round(waits, 2), "orders": round(orders, 2),
                     "rule_cash": round(max(cash - waits - orders, 0.0), 2), "positions": pos, "total": round(total, 2),
                     "empty": empty})
        for k, p in pos.items():
            t = totals.setdefault(k, {"symbol": k, "color": color(k), "qty": 0.0, "value": 0.0, "strategies": 0})
            t["qty"] += p["qty"]
            t["value"] += p["value"]
            t["strategies"] += 1
    rows.sort(key=lambda r: (r["empty"], -r["total"]))
    live = [r for r in rows if not r["empty"]]
    bot_total = sum(r["total"] for r in live)
    bot_cash = sum(r["cash"] for r in live)
    syms = sorted(totals.values(), key=lambda t: -t["value"])
    for t in syms:
        t["value"] = round(t["value"], 2)
        t["pct"] = t["value"] / bot_total if bot_total > 0.5 else None
    unassigned = ledger.pool_cash(mode)

    # Webull account: the bot's shares vs the account's, and what is not the bot's
    check, own, own_cash, hkd, acct_total = [], [], None, None, None
    if acct:
        apos = acct.get("positions") or {}
        for t in syms:
            have = float((apos.get(t["symbol"]) or {}).get("qty") or 0)
            check.append({"symbol": t["symbol"], "bot": t["qty"], "account": have,
                          "status": "match" if abs(have - t["qty"]) < QTY_TOL else ("extra" if have > t["qty"] else "missing")})
        for k, p in sorted(apos.items(), key=lambda kv: -(kv[1].get("value") or 0)):
            q = float(p.get("qty") or 0) - (totals[k]["qty"] if k in totals else 0.0)
            if q <= QTY_TOL:
                continue
            last = p.get("last")
            val = q * last if last is not None else (p.get("value") or 0.0)
            cost = p.get("cost")
            own.append({"symbol": k, "color": color(k), "qty": q, "price": last, "value": round(val or 0.0, 2), "cost": cost,
                        "pnl": round((last - cost) * q, 2) if (last is not None and cost) else None,
                        "pnl_pct": (last / cost - 1) if (last is not None and cost) else None,
                        "part": k in totals})                          # Webull holds more of a bot symbol than the bot owns
        own_cash = ledger.outside_cash(mode, acct.get("cash"))
        hkd = acct.get("cash_hkd")
        acct_total = acct.get("total")
    own_total = (sum(o["value"] for o in own) + (own_cash or 0.0)) if acct else None
    summed = bot_total + unassigned + (own_total or 0.0)
    return {"mode": mode, "rows": live, "empty": [{"id": r["id"], "name": r["name"], "color": r["color"], "control": r["control"],
                                                    "label": r["label"]} for r in rows if r["empty"]],
            "symbols": syms, "cash_color": CASH_COLOR, "total": round(bot_total, 2), "cash": round(bot_cash, 2),
            "waits": round(sum(r["waits"] for r in live), 2), "orders": round(sum(r["orders"] for r in live), 2),
            "unassigned": round(unassigned, 2),
            "not_bot": None if not acct else {"items": own, "cash": round(own_cash, 2) if own_cash is not None else None,
                                              "hkd": hkd, "total": round(own_total, 2)},
            "account": None if not acct else {"total": acct_total, "cash": acct.get("cash"), "check": check,
                                              "adds_up": acct_total is not None and abs(summed - acct_total) < 1.0,
                                              "gap": round(acct_total - summed, 2) if acct_total is not None else None},
            "account_error": account_error, "checked_at": (acct or {}).get("_at")}


CSV_COLS = ["strategy_id", "strategy", "state", "symbol", "shares", "price_usd", "value_usd", "share_of_strategy", "cash_kind"]


def csv_rows(d: dict):
    for r in d["rows"]:
        for k, p in sorted(r["positions"].items(), key=lambda kv: -kv[1]["value"]):
            yield [r["id"], r["name"], r["label"] or r["state"] or "", k, round(p["qty"], 6), round(p["price"] or 0, 4), p["value"],
                   round(p["value"] / r["total"], 4) if r["total"] else "", ""]
        for kind, amt in (("waits for a buy signal", r["waits"]), ("for planned orders", r["orders"]), ("by the rule", r["rule_cash"])):
            if amt >= 0.005:
                yield [r["id"], r["name"], r["label"] or r["state"] or "", "CASH", "", "", amt,
                       round(amt / r["total"], 4) if r["total"] else "", kind]
    if d["unassigned"] >= 0.005:
        yield ["", "Bot unassigned", "", "CASH", "", "", d["unassigned"], "", "not given to a strategy"]
    nb = d.get("not_bot")
    if nb:
        for o in nb["items"]:
            yield ["", "Not the bot's", "", o["symbol"], round(o["qty"], 6), o["price"] or "", o["value"], "", ""]
        if nb["cash"] is not None:
            yield ["", "Not the bot's", "", "CASH", "", "", nb["cash"], "", "not given to the bot"]
        if nb.get("hkd"):
            yield ["", "Not the bot's", "", "CASH HKD", "", "", "", "", f"HK${nb['hkd']:,.2f}"]
