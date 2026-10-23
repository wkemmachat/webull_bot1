"""The bot's own books: for every trading mode and strategy, its cash and the shares it holds.

Each strategy is a sub-account of the one broker account. Money given to a strategy (Add money) and
taken back (Withdraw) is recorded in `money`, so returns are measured on net money in and adding money
never looks like profit. Shares you bought yourself in Webull are never counted as the bot's.
"""
from __future__ import annotations

import json
import time

from . import db, marketdata as md


def ensure(mode: str, sid: str):
    db.run("INSERT OR IGNORE INTO ledger(mode,strategy,cash,cap_in,cap_out,updated_at) VALUES(?,?,0,0,0,?)",
           (mode, sid, int(time.time())))


def get(mode: str, sid: str) -> dict:
    ensure(mode, sid)
    r = db.one("SELECT * FROM ledger WHERE mode=? AND strategy=?", (mode, sid))
    r["holdings"] = {h["symbol"]: h["qty"] for h in db.rows("SELECT symbol, qty FROM holdings WHERE mode=? AND strategy=? AND qty>1e-9",
                                                             (mode, sid))}
    r["costs"] = {h["symbol"]: h["cost"] for h in db.rows("SELECT symbol, cost FROM holdings WHERE mode=? AND strategy=? AND qty>1e-9",
                                                           (mode, sid))}
    return r


def all_for(mode: str) -> dict:
    out = {r["strategy"]: {**r, "holdings": {}, "costs": {}} for r in db.rows("SELECT * FROM ledger WHERE mode=?", (mode,))}
    for h in db.rows("SELECT * FROM holdings WHERE mode=? AND qty>1e-9", (mode,)):
        if h["strategy"] in out:
            out[h["strategy"]]["holdings"][h["symbol"]] = h["qty"]
            out[h["strategy"]]["costs"][h["symbol"]] = h["cost"]
    return out


def book_fill(mode, sid, symbol, side, dq, dv):
    """Apply a (partial) fill: dq shares for dv dollars."""
    sign = 1 if side == "BUY" else -1
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO holdings(mode,strategy,symbol,qty,cost) VALUES(?,?,?,0,0)", (mode, sid, symbol))
        h = c.execute("SELECT qty, cost FROM holdings WHERE mode=? AND strategy=? AND symbol=?", (mode, sid, symbol)).fetchone()
        qty, cost = h["qty"], h["cost"]
        if side == "BUY":
            qty, cost = qty + dq, cost + dv
        else:
            avg = cost / qty if qty > 1e-9 else 0
            qty, cost = max(0.0, qty - dq), max(0.0, cost - avg * dq)
        c.execute("UPDATE holdings SET qty=?, cost=? WHERE mode=? AND strategy=? AND symbol=?", (qty, cost, mode, sid, symbol))
        c.execute("UPDATE ledger SET cash=cash-?, updated_at=? WHERE mode=? AND strategy=?", (sign * dv, int(time.time()), mode, sid))


def value(mode: str, sid: str, prices: dict | None = None) -> dict:
    L = get(mode, sid)
    prices = prices if prices is not None else md.prices(L["holdings"].keys())
    pos, total, missing = {}, L["cash"], False
    for sym, q in L["holdings"].items():
        px = prices.get(sym)
        if px is None:
            missing = True
            px = (L["costs"].get(sym) or 0) / q if q else 0
        pos[sym] = {"qty": q, "price": px, "value": q * px, "cost": L["costs"].get(sym)}
        total += q * px
    net = (L["cap_in"] or 0) - (L["cap_out"] or 0)
    return {"cash": L["cash"], "positions": pos, "value": total, "net_in": net, "cap_in": L["cap_in"], "cap_out": L["cap_out"],
            "pnl": total - net, "ret": (total / net - 1) if net > 0 else None, "missing_price": missing, "start_t": L["start_t"],
            "hold_cash": L["hold_cash"], "waiting_cash": waiting_cash(L)}


def weights(mode: str, sid: str, prices: dict) -> tuple[dict, float]:
    """Current share of the strategy's TRADING value per symbol (cash waiting for a buy signal left out), and that total."""
    v = value(mode, sid, prices)
    tot = v["value"] - waiting_cash(get(mode, sid))
    if tot <= 0:
        return {}, 0.0
    return {s: p["value"] / tot for s, p in v["positions"].items()}, tot


# ---------------------------------------------------------------- money
def strategies_cash(mode: str) -> float:
    return db.one("SELECT COALESCE(SUM(cash),0) v FROM ledger WHERE mode=?", (mode,))["v"]


def pending_buys(mode: str) -> float:
    return db.one("SELECT COALESCE(SUM((COALESCE(qty,0)-COALESCE(applied_qty,0))*COALESCE(limit_price,0)),0) v FROM orders "
                  "WHERE mode=? AND side='BUY' AND status IN ('sending','submitted','unknown')", (mode,))["v"]


# Three layers of money in one broker account:
#   Webull account  =  allocated to the bot  +  not for the bot (cash the bot never touches + your own shares)
#   allocated       =  strategies (their cash + shares)  +  bot unassigned (the "pool")
def pool(mode: str) -> dict:
    r = db.one("SELECT * FROM pool WHERE mode=?", (mode,))
    if not r:
        db.run("INSERT OR IGNORE INTO pool(mode,cash,cap_in,cap_out,updated_at) VALUES(?,0,0,0,?)", (mode, int(time.time())))
        r = db.one("SELECT * FROM pool WHERE mode=?", (mode,))
    return r


def pool_cash(mode: str) -> float:
    return round(pool(mode)["cash"] or 0.0, 2)


def _pool_add(c, mode, amount):
    pool(mode)
    c.execute("UPDATE pool SET cash=cash+?, updated_at=? WHERE mode=?", (amount, int(time.time()), mode))


def bot_cash(mode: str) -> float:
    """All cash that belongs to the bot: strategies' cash + bot unassigned."""
    return strategies_cash(mode) + pool_cash(mode)


def outside_cash(mode: str, account_cash: float | None) -> float | None:
    """Cash in the broker account that is NOT given to the bot. The bot never uses it."""
    if account_cash is None:
        return None
    return account_cash - bot_cash(mode)


def unassigned(mode: str, account_cash: float | None = None) -> float:
    """Bot unassigned: money given to the bot that no strategy has yet."""
    return pool_cash(mode)


def fund_in(mode: str, amount: float, account_cash: float | None, note: str = "") -> int:
    """Webull → bot: allocate part of the account's free cash to the bot (it lands in bot unassigned)."""
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Enter an amount above 0")
    free = outside_cash(mode, account_cash)
    if free is None:
        raise ValueError("Cannot read the account cash right now; try again in a minute")
    if amount > free + 0.005:
        raise ValueError(f"Only ${max(free, 0):,.2f} of cash in the account is not given to the bot yet")
    now = int(time.time())
    with db.tx() as c:
        _pool_add(c, mode, amount)
        c.execute("UPDATE pool SET cap_in=cap_in+? WHERE mode=?", (amount, mode))
        cur = c.execute("INSERT INTO money(mode,t,kind,strategy,amount,status,note,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?,?)",
                        (mode, now, "to_bot", None, amount, "done", note, now, amount))
    return cur.lastrowid


def fund_out(mode: str, amount: float, note: str = "") -> int:
    """Bot → Webull: give bot-unassigned cash back to the account (the bot stops using it)."""
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Enter an amount above 0")
    have = pool_cash(mode)
    if amount > have + 0.005:
        raise ValueError(f"Bot unassigned has ${have:,.2f}. Withdraw from a strategy first to free more.")
    amount = min(amount, have)
    now = int(time.time())
    with db.tx() as c:
        _pool_add(c, mode, -amount)
        c.execute("UPDATE pool SET cap_out=cap_out+? WHERE mode=?", (amount, mode))
        cur = c.execute("INSERT INTO money(mode,t,kind,strategy,amount,status,note,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?,?)",
                        (mode, now, "to_webull", None, amount, "done", note, now, amount))
    return cur.lastrowid


def add_money(mode: str, sid: str, amount: float, note: str = "", invest: str = "now", account_cash: float | None = None) -> int:
    """Bot unassigned → strategy."""
    if amount <= 0:
        raise ValueError("Enter an amount above 0")
    un = pool_cash(mode)
    if amount > un + 0.005:
        raise ValueError(f"Bot unassigned has only ${max(un, 0):,.2f}. Allocate more money to the bot first.")
    amount = min(amount, un) if amount > un else amount
    with db.tx() as c:
        _pool_add(c, mode, -amount)
    credit(mode, sid, amount, hold=(invest == "wait"))
    now = int(time.time())
    cur = db.run("INSERT INTO money(mode,t,kind,strategy,amount,invest,status,note,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (mode, now, "add", sid, amount, invest, "done", note, now, amount))
    return cur.lastrowid


def credit(mode: str, sid: str, amount: float, hold: bool = False, keep_hold: bool = True):
    """Give a strategy money (counted as money in).
    hold=True: this amount is set aside as cash until the strategy's next BUY signal; the rest of the strategy keeps
    trading as usual. More waiting money joins the same wait (keep_hold). Money added with hold=False is invested at
    the current signal and the waiting cash keeps waiting."""
    ensure(mode, sid)
    now = int(time.time())
    L = get(mode, sid)
    if hold:
        since = L["hold_cash"] if (keep_hold and L["hold_cash"]) else now
        amt = (L["hold_amt"] or 0) + amount
    else:
        since, amt = L["hold_cash"] or 0, L["hold_amt"] or 0
    db.run("UPDATE ledger SET cash=cash+?, cap_in=cap_in+?, start_t=COALESCE(start_t, ?), hold_cash=?, hold_amt=?, updated_at=? "
           "WHERE mode=? AND strategy=?", (amount, amount, now, since, amt, now, mode, sid))


def waiting_cash(L: dict) -> float:
    """Cash set aside for the next buy signal (never more than the cash there is)."""
    if not L.get("hold_cash"):
        return 0.0
    return max(0.0, min(L.get("hold_amt") or 0.0, L["cash"]))


def tradable_cash(L: dict) -> float:
    return L["cash"] - waiting_cash(L)


def end_wait(mode: str, sid: str):
    db.run("UPDATE ledger SET hold_cash=0, hold_amt=0 WHERE mode=? AND strategy=?", (mode, sid))


def take_cash(mode: str, sid: str, amount: float, kind="withdraw", other=None, note="", money_id=None, to_pool=False) -> float:
    """Move up to `amount` of the strategy's free cash out of it. Returns what was moved.
    to_pool=True puts it in bot unassigned (a withdrawal); a move hands it to another strategy instead."""
    L = get(mode, sid)
    free = max(0.0, L["cash"] - pending_strategy_buys(mode, sid))
    amt = round(min(amount, free), 2)
    now = int(time.time())
    with db.tx() as c:
        c.execute("UPDATE ledger SET cash=cash-?, cap_out=cap_out+?, updated_at=? WHERE mode=? AND strategy=?",
                  (amt, amt, now, mode, sid))
        if L.get("hold_cash"):                     # money taken out comes from the waiting cash first
            left = max(0.0, (L.get("hold_amt") or 0) - amt)
            c.execute("UPDATE ledger SET hold_amt=?, hold_cash=? WHERE mode=? AND strategy=?",
                      (left, L["hold_cash"] if left > 0.005 else 0, mode, sid))
        if money_id:
            c.execute("UPDATE money SET status='done', done_at=?, done_amount=? WHERE id=?", (now, amt, money_id))
        if to_pool:
            _pool_add(c, mode, amt)
    return amt


def pending_strategy_buys(mode, sid):
    return db.one("SELECT COALESCE(SUM((COALESCE(qty,0)-COALESCE(applied_qty,0))*COALESCE(limit_price,0)),0) v FROM orders "
                  "WHERE mode=? AND strategy=? AND side='BUY' AND status IN ('sending','submitted','unknown')", (mode, sid))["v"]


def record_money(mode, kind, sid, amount, other=None, note="", invest=None, status="pending", plan_id=None) -> int:
    cur = db.run("INSERT INTO money(mode,t,kind,strategy,other,amount,invest,status,note,plan_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (mode, int(time.time()), kind, sid, other, amount, invest, status, note, plan_id))
    return cur.lastrowid


def moves(mode: str, limit=50):
    return db.rows("SELECT * FROM money WHERE mode=? ORDER BY id DESC LIMIT ?", (mode, limit))


def set_applied_target(mode, sid, target: dict | None):
    db.run("UPDATE ledger SET applied_target=? WHERE mode=? AND strategy=?", (json.dumps(target) if target is not None else None, mode, sid))


def reset_mode(mode: str):
    with db.tx() as c:
        for t in ("ledger", "holdings", "money", "equity", "pool"):
            c.execute(f"DELETE FROM {t} WHERE mode=?", (mode,))
        c.execute("UPDATE orders SET status='cancelled', error='account reset' WHERE mode=? AND status IN "
                  "('scheduled','sending','submitted','unknown')", (mode,))
        c.execute("UPDATE plans SET status='cancelled', note=COALESCE(note,'') || ' · account reset' WHERE mode=? AND status='active'",
                  (mode,))
    db.set_state(f"bench:{mode}", None)
