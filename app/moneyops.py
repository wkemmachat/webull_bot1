"""Money between Webull, the bot and its strategies.

  Webull account ── Allocate to bot ──▶ Bot unassigned ── Add / Split ──▶ Strategy 1, 2, 3 …
                 ◀── Return to Webull ──               ◀── Withdraw ──

To bot     part of the account's free cash is given to the bot (bot unassigned). Cash you do not give the bot
           is never used by it.
Add/Split  bot unassigned → one strategy, or several (equal split or your own amounts). "Now" follows the
           current signal; "wait" keeps it in cash until the strategy's next BUY signal.
Withdraw   the strategy's free cash first; if that is not enough, its holdings are sold evenly with a split
           plan and the cash is freed when the plan finishes. It goes back to bot unassigned.
Move       a withdraw from one strategy that is then added to another.
To Webull  bot unassigned → the account; the bot stops using it (to take it out of Webull, withdraw in the app).
"""
from __future__ import annotations

import math

from . import brokers, db, execution, ledger, marketdata as md, notify
from . import strategies as S


def account_cash(mode: str):
    b = brokers.get(mode)
    try:
        return b.account().get("cash")
    except Exception as e:
        raise ValueError(f"Cannot read the {brokers.MODE_LABEL[mode]} account: {e}")


def _strat(sid):
    s = S.get(sid)
    if not s:
        raise ValueError("Unknown strategy")
    return s


def default_invest() -> str:
    """'now' or 'wait' (= keep cash until the next BUY signal), from Execution → New money."""
    return "wait" if db.get_setting("new_money_start") == "buy" else "now"


def _invest(v):
    v = v or default_invest()
    if v not in ("now", "wait"):
        raise ValueError("invest must be 'now' or 'wait'")
    return v


WAIT_TXT = "kept in cash until the next buy signal"


def to_bot(mode, amount, note=""):
    amount = round(float(amount), 2)
    cash = account_cash(mode)
    floor = float(db.get_setting(f"protect_floor_{mode}") or 0)
    if floor > 0 and cash is not None and cash - ledger.bot_cash(mode) - amount < floor - 0.005:
        raise ValueError(f"That would give the bot money below your protected floor ${floor:,.2f}. Lower the floor first "
                         "(Money → Protected cash floor).")
    mid = ledger.fund_in(mode, amount, cash, note)
    db.add_event("info", "money", f"Allocated ${amount:,.2f} to the bot", f"{brokers.MODE_LABEL[mode]} · bot unassigned now "
                 f"${ledger.pool_cash(mode):,.2f}", mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Allocated ${amount:,.2f} from Webull to the bot. "
                f"Bot unassigned: ${ledger.pool_cash(mode):,.2f}.")
    return {"id": mid, "pool": ledger.pool_cash(mode)}


def to_webull(mode, amount, note=""):
    amount = round(float(amount), 2)
    mid = ledger.fund_out(mode, amount, note)
    db.add_event("info", "money", f"Returned ${amount:,.2f} to Webull", f"{brokers.MODE_LABEL[mode]} · the bot no longer uses it", mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Returned ${amount:,.2f} from the bot to Webull (the bot will not use it).")
    return {"id": mid, "pool": ledger.pool_cash(mode)}


def split(mode, allocations: dict, invest=None, note=""):
    """Bot unassigned → several strategies at once, e.g. {"gold_sta": 10, "qld_regime": 10}."""
    invest = _invest(invest)
    alloc = {}
    for sid, amt in (allocations or {}).items():
        a = round(float(amt or 0), 2)
        if a < 0:
            raise ValueError("Amounts cannot be negative")
        if a > 0:
            _strat(sid)
            alloc[sid] = a
    if not alloc:
        raise ValueError("Enter an amount for at least one strategy")
    tot = round(sum(alloc.values()), 2)
    have = ledger.pool_cash(mode)
    if tot > have + 0.005:
        raise ValueError(f"That is ${tot:,.2f}; bot unassigned has ${have:,.2f}")
    out = {}
    for sid, a in alloc.items():
        out[sid] = add(mode, sid, min(a, ledger.pool_cash(mode)), invest, note or "split")
    warns = [r["warning"] for r in out.values() if r.get("warning")]
    return {"count": len(out), "total": tot, "pool": ledger.pool_cash(mode), **({"warnings": warns} if warns else {})}


def equal_split(total: float, sids: list) -> dict:
    """$total over the strategies in cents, any leftover cent to the first ones."""
    if not sids:
        return {}
    cents = int(round(float(total) * 100))
    base, rem = divmod(cents, len(sids))
    return {sid: (base + (1 if i < rem else 0)) / 100 for i, sid in enumerate(sids)}


def stopped_warning(s) -> str:
    """Money given to a strategy that is stopped (or stopping) is never invested: say so."""
    c = (s.row or {}).get("control")
    if c in ("stopped", "stopping"):
        return (f"{s.name} is {'stopped' if c == 'stopped' else 'set to Stop & sell'}, so it will not buy with this money. "
                "Set it back to Active on its page, or move the money to another strategy.")
    return ""


def add(mode, sid, amount, invest=None, note=""):
    s = _strat(sid)
    invest = _invest(invest)
    amount = round(float(amount), 2)
    mid = ledger.add_money(mode, sid, amount, note=note, invest=invest)
    L = ledger.value(mode, sid)
    warn = stopped_warning(s)
    db.add_event("warn" if warn else "info", "money", f"Added ${amount:,.2f} to {s.name}",
                 f"{brokers.MODE_LABEL[mode]} · capital now ${L['net_in']:,.2f}"
                 + (f" · {WAIT_TXT}" if invest == "wait" else " · invests at the current signal") + (f" · {warn}" if warn else ""),
                 strategy=sid, mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Added ${amount:,.2f} to {s.name}. Capital now ${L['net_in']:,.2f}."
                + (f" It is {WAIT_TXT}." if invest == "wait" else "") + (f"\n⚠ {warn}" if warn else ""), strategy=sid)
    return {"id": mid, "capital": L["net_in"], **({"warning": warn} if warn else {})}


def invest_now(mode, sid):
    """Cash that waits for the next buy signal joins the strategy now: it buys toward today's target (split plan)."""
    s = _strat(sid)
    L = ledger.get(mode, sid)
    amt = ledger.waiting_cash(L)
    if not L.get("hold_cash") or amt <= 0.005:
        raise ValueError(f"{s.name} has no cash waiting for a buy signal")
    warn = stopped_warning(s)
    if warn:
        raise ValueError(warn)
    ledger.end_wait(mode, sid)
    ap = execution.active_plan(mode, sid)
    if ap and ap["reason"] not in ("withdraw", "move"):
        execution.cancel_plan(ap["id"], "waiting cash joins the plan")
    ledger.set_applied_target(mode, sid, None)          # the next check plans with all the money
    db.add_event("info", "money", f"{s.name}: ${amt:,.2f} waiting cash invested now (your choice)",
                 f"{brokers.MODE_LABEL[mode]} · it buys toward today's target from the next check (at the market open if closed)",
                 strategy=sid, mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · {s.name}: the ${amt:,.2f} that waited for a buy signal is invested now "
                "at today's signal.", strategy=sid)
    return {"ok": True, "amount": round(amt, 2)}


def _raise_cash(mode, s, amount, kind, other=None, note="", invest="now"):
    """Free `amount` of cash in strategy s; returns ('done', moved) or ('pending', plan_id)."""
    L = ledger.get(mode, s.id)
    v = ledger.value(mode, s.id)
    if amount > v["value"] + 0.01:
        raise ValueError(f"{s.name} is worth ${v['value']:,.2f}; you asked for ${amount:,.2f}")
    free = max(0.0, L["cash"] - ledger.pending_strategy_buys(mode, s.id))
    if free + 0.01 >= amount:
        mid = ledger.record_money(mode, kind, s.id, amount, other=other, note=note)
        moved = ledger.take_cash(mode, s.id, amount, money_id=mid, to_pool=(kind == "withdraw"))
        return "done", moved, mid
    ap = execution.active_plan(mode, s.id)
    if ap:
        if ap["reason"] in ("withdraw", "move"):
            raise ValueError("A withdrawal for this strategy is already running")
        execution.cancel_plan(ap["id"], f"{kind} requested")
        L = ledger.get(mode, s.id)
        free = max(0.0, L["cash"] - ledger.pending_strategy_buys(mode, s.id))
    short = amount - free
    held_v = sum(p["value"] for p in v["positions"].values())
    frac = min(1.0, short / held_v * 1.02) if held_v > 0 else 1.0
    sells = {sym: (math.ceil(q * frac) if frac < 1 else int(q)) for sym, q in L["holdings"].items()}
    sells = {k: min(int(L["holdings"][k]), q) for k, q in sells.items() if q >= 1}
    mid = ledger.record_money(mode, kind, s.id, amount, other=other, note=note)
    pid = execution.build_plan(mode, s, {}, kind, md.now_utc(), sell_override=sells, buys=False,
                               on_done={"money_id": mid, "amount": amount, "kind": kind, "move_to": other, "invest": invest})
    if not pid:
        db.run("UPDATE money SET status='failed', note=COALESCE(note,'') || ' · could not build a sell plan' WHERE id=?", (mid,))
        raise ValueError("Could not create the sell plan (no price?). Try again in a minute.")
    db.run("UPDATE money SET plan_id=? WHERE id=?", (pid, mid))
    return "pending", pid, mid


def withdraw(mode, sid, amount, note=""):
    s = _strat(sid)
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Enter an amount above 0")
    st, x, mid = _raise_cash(mode, s, amount, "withdraw", note=note)
    if st == "done":
        db.add_event("info", "money", f"Withdrew ${x:,.2f} from {s.name}", "From the strategy's cash; now in bot unassigned", strategy=sid, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · Withdrew ${x:,.2f} from {s.name} (back to bot unassigned).", strategy=sid)
        return {"status": "done", "amount": x}
    db.add_event("info", "money", f"Withdraw ${amount:,.2f} from {s.name}: selling", f"Sell plan #{x}", strategy=sid, mode=mode)
    return {"status": "pending", "plan_id": x}


def move(mode, src, dst, amount, note="", invest=None):
    a, b = _strat(src), _strat(dst)
    invest = _invest(invest)
    if src == dst:
        raise ValueError("Pick two different strategies")
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Enter an amount above 0")
    st, x, mid = _raise_cash(mode, a, amount, "move", other=dst, note=note, invest=invest)
    if st == "done":
        ledger.credit(mode, dst, x, hold=(invest == "wait"))
        db.add_event("info", "money", f"Moved ${x:,.2f}: {a.name} → {b.name}", "", strategy=src, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · Moved ${x:,.2f} from {a.name} to {b.name}.", strategy=src)
        return {"status": "done", "amount": x}
    return {"status": "pending", "plan_id": x}


def after_plan(mode, plan, od):
    """Called when a withdraw/move sell plan finishes."""
    sid = plan["strategy"]
    moved = ledger.take_cash(mode, sid, float(od["amount"]), money_id=od.get("money_id"), to_pool=not od.get("move_to"))
    s = S.get(sid)
    name = s.name if s else sid
    if od.get("move_to"):
        ledger.credit(mode, od["move_to"], moved, hold=(od.get("invest") == "wait"))
        t = S.get(od["move_to"])
        msg = f"Moved ${moved:,.2f} from {name} to {t.name if t else od['move_to']}."
    else:
        msg = f"Withdrew ${moved:,.2f} from {name} (back to bot unassigned)."
    if moved + 0.5 < float(od["amount"]):
        msg += f" Asked for ${float(od['amount']):,.2f}; prices moved during the sale."
    db.add_event("info", "money", msg, f"Plan #{plan['id']}", strategy=sid, mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · {msg}", strategy=sid)


def seed_paper():
    """First start: every strategy gets the paper allowance (default $10,000)."""
    if db.get_state("paper_seeded"):
        return
    st = db.get_settings()
    amt = float(st.get("paper_strategy_cash") or 10000)
    inv = default_invest()
    for r in S.rows():
        if ledger.get("paper", r["id"])["cap_in"] <= 0:
            ledger.credit("paper", r["id"], amt, hold=(inv == "wait"))
            mid = ledger.record_money("paper", "add", r["id"], amt, note="Paper start", invest=inv, status="done")
            db.run("UPDATE money SET done_at=t, done_amount=amount WHERE id=?", (mid,))
    db.set_state("paper_seeded", 1)


def seed_new_paper(sid):
    """A default strategy added by an update gets the paper allowance too, from the paper account's free cash."""
    st = db.get_settings()
    if st.get("mode_paper") != "1":
        return
    amt = float(st.get("paper_strategy_cash") or 10000)
    try:
        free = ledger.outside_cash("paper", account_cash("paper"))
        if free is None or free < amt:
            return
        ledger.fund_in("paper", amt, free + ledger.bot_cash("paper"), note="paper money for a new strategy")
        ledger.add_money("paper", sid, amt, note="Paper start", invest=default_invest())
    except Exception as e:
        db.add_event("warn", "money", "Could not give paper money to the new strategy", str(e), strategy=sid)
