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

import functools
import json
import logging
import math
import threading
import time

from . import brokers, db, execution, ledger, marketdata as md, notify
from . import strategies as S

log = logging.getLogger(__name__)
_MONEY = threading.RLock()


def _one_at_a_time(fn):
    """Money actions never overlap (a move waits off the web app's thread, so a withdraw could otherwise run at the same
    time and both would count the same free cash). A second one is refused at once rather than waiting."""
    @functools.wraps(fn)
    def run(*a, **k):
        if not _MONEY.acquire(blocking=False):
            raise ValueError("Another money action is still running. Try again in a moment.")
        try:
            return fn(*a, **k)
        finally:
            _MONEY.release()
    return run


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


@_one_at_a_time
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


@_one_at_a_time
def to_webull(mode, amount, note=""):
    amount = round(float(amount), 2)
    mid = ledger.fund_out(mode, amount, note)
    db.add_event("info", "money", f"Returned ${amount:,.2f} to Webull", f"{brokers.MODE_LABEL[mode]} · the bot no longer uses it", mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Returned ${amount:,.2f} from the bot to Webull (the bot will not use it).")
    return {"id": mid, "pool": ledger.pool_cash(mode)}


@_one_at_a_time
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


@_one_at_a_time
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


@_one_at_a_time
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


def _raise_cash(mode, s, amount, kind, other=None, note="", invest="now", everything=False):
    """Free `amount` of cash in strategy s; returns ('done', moved) or ('pending', plan_id).
    everything: all of it at today's prices (the dialog's amount was priced a moment earlier and may be a little off)."""
    L = ledger.get(mode, s.id)
    v = ledger.value(mode, s.id)
    if everything:
        amount = round(v["value"], 2)
        if amount <= 0:
            raise ValueError(f"{s.name} holds nothing to take out")
    elif amount > v["value"] + 0.01:
        raise ValueError(f"{s.name} is worth ${v['value']:,.2f} now (prices move); you asked for ${amount:,.2f}. "
                         "Press Everything to take all of it.")
    free = max(0.0, L["cash"] - ledger.pending_strategy_buys(mode, s.id))
    if free + 0.01 >= amount:
        mid = ledger.record_money(mode, kind, s.id, amount, other=other, note=note)
        moved = ledger.take_cash(mode, s.id, free if everything else amount, money_id=mid, to_pool=(kind == "withdraw"))
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
    sells = {}
    for sym, q in L["holdings"].items():
        dp = execution._sell_dp(mode, sym, q)
        if frac >= 1:
            x = execution._down(q, dp)                            # everything: fractions included when allowed
        else:
            m = 10 ** min(dp, execution.FRAC_DP)
            x = min(execution._down(q, dp), math.ceil(q * frac * m - 1e-6) / m)   # a little more than needed, rounded up
        if x > execution.EPS:
            sells[sym] = x
    mid = ledger.record_money(mode, kind, s.id, amount, other=other, note=note)
    pid = execution.build_plan(mode, s, {}, kind, md.now_utc(), sell_override=sells, buys=False,
                               on_done={"money_id": mid, "amount": amount, "kind": kind, "move_to": other, "invest": invest,
                                        "all": bool(everything)})
    if not pid:
        db.run("UPDATE money SET status='failed', note=COALESCE(note,'') || ' · could not build a sell plan' WHERE id=?", (mid,))
        raise ValueError("Could not create the sell plan (no price?). Try again in a minute.")
    db.run("UPDATE money SET plan_id=? WHERE id=?", (pid, mid))
    return "pending", pid, mid


@_one_at_a_time
def withdraw(mode, sid, amount, note="", everything=False):
    s = _strat(sid)
    amount = round(float(amount or 0), 2)
    if amount <= 0 and not everything:
        raise ValueError("Enter an amount above 0")
    st, x, mid = _raise_cash(mode, s, amount, "withdraw", note=note, everything=everything)
    if st == "done":
        db.add_event("info", "money", f"Withdrew ${x:,.2f} from {s.name}", "From the strategy's cash; now in bot unassigned", strategy=sid, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · Withdrew ${x:,.2f} from {s.name} (back to bot unassigned).", strategy=sid)
        return {"status": "done", "amount": x}
    db.add_event("info", "money", f"Withdraw ${amount:,.2f} from {s.name}: selling", f"Sell plan #{x}", strategy=sid, mode=mode)
    return {"status": "pending", "plan_id": x}


@_one_at_a_time
def move(mode, src, dst, amount, note="", invest=None, everything=False):
    a, b = _strat(src), _strat(dst)
    invest = _invest(invest)
    if src == dst:
        raise ValueError("Pick two different strategies")
    amount = round(float(amount or 0), 2)
    if amount <= 0 and not everything:
        raise ValueError("Enter an amount above 0")
    if invest == "now" and _in_kind_target(mode, a, b):
        from . import engine
        # no check (it could start a plan for either strategy) and no order pass while the books change hands
        if not engine._lock.acquire(timeout=45):
            raise ValueError("The bot is busy with its regular check. Try the move again in a minute.")
        try:
            if not execution._LOCK.acquire(timeout=30):
                raise ValueError("The bot is busy sending orders. Try the move again in a minute.")
            try:
                r = _move_in_kind(mode, a, b, amount, note, everything)
            finally:
                execution._LOCK.release()
        finally:
            engine._lock.release()
        if r is not None:
            return r
    st, x, mid = _raise_cash(mode, a, amount, "move", other=dst, note=note, invest=invest, everything=everything)
    if st == "done":
        ledger.credit(mode, dst, x, hold=(invest == "wait"))
        db.add_event("info", "money", f"Moved ${x:,.2f}: {a.name} → {b.name}", "", strategy=src, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · Moved ${x:,.2f} from {a.name} to {b.name}.", strategy=src)
        return {"status": "done", "amount": x}
    return {"status": "pending", "plan_id": x}


# ---------------------------------------------------------------- Move as shares
# When the receiving strategy wants a symbol the sending one holds (both hold ROM, say), those shares change hands in the
# bot's books at the price the bot values them at (the Money page's price): no Webull order, no fee, Webull's account does
# not change, and neither strategy gains or loses by it. Only the rest is raised the usual way (cash, then a sell plan).
IN_KIND_NOTE = "moved inside the bot"
IN_KIND_OVER = 0.02            # the receiving strategy may end up this much above its target (capped at half its band)


def _target_now(s):
    """The strategy's current target from its last check, or None when that check failed or is old."""
    from . import engine
    r = db.one("SELECT * FROM strategy_state WHERE strategy=?", (s.id,))
    if not r or not r.get("ok") or not r.get("target"):
        return None
    if not engine.fresh(s, {"ok": True, "bar_time": r.get("bar_time")}, md.now_utc()):
        return None
    try:
        t = json.loads(r["target"])
    except (TypeError, ValueError):
        return None
    return {k: float(w) for k, w in (t or {}).items() if w and float(w) > 0.0005}


def _in_kind_target(mode, a, b):
    """b's target when some of a's shares could move to b as shares now, else None (checked again under the locks)."""
    from . import hk
    b = S.get(b.id) or b                               # fresh control
    if (b.row or {}).get("control", "active") != "active":
        return None
    target = _target_now(b)
    if not target:
        return None
    for sid in (a.id, b.id):
        if execution.active_plan(mode, sid):
            return None
        if db.one(f"SELECT COUNT(*) n FROM orders WHERE mode=? AND strategy=? AND status IN ({execution._q(len(execution.WORKING))})",
                  (mode, sid, *execution.WORKING))["n"]:
            return None
    held = ledger.get(mode, a.id)["holdings"]
    blk = execution.blocked_symbols(mode)
    if not any(held.get(s, 0) > execution.EPS and s not in blk and not hk.is_hk(s) for s in target):
        return None
    return target


def _move_in_kind(mode, a, b, amount, note, everything):
    """Under the engine and execution locks: the share part, then the rest. None = nothing moved, use the cash way."""
    target = _in_kind_target(mode, a, b)               # again: a check may have changed it while we waited
    if not target:
        return None
    b = S.get(b.id) or b
    va = ledger.value(mode, a.id)
    total = round(va["value"], 2) if everything else amount
    if total <= 0:
        return None
    if total > va["value"] + 0.01:
        raise ValueError(f"{a.name} is worth ${va['value']:,.2f} now (prices move); you asked for ${amount:,.2f}. "
                         "Press Everything to take all of it.")
    LA, LB = ledger.get(mode, a.id), ledger.get(mode, b.id)
    vb = ledger.value(mode, b.id)
    after = max(0.0, vb["value"] - ledger.waiting_cash(LB)) + total          # b's trading value once the money is in
    free = max(0.0, LA["cash"] - ledger.pending_strategy_buys(mode, a.id))
    over = min(IN_KIND_OVER, b.rebalance_band() / 2)
    prices = md.prices(set(target))
    picks = []
    for sym, w in sorted(target.items(), key=lambda x: -x[1]):
        have, px = LA["holdings"].get(sym, 0.0), prices.get(sym)
        if have <= execution.EPS or not px or px <= 0:
            continue
        frac = execution.fractional_on(mode, sym)
        hb = LB["holdings"].get(sym, 0.0) * px
        picks.append({"symbol": sym, "price": px, "have": have, "dp": execution.FRAC_DP if frac else 0, "frac": frac,
                      "want": max(0.0, w * after - hb), "room": max(0.0, (w + over) * after - hb), "qty": 0})
    if not picks:
        return None

    def take(p, q):
        """Up to q more shares of p, rounded down to whole shares (or 0.01); all of a's shares, exactly, when q covers them."""
        q = max(0.0, min(q, p["have"] - p["qty"]))
        x = p["have"] if p["qty"] + q >= p["have"] - 1e-9 else execution._down(p["qty"] + q, p["dp"])
        added = max(0.0, x - p["qty"])
        p["qty"] = x
        return added * p["price"]

    done = 0.0
    for p in picks:                                      # 1) what b wants, up to the amount
        done += take(p, min(p["want"], total - done) / p["price"])
    need = total - done - (0 if everything else free)
    for p in picks:                                      # 2) a has too little cash for the rest: a little more as shares
        if need <= 0.01:
            break
        got = take(p, min(max(0.0, p["room"] - p["qty"] * p["price"]), need, total - done) / p["price"])
        done += got
        need -= got
    fills = [{"symbol": p["symbol"], "qty": p["qty"], "price": p["price"], "value": round(p["qty"] * p["price"], 2)}
             for p in picks if p["qty"] > execution.EPS and p["qty"] * p["price"] >= execution.MIN_FRACTION_USD]
    if not fills:
        return None
    val = round(sum(f["value"] for f in fills), 2)
    unit = max((execution.MIN_FRACTION_USD if p["frac"] else p["price"]) for p in picks if p["qty"] > execution.EPS)
    _book_in_kind(mode, a, b, fills, val, note)
    db.set_state(f"moverest:{mode}:{b.id}", target)    # b waits for the rest only while its signal is still this one
    out = {"in_kind": fills, "in_kind_value": val}
    t0 = db.one("SELECT COALESCE(MAX(id),0) n FROM money")["n"]

    # the rest (what b does not want as shares) the usual way. Nothing below may undo the share part, so it never raises.
    try:
        L = ledger.get(mode, a.id)
        free = max(0.0, L["cash"] - ledger.pending_strategy_buys(mode, a.id))
        left = ledger.value(mode, a.id)["value"]
        rest = round(left if everything else min(total - val, left), 2)
        if rest <= 0.01:
            return {"status": "done", "amount": val, **out}
        short = 0.0
        if not everything and rest > free + 0.01 and rest - free < unit:
            short = round(rest - free, 2)          # less than one share would have to be sold: move a little less instead
            rest = round(free, 2)
            _short_note(mode, a, short)
            out["short"] = short
            if rest <= 0.01:
                return {"status": "done", "amount": val, **out}
        st, x, mid = _raise_cash(mode, a, rest, "move", other=b.id, note=(note + " · " if note else "") + ledger.MOVE_REST,
                                 invest="now", everything=everything)
        if st == "done":
            ledger.credit(mode, b.id, x, hold=False)
            db.add_event("info", "money", f"Moved ${x:,.2f} cash: {a.name} → {b.name}", "the rest of the move, from its cash",
                         strategy=a.id, mode=mode)
            return {"status": "done", "amount": round(val + x, 2), **out}
        return {"status": "pending", "plan_id": x, "amount": val, **out}
    except Exception as e:
        log.exception("move: the rest after the shares")
        db.run("UPDATE money SET status='failed', note=COALESCE(note,'') || ' · could not be raised' WHERE id>? AND mode=? "
               "AND kind='move' AND strategy=? AND other=? AND status='pending'", (t0, mode, a.id, b.id))
        warn = (f"${val:,.2f} moved as shares, but the rest could not be raised: {e}. "
                f"Check {a.name} and move the rest again if you still want it.")
        db.add_event("warn", "money", f"Move {a.name} → {b.name}: only the shares moved", warn, strategy=a.id, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · {warn}", strategy=a.id)
        return {"status": "done", "amount": val, "warning": warn, **out}


def _short_note(mode, a, short):
    db.add_event("info", "money", f"Move from {a.name}: ${short:,.2f} less than asked",
                 "Shares move in whole shares; raising the last part would have meant a Webull sale smaller than one share, "
                 f"so ${short:,.2f} stays in {a.name}.", strategy=a.id, mode=mode)


def _book_in_kind(mode, a, b, fills, val, note=""):
    """One transaction: a done plan with internal fills on each side, both strategies' holdings, and the money in/out."""
    import secrets
    ledger.ensure(mode, b.id)
    now = int(time.time())
    tag = secrets.token_hex(3)
    what = ", ".join(f"{execution.qs(f['qty'])} {f['symbol']} @ ${f['price']:,.2f}" for f in fills)
    with db.tx() as c:
        pids = {}
        for sid, side, other in ((a.id, "SELL", b.id), (b.id, "BUY", a.id)):
            summ = {"fills": [{"side": side, "symbol": f["symbol"], "qty": f["qty"], "avg": f["price"], "value": f["value"],
                               "inside": f["qty"]} for f in fills], "retried": 0}
            cur = c.execute("INSERT INTO plans(mode,strategy,reason,status,created_at,start_at,finished_at,target,note,on_done,lots,"
                            "interval_min,summary) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (mode, sid, "move", "done", now, now, now, "{}",
                             f"{IN_KIND_NOTE}: {'to' if side == 'SELL' else 'from'} {(b if side == 'SELL' else a).name}", None, 1, 0,
                             json.dumps(summ)))
            pid = cur.lastrowid
            pids[sid] = pid
            for f in fills:
                c.execute("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,limit_price,session,"
                          "scheduled_at,status,client_order_id,broker_order_id,filled_qty,avg_price,applied_qty,applied_value,fee,"
                          "error,updated_at,retry,cross_with) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (pid, mode, sid, 0, 1, 1, f["symbol"], side, f["qty"], f["qty"], f["price"], "CORE", now, "filled",
                           f"int{mode[0]}{pid}{side[0]}{f['symbol']}{tag}", "internal", f["qty"], f["price"], f["qty"], f["value"], 0.0,
                           None, now, 0, other))
                ledger.book_fill_c(c, mode, sid, f["symbol"], side, f["qty"], f["value"])
        # the shares' value leaves a (money out) and joins b (money in); neither strategy's cash changes
        c.execute("UPDATE ledger SET cash=cash-?, cap_out=cap_out+?, updated_at=? WHERE mode=? AND strategy=?",
                  (val, val, now, mode, a.id))
        c.execute("UPDATE ledger SET cash=cash+?, cap_in=cap_in+?, start_t=COALESCE(start_t, ?), updated_at=? WHERE mode=? AND strategy=?",
                  (val, val, now, now, mode, b.id))
        c.execute("INSERT INTO money(mode,t,kind,strategy,other,amount,invest,status,note,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (mode, now, "move", a.id, b.id, val, "now", "done",
                   "; ".join(x for x in (note, f"as shares: {what} — {IN_KIND_NOTE}, no Webull order, no fee") if x), now, val))
    s = db.get_settings()
    saved = val * 2 * (execution.FEE_RESERVE + execution._f(s.get("exec_limit_offset_pct"), 0.10) / 100)
    msg = (f"Moved ${val:,.2f} from {a.name} to {b.name} as shares: {what}. {b.name} wants them too, so they changed hands "
           f"inside the bot: no Webull order, no fee (about ${saved:,.2f} of fees and spread saved). Webull's account does not change.")
    for sid in (a.id, b.id):
        db.add_event("info", "money", f"Moved ${val:,.2f} as shares: {a.name} → {b.name}", msg, strategy=sid, mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · {msg}", strategy=a.id)
    return pids


def after_plan(mode, plan, od):
    """Called when a withdraw/move sell plan finishes."""
    sid = plan["strategy"]
    want = float(od["amount"])
    if od.get("all"):                                    # Everything: whatever the sale brought in
        want = max(want, ledger.get(mode, sid)["cash"])
    moved = ledger.take_cash(mode, sid, want, money_id=od.get("money_id"), to_pool=not od.get("move_to"))
    s = S.get(sid)
    name = s.name if s else sid
    if od.get("move_to"):
        ledger.credit(mode, od["move_to"], moved, hold=(od.get("invest") == "wait"))
        t = S.get(od["move_to"])
        msg = f"Moved ${moved:,.2f} from {name} to {t.name if t else od['move_to']}."
    else:
        msg = f"Withdrew ${moved:,.2f} from {name} (back to bot unassigned)."
    if moved + 0.5 < float(od["amount"]) and not od.get("all"):
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


# ---------------------------------------------------------------- Hong Kong dollars
#   Webull HKD cash ── Allocate HKD to bot ──▶ Bot HKD ── (Hong Kong test trades; HK strategies later)
#                   ◀── Return HKD to Webull ──
# Converting USD to HKD happens in the Webull app (Assets → Currency exchange); the bot only uses HKD you give it.
def account_hkd(mode: str):
    b = brokers.get(mode)
    try:
        return b.account().get("cash_hkd")
    except Exception as e:
        raise ValueError(f"Cannot read the {brokers.MODE_LABEL[mode]} account: {e}")


def hkd_to_bot(mode, amount, note=""):
    from . import hk
    amount = round(float(amount), 2)
    mid = ledger.hk_fund_in(mode, amount, account_hkd(mode), note)
    left = ledger.hk_cash(mode)
    db.add_event("info", "money", f"Allocated HK${amount:,.2f} to the bot", f"{brokers.MODE_LABEL[mode]} · bot HKD now HK${left:,.2f}"
                 f" (≈ ${hk.to_usd(left):,.0f})", mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Allocated HK${amount:,.2f} from Webull to the bot. Bot HKD: HK${left:,.2f}.")
    return {"id": mid, "hkd": left}


def hkd_to_webull(mode, amount, note=""):
    amount = round(float(amount), 2)
    mid = ledger.hk_fund_out(mode, amount, note)
    db.add_event("info", "money", f"Returned HK${amount:,.2f} to Webull", f"{brokers.MODE_LABEL[mode]} · the bot no longer uses it",
                 mode=mode)
    notify.send("money", f"{brokers.MODE_LABEL[mode]} · Returned HK${amount:,.2f} from the bot to Webull.")
    return {"id": mid, "hkd": ledger.hk_cash(mode)}


def paper_convert(usd, rate=None):
    """Paper only: like Webull's currency exchange, turn some of the paper account's free USD into HKD."""
    from . import hk
    usd = round(float(usd), 2)
    if usd <= 0:
        raise ValueError("Enter an amount above 0")
    free = ledger.outside_cash("paper", account_cash("paper"))
    if free is None or usd > free + 0.005:
        raise ValueError(f"The paper account has ${max(free or 0, 0):,.2f} of USD that is not given to the bot")
    rate = rate or hk.hkd_per_usd()
    b = brokers.get("paper")
    a = b._acct()
    a["cash"] -= usd
    a["cash_hkd"] = round(a.get("cash_hkd", 0.0) + usd * rate, 2)
    b._save(a)
    db.add_event("info", "money", f"Paper: converted ${usd:,.2f} to HK${usd * rate:,.2f}", f"rate {rate:.4f} HKD per USD", mode="paper")
    return {"cash_hkd": a["cash_hkd"], "rate": rate}


def hkd_view(mode: str, acct: dict | None) -> dict:
    """The HKD block of the Money page."""
    from . import hk, testtrade
    have = (acct or {}).get("cash_hkd")
    bot = ledger.hk_cash(mode)
    held = {s: q for s, q in testtrade.held(mode).items() if hk.is_hk(s)}
    moves = [dict(m) for m in db.rows("SELECT * FROM money WHERE mode=? AND ccy='HKD' ORDER BY id DESC LIMIT 20", (mode,))]
    return {"account_hkd": have, "bot_hkd": bot, "outside_hkd": ledger.hk_outside(mode, have), "rate": hk.hkd_per_usd(),
            "bot_usd": round(hk.to_usd(bot), 2), "test_held": held, "moves": moves,
            "products": [{"symbol": s, **p} for s, p in hk.PRODUCTS.items()], "market": hk.status(md.now_utc())}
