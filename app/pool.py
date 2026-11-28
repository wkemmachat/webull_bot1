"""Strategy pool: one shared pot of the bot's money per mode (Paper, Webull test and Live each have their own).

PRD "Strategy pool" (27 Nov 2026) and the research "Capital allocation across strategies": instead of fixed cash per strategy,
a member strategy gets money only when its buy signal starts a trade, and gives it all back when the trade ends.

  pool total T   all the money allocated to the bot in this mode: bot unassigned (the pool's free cash) + every strategy's value
  trade starts   a member with no money gets a target above 0 → B = min(slot % × T, free cash, its group's room)
                 group's room = group cap % × T − what that group's strategies hold now (group = What your money is in)
                 B under the smallest trade (min % × T) → nothing is bought; the member waits for money and is checked again
                 several starting the same check and not enough cash → they share it in proportion to their slots
  in the trade   the strategy sizes from B with its own rules (a 50% signal invests half of B); nothing is topped up or cut
  trade ends     target 0 and no shares, no running plan, no open order → all its cash (profit or loss) goes back to the pool
  members        any number; strategies not in the pool are signals only (no new money; a non-member that still holds a
                 trade only sells, on its own signal or at the next open when "sell now" was chosen, then its cash returns)
  no parking     members (and non-members in a pool mode) do not park in gold or T-bills while out: that money is the pool's
The moves are the ledger's own (bot unassigned ⇄ strategy), recorded in Money movements with a "pool:" note, so each strategy's
P&L still counts what it was given and what it gave back. No LINE message: the strategy's own signal message already says it.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time

import numpy as np
import pandas as pd

from . import db, execution, exposure, idle, ledger, marketdata as md
from . import strategies as S

log = logging.getLogger(__name__)

DEFAULTS = {"on": False, "slot_pct": None, "cap_pct": 25.0, "min_pct": 2.0, "members": {}, "sell_now": []}
SLOT_LO, SLOT_HI, SLOT_K = 10.0, 25.0, 150.0          # suggested slot = 150% ÷ members, kept between 10% and 25%
NOTE_IN, NOTE_OUT = "pool: trade starts", "pool: trade ended"


# ---------------------------------------------------------------- settings
def cfg(mode: str) -> dict:
    c = db.get_state(f"pool:{mode}") or {}
    out = {**DEFAULTS, **c}
    out["members"] = dict(out.get("members") or {})
    out["sell_now"] = list(out.get("sell_now") or [])
    return out


def _save(mode: str, c: dict):
    db.set_state(f"pool:{mode}", c)


def on(mode: str) -> bool:
    return bool(cfg(mode).get("on"))


def suggested_slot(n: int) -> float:
    if n <= 0:
        return 15.0
    return round(min(SLOT_HI, max(SLOT_LO, SLOT_K / n)) * 2) / 2


def slot_pct(c: dict) -> float:
    return float(c["slot_pct"]) if c.get("slot_pct") else suggested_slot(len(c["members"]))


def is_member(mode: str, sid: str, c: dict | None = None) -> bool:
    c = c or cfg(mode)
    return bool(c.get("on")) and sid in c["members"]


# ---------------------------------------------------------------- strategy facts
def parking(s) -> set:
    return idle._parking(s)


def main_symbol(s) -> str | None:
    park = parking(s)
    for x in (s.trade_symbols() or []):
        if x and x not in park:
            return x
    return None


def underlying(s) -> tuple:
    """(key, label) of the ETF a strategy trades, for Choose members: 'QLD' / 'Nasdaq-100 2x'. A basket of stocks
    (C2-7) is one key per market: 'Nasdaq-100 stocks' / '7 stocks'."""
    park = parking(s)
    syms = [x for x in (s.trade_symbols() or []) if x and x not in park]
    if not syms:
        return "Other", ""
    if len(syms) > 2:
        return group_label(group_of(s)), f"{len(syms)} stocks"
    g, lev = exposure.classify(syms[0])
    return syms[0], (f"{group_label(g)} {lev:g}x" if g != "other" else "")


def ranks(mode: str) -> dict:
    """Choose members: each strategy's ETF and its 10-year backtest (the Backtest page's numbers; nothing is re-run)."""
    from . import btview
    rows = {r["id"]: r for r in btview.overview(mode).get("rows", [])}
    out = {}
    for s in S.all_instances():
        key, label = underlying(s)
        r = rows.get(s.id) or {}
        out[s.id] = {"etf": key, "etf_label": label, "cap_group": group_label(group_of(s)), "r10": r.get("r10"),
                     "dd10": r.get("dd10"), "ret_dd": r.get("ret_dd"), "years": r.get("years")}
    return out


def group_of(s) -> str:
    sym = main_symbol(s)
    if not sym:
        return "other"
    g = exposure.classify(sym)[0]
    return sym if g == "other" else g


def group_label(g: str) -> str:
    return exposure.GROUPS[g][0] if g in exposure.GROUPS else g


def strip_parking(s, target: dict) -> dict:
    """The target without gold / T-bill / cash-ETF parking: in a pool that money stays in the pool."""
    park = parking(s)
    return {k: w for k, w in (target or {}).items() if k not in park and w and float(w) > 0.0005}


def pool_target(mode: str, s, target: dict, c: dict | None = None) -> dict:
    """The target the bot trades for this strategy in a pool mode (unchanged when the pool is off)."""
    c = c or cfg(mode)
    if not c.get("on"):
        return target
    if s.id in c["sell_now"] and s.id not in c["members"]:
        return {}
    return strip_parking(s, target)


def no_buys(mode: str, sid: str, c: dict | None = None) -> bool:
    """In a pool mode a strategy that is not a member never buys (it may still hold a trade it started as a member)."""
    c = c or cfg(mode)
    return bool(c.get("on")) and sid not in c["members"]


DUST = 0.01           # less than this of a share is a crumb (a sale to 4 decimals can leave one): not a position
SWEEP_S = 600         # a leftover parking position is re-planned at most this often


def held(L: dict) -> dict:
    return {sym: q for sym, q in (L.get("holdings") or {}).items() if q >= DUST}


def _sweep(mode, sid, s, L) -> bool:
    """Gold / T-bill parking left over after its sale (a refused fraction, a retry that gave up): plan its sale again.
    Members and non-members never park while the pool is on, so any parking position is left over."""
    if s is None or (s.row or {}).get("control") == "stopped":
        return False
    left = [sym for sym in held(L) if sym in parking(s)]
    if not left:
        return False
    k = f"poolsweep:{mode}:{sid}"
    if time.time() - (db.get_state(k) or 0) < SWEEP_S:
        return False
    db.set_state(k, int(time.time()))
    ledger.set_applied_target(mode, sid, None)          # the next check plans the sale
    db.add_event("info", "orders", f"{s.name}: selling its leftover parking ({', '.join(left)})",
                 "The pool keeps no gold or T-bill parking", strategy=sid, mode=mode)
    return True


def _busy(mode, sid) -> bool:
    if execution.active_plan(mode, sid):
        return True
    return bool(db.one("SELECT 1 x FROM orders WHERE mode=? AND strategy=? AND status IN ('sending','submitted','unknown') LIMIT 1",
                       (mode, sid)))


def totals(mode: str, prices: dict | None = None) -> dict:
    """T, the pool's free cash and each strategy's value (shares + cash) in this mode."""
    L = ledger.all_for(mode)
    syms = set()
    for r in L.values():
        syms |= set(r["holdings"])
    prices = prices if prices is not None else (md.prices(syms) if syms else {})
    vals = {}
    for sid, r in L.items():
        v = r["cash"]
        for sym, q in r["holdings"].items():
            px = prices.get(sym)
            if px is None:
                px = (r["costs"].get(sym) or 0) / q if q else 0
            v += q * px
        if abs(v) > 0.005 or r["holdings"]:
            vals[sid] = v
    free = ledger.pool_cash(mode)
    return {"T": free + sum(vals.values()), "free": free, "values": vals, "ledger": L}


# ---------------------------------------------------------------- the step (each check, before plans are built)
def step(mode: str, evs: dict, now, fresh=None) -> dict:
    """Return the money of finished trades to the pool, then fund the members whose trade starts. evs: {sid: (strategy, ev)}."""
    c = cfg(mode)
    if not c.get("on"):
        return {}
    from . import moneyops
    if not moneyops._MONEY.acquire(blocking=False):
        return {"busy": True}                              # a money action is running: try at the next check
    try:
        return _step(mode, c, evs, now, fresh)
    finally:
        moneyops._MONEY.release()


def _ok(s, ev, now, fresh):
    if not ev or not ev.get("ok"):
        return False
    return fresh(s, ev, now) if fresh else True


def _step(mode, c, evs, now, fresh) -> dict:
    out = {"returned": [], "funded": [], "waiting": []}
    tot = totals(mode)
    members = c["members"]
    # 1 · trades that ended: all the cash back to the pool
    for sid, r in tot["ledger"].items():
        if _busy(mode, sid):
            continue
        s = S.get(sid)
        if s is None:
            continue
        if _sweep(mode, sid, s, r) or held(r) or r["cash"] <= 0.005:
            continue
        member = sid in members
        if member and (s.row or {}).get("control") == "active":
            ev = (evs.get(sid) or (None, None))[1]
            if not _ok(s, ev, now, fresh) or strip_parking(s, ev.get("target")):
                continue                                   # still in its trade (or no fresh signal to tell)
        amt = round(r["cash"] - ledger.pending_strategy_buys(mode, sid), 2)
        if amt <= 0.005:
            continue
        mid = ledger.record_money(mode, "withdraw", sid, amt, note=NOTE_OUT)
        moved = ledger.take_cash(mode, sid, amt, money_id=mid, to_pool=True)
        db.add_event("info", "money", f"{s.name}: ${moved:,.2f} back to the pool", "Its trade ended" if member else
                     "Not in the pool: its money goes back", strategy=sid, mode=mode)
        out["returned"].append((sid, moved))
        if sid in c["sell_now"]:
            c["sell_now"].remove(sid)
    # 2 · trades that start: B = min(slot, free cash, group room), shared when short
    tot = totals(mode)
    T, free = tot["T"], tot["free"]
    if T <= 0:
        _save(mode, c)
        return out
    slot, cap, mn = slot_pct(c) / 100, float(c["cap_pct"]) / 100, float(c["min_pct"]) / 100
    gval = {}
    for sid, v in tot["values"].items():
        s = S.get(sid)
        if s is not None:
            gval[group_of(s)] = gval.get(group_of(s), 0.0) + v
    want = {}
    for sid in sorted(members, key=lambda x: members[x].get("joined", 0)):
        pair = evs.get(sid)
        if not pair:
            continue
        s, ev = pair
        if (s.row or {}).get("control") != "active" or not _ok(s, ev, now, fresh) or not strip_parking(s, ev.get("target")):
            db.set_state(f"poolwait:{mode}:{sid}", None)
            continue
        r = tot["ledger"].get(sid)
        if r and (held(r) or r["cash"] > 0.5 or _busy(mode, sid)):
            continue                                       # already in its trade
        g = group_of(s)
        room = max(0.0, cap * T - gval.get(g, 0.0))
        b = min(slot * T, room)
        want[sid] = (s, b, b < slot * T - 0.5)
        gval[g] = gval.get(g, 0.0) + b
    need = sum(b for _, b, _ in want.values())
    k = min(1.0, free / need) if need > 0 else 1.0
    for sid, (s, b, capped) in want.items():
        amt = min(math.floor(b * k * 100) / 100, math.floor(free * 100) / 100)     # cents, never more than is left
        if amt < mn * T or amt < 1:
            why = "group cap" if capped and b < mn * T else "free cash"
            st = db.get_state(f"poolwait:{mode}:{sid}") or {}
            db.set_state(f"poolwait:{mode}:{sid}", {"since": st.get("since") or int(time.time()), "free": round(free, 2), "why": why})
            out["waiting"].append(sid)
            continue
        db.set_state(f"poolwait:{mode}:{sid}", None)
        ledger.add_money(mode, sid, amt, note=NOTE_IN + (" (group cap)" if capped else "") + (" (shared cash)" if k < 1 else ""),
                         invest="now")
        ledger.set_applied_target(mode, sid, None)
        db.set_state(f"pooltrade:{mode}:{sid}", {"t": int(time.time()), "amount": amt, "slot": round(slot * T, 2),
                                                 "capped": capped, "shared": k < 1})
        db.add_event("info", "money", f"{s.name}: ${amt:,.2f} from the pool for its trade",
                     f"{slot * 100:g}% of the pool ${T:,.2f}" + (" · cut to the group cap" if capped else "")
                     + (" · free cash shared" if k < 1 else ""), strategy=sid, mode=mode)
        out["funded"].append((sid, amt))
        free -= amt
    _save(mode, c)
    return out


# ---------------------------------------------------------------- settings changes (Money page)
def check_member(mode: str, s):
    if s is None:
        raise ValueError("Unknown strategy")
    if (s.row or {}).get("archived"):
        raise ValueError(f"{s.name} is archived")
    if mode == "live":
        sym = main_symbol(s)
        if sym and not db.one("SELECT 1 x FROM test_trades WHERE mode='live' AND symbol=? AND qty>=1 AND status='ok' LIMIT 1", (sym,)):
            raise ValueError(f"{s.name}: run the Webull test trade of {sym} in Live first (Go-live → Test trade)")


def _pnl(mode, sid) -> float:
    v = ledger.value(mode, sid)
    return round(v["pnl"], 2)


def set_members(mode: str, sids: list) -> dict:
    c = cfg(mode)
    new = list(dict.fromkeys(sids or []))
    for sid in new:
        if sid not in c["members"]:
            check_member(mode, S.get(sid))
    now = int(time.time())
    members = {sid: c["members"].get(sid) or {"joined": now, "pnl0": _pnl(mode, sid)} for sid in new}
    c["members"] = members
    c["sell_now"] = [x for x in c["sell_now"] if x not in members]
    _save(mode, c)
    db.add_event("info", "money", f"Pool members: {len(members)}", ", ".join(S.get(x).name for x in members if S.get(x)), mode=mode)
    return view(mode)


def set_settings(mode: str, on_=None, slot=None, cap=None, minp=None, auto_slot=None) -> dict:
    c = cfg(mode)
    if slot is not None:
        v = float(slot)
        if not 1 <= v <= 100:
            raise ValueError("Trade size: 1 to 100% of the pool")
        c["slot_pct"] = v
    if auto_slot:
        c["slot_pct"] = None
    if cap is not None:
        v = float(cap)
        if not 1 <= v <= 100:
            raise ValueError("Group cap: 1 to 100% of the pool")
        c["cap_pct"] = v
    if minp is not None:
        v = float(minp)
        if not 0 <= v <= 50:
            raise ValueError("Smallest trade: 0 to 50% of the pool")
        c["min_pct"] = v
    if on_ is not None:
        if on_ and not c["members"]:
            raise ValueError("Choose the pool members first")
        was = bool(c.get("on"))
        c["on"] = bool(on_)
        if c["on"] and not was:
            c["since"] = int(time.time())
            for sid in c["members"]:
                c["members"][sid] = {"joined": int(time.time()), "pnl0": _pnl(mode, sid)}
        db.add_event("info", "money", f"Strategy pool {'on' if c['on'] else 'off'}",
                     "Members get money when a trade starts and give it back when it ends; strategies outside the pool are signals only"
                     if c["on"] else "Back to money per strategy: open trades keep their money; free pool cash stays bot unassigned",
                     mode=mode)
    _save(mode, c)
    return view(mode)


def remove(mode: str, sid: str, sell: bool = False) -> dict:
    c = cfg(mode)
    if sid not in c["members"]:
        raise ValueError("Not a pool member")
    c["members"].pop(sid)
    if sell and sid not in c["sell_now"]:
        c["sell_now"].append(sid)
    _save(mode, c)
    s = S.get(sid)
    db.add_event("info", "money", f"{s.name if s else sid}: out of the pool", "Sells at the next open" if sell else
                 "Finishes its trade, then its money goes back to the pool", strategy=sid, mode=mode)
    return view(mode)


def stay(mode: str, sid: str) -> dict:
    """Undo a removal while its trade is still open."""
    c = cfg(mode)
    check_member(mode, S.get(sid))
    c["members"][sid] = {"joined": int(time.time()), "pnl0": _pnl(mode, sid)}
    c["sell_now"] = [x for x in c["sell_now"] if x != sid]
    _save(mode, c)
    return view(mode)


# ---------------------------------------------------------------- the Money page
def _since_trade(mode, sid):
    r = db.one("SELECT t FROM money WHERE mode=? AND strategy=? AND kind='add' AND note LIKE ? ORDER BY id DESC LIMIT 1",
               (mode, sid, NOTE_IN + "%"))
    return r["t"] if r else None


def view(mode: str) -> dict:
    c = cfg(mode)
    tot = totals(mode)
    T, free = tot["T"], tot["free"]
    slot = slot_pct(c)
    states = {r["strategy"]: r for r in db.rows("SELECT strategy, state, label, target, ok FROM strategy_state")}
    members, outside, groups = [], [], {}
    for s in S.all_instances():
        if (s.row or {}).get("control") == "stopped" and s.id not in c["members"] and s.id not in tot["values"]:
            continue
        v = tot["values"].get(s.id, 0.0)
        L = tot["ledger"].get(s.id) or {"holdings": {}, "cash": 0.0}
        st = states.get(s.id) or {}
        try:
            tgt = strip_parking(s, json.loads(st.get("target") or "{}"))
        except (TypeError, ValueError):
            tgt = {}
        g = group_of(s)
        H = held(L)
        in_trade = bool(H) or abs(v) > 0.5
        park_only = bool(H) and all(sym in parking(s) for sym in H)
        wait = db.get_state(f"poolwait:{mode}:{s.id}")
        pt = db.get_state(f"pooltrade:{mode}:{s.id}") or {}
        base = {"id": s.id, "name": s.name, "color": s.color, "etf": main_symbol(s), "group": g, "group_label": group_label(g), "value": round(v, 2),
                "pct": (v / T) if T > 0 else None, "state": st.get("state"), "label": st.get("label"), "wants": bool(tgt),
                "control": (s.row or {}).get("control")}
        if s.id in c["members"]:
            m = c["members"][s.id]
            vv = ledger.value(mode, s.id)
            if park_only:
                status = ("", "Selling its gold parking · money back after")
            elif in_trade and not H:
                status = ("ok", "Has its money · buys at the next open") if tgt else ("", "Trade ended · money back at the next check")
            elif in_trade:
                status = ("info", "In a trade · group cap") if pt.get("capped") else ("ok", "In a trade · partial") if pt.get("shared") else \
                    ("ok", "In a trade")
            elif wait and tgt:
                status = ("warn", "Signal · waits for money")
            elif tgt:
                status = ("info", "Signal · buys at the next check")
            else:
                status = ("", "No signal · waiting")
            open_pnl = None
            if in_trade and pt.get("amount"):
                open_pnl = round(v - pt["amount"], 2)
            members.append({**base, "status": status, "since": _since_trade(mode, s.id) if in_trade else None, "open_pnl": open_pnl,
                            "pnl_joined": round(vv["pnl"] - (m.get("pnl0") or 0), 2), "joined": m.get("joined"),
                            "wait": wait})
            if in_trade:
                gr = groups.setdefault(g, {"key": g, "label": group_label(g), "value": 0.0, "who": [], "color": exposure.GROUPS.get(g, ("", "", "#888"))[2]})
                gr["value"] += v
                gr["who"].append(s.name.split(" · ")[0])
            else:
                groups.setdefault(g, {"key": g, "label": group_label(g), "value": 0.0, "who": [], "color": exposure.GROUPS.get(g, ("", "", "#888"))[2]})
                groups[g]["who"].append(s.name.split(" · ")[0])
        else:
            leaving = in_trade and c.get("on")
            outside.append({**base, "leaving": leaving, "sell_now": s.id in c["sell_now"]})
            if leaving:
                gr = groups.setdefault(g, {"key": g, "label": group_label(g), "value": 0.0, "who": [], "color": exposure.GROUPS.get(g, ("", "", "#888"))[2]})
                gr["value"] += v
                gr["who"].append(s.name.split(" · ")[0] + " (leaving)")
    for gr in groups.values():
        gr["pct"] = gr["value"] / T if T > 0 else 0.0
        gr["who"] = list(dict.fromkeys(gr["who"]))
    in_trades = sum(tot["values"].values())
    return {"mode": mode, "on": bool(c.get("on")), "slot_pct": slot, "slot_auto": not c.get("slot_pct"),
            "suggested_slot": suggested_slot(len(c["members"])), "cap_pct": float(c["cap_pct"]), "min_pct": float(c["min_pct"]),
            "total": round(T, 2), "free": round(free, 2), "in_trades": round(in_trades, 2), "slot_usd": round(slot / 100 * T, 2),
            "cap_usd": round(float(c["cap_pct"]) / 100 * T, 2), "min_usd": round(float(c["min_pct"]) / 100 * T, 2),
            "members": members, "outside": sorted(outside, key=lambda r: (not r["leaving"], r["name"])),
            "groups": sorted(groups.values(), key=lambda g: -g["value"]), "waiting": [m for m in members if m["status"][1].startswith("Signal · waits")],
            "needs_test": mode == "live", "alerts": _alerts(mode)}


def _alerts(mode):
    try:
        from . import poolalert
        return poolalert.public(mode)
    except Exception as e:                                  # the settings dialog still opens
        log.warning("pool alert settings: %s", e)
        return None


def since(mode: str, c: dict | None = None) -> int | None:
    """When the pool was turned on (this time): the start of the pool's own record."""
    c = c or cfg(mode)
    if not c.get("on"):
        return None
    if c.get("since"):
        return int(c["since"])
    r = db.one("SELECT MAX(t) t FROM events WHERE mode=? AND title='Strategy pool on'", (mode,))   # turned on before 'since' was kept
    return int(r["t"]) if r and r["t"] else None


def repair_equity(mode: str) -> int:
    """Once per pool start: the bot's '*' equity records written since then left out the pool's free cash (the Dashboard
    showed $0 and −100%). Pool cash + the strategies' net money in is the money allocated to the bot, which only changes
    when money moves between Webull and the bot, so each record gets value += K(t) − capital, capital = K(t)."""
    t0 = since(mode)
    if not t0:
        return 0
    key = f"pool_eq_fix:{mode}:{t0}"
    if db.get_state(key):
        return 0
    L = ledger.all_for(mode)
    K = ledger.pool_cash(mode) + sum((r["cap_in"] or 0) - (r["cap_out"] or 0) for r in L.values())
    flows = db.rows("SELECT t, kind, amount FROM money WHERE mode=? AND kind IN ('to_bot','to_webull') AND t>=? "
                    "AND (ccy IS NULL OR ccy='USD')", (mode, t0))
    n = 0
    with db.tx() as c:
        for r in c.execute("SELECT t, value, capital, bench FROM equity WHERE mode=? AND strategy='*' AND t>=?", (mode, t0)).fetchall():
            k = K - sum((f["amount"] if f["kind"] == "to_bot" else -f["amount"]) for f in flows if f["t"] > r["t"])
            add = k - (r["capital"] or 0)
            if add > 0.5:
                c.execute("UPDATE equity SET value=?, capital=?, bench=? WHERE mode=? AND strategy='*' AND t=?",
                          ((r["value"] or 0) + add, k, (r["bench"] or 0) + add, mode, r["t"]))
                n += 1
    db.set_state(key, int(time.time()))
    if n:
        db.add_event("info", "money", f"Bot value records repaired ({n})", "The pool's free cash is now part of the bot's value", mode=mode)
    return n


def strategy_info(mode: str, sid: str) -> dict:
    from . import brokers
    c = cfg(mode)
    if not c.get("on"):
        return {"on": False}
    s = S.get(sid)
    tot = totals(mode)
    T = tot["T"]
    member = sid in c["members"]
    return {"on": True, "member": member, "mode_label": brokers.MODE_LABEL.get(mode, mode), "slot_pct": slot_pct(c),
            "slot_usd": round(slot_pct(c) / 100 * T, 2), "cap_pct": float(c["cap_pct"]), "group_label": group_label(group_of(s)) if s else "",
            "waiting": bool(member and db.get_state(f"poolwait:{mode}:{sid}")), "leaving": (not member) and abs(tot["values"].get(sid, 0.0)) > 0.5}


# ---------------------------------------------------------------- expected return of a mix: the pool backtest
_bt_lock = threading.Lock()
_bt_jobs: dict = {}
_bt_cache: dict = {}


def _series(sid):
    from . import backtest as BT
    r = BT.run(sid)
    if not r.get("ok"):
        raise ValueError(f"{sid}: {r.get('error')}")
    s = r["series"]
    idx = pd.to_datetime(s["t"], unit="s").normalize()
    eq = pd.Series(s["strategy"], index=idx, dtype=float)
    ex = pd.Series(s["expo"], index=idx, dtype=float)
    eq, ex = eq[~eq.index.duplicated(keep="last")], ex[~ex.index.duplicated(keep="last")]
    return eq, ex


def simulate(R: pd.DataFrame, X: pd.DataFrame, avail: pd.DataFrame, groups: dict, slot: float, cap: float, minp: float,
             C: float = 100_000.0, cost: float = 0.0011):
    """The pool's rules on the members' own backtests: each member's daily return on the money it was given (its backtest
    return), money given when its trade starts (min of slot × total, free cash, group room; shared when short; skipped
    under the smallest trade), riding with its profit or loss, back to the pool when it holds nothing. Returns the daily
    value and the share of money idle."""
    days = R.index
    cols = list(R.columns)
    n = len(cols)
    xr, xp = X.values, X.shift(1).fillna(0.0).values
    rr, av = R.values, avail.values
    involved = np.maximum(xr, xp)
    g = np.array([groups[c] for c in cols])
    held = np.zeros(n)
    total = C
    vals, idle_ = [], []
    for i in range(len(days)):
        act = (involved[i] > 0) & av[i]
        keep = act & (held > 0)
        alloc = np.where(keep, held, 0.0)
        new = act & ~(held > 0)
        if new.any():
            free = total - alloc.sum()                     # money given to open trades (their own cash included) is theirs
            gv = {}
            for j in np.where(keep)[0]:
                gv[g[j]] = gv.get(g[j], 0.0) + alloc[j]
            want = np.zeros(n)
            for j in np.where(new)[0]:
                room = max(0.0, cap * total - gv.get(g[j], 0.0))
                want[j] = min(slot * total, room)
                gv[g[j]] = gv.get(g[j], 0.0) + want[j]
            need = want.sum()
            k = min(1.0, max(free, 0.0) / need) if need > 0 else 1.0
            b = want * k
            b[b < minp * total] = 0.0
            alloc = alloc + b
        pnl = alloc * rr[i]
        held = np.where(act, alloc + pnl, 0.0)
        idle_.append(1 - (alloc * involved[i]).sum() / total if total > 0 else 1)
        total = total + pnl.sum()
        vals.append(total)
    return pd.Series(vals, index=days), float(np.mean(idle_))


def _stats(v: pd.Series, years=None) -> dict:
    if years:
        v = v[v.index >= v.index[-1] - pd.DateOffset(years=years)]
    if len(v) < 30:
        return None
    y = (v.index[-1] - v.index[0]).days / 365.25
    cagr = (v.iloc[-1] / v.iloc[0]) ** (1 / y) - 1 if y > 0 else 0.0
    dd = float((v / v.cummax() - 1).min())
    return {"cagr": round(cagr * 100, 1), "maxdd": round(dd * 100, 1), "from": str(v.index[0].date())}


def ranges(v: pd.Series) -> dict:
    """What a normal stretch of this mix looks like in its backtest (month ends): for 1–12 months, the 10th / 50th / 90th
    percentile of the return over that many months, plus the share of months up, the worst month and 12-month figures.
    The Dashboard compares the real pool with these."""
    m = v.resample("ME").last().dropna()
    out = {"bands": [], "months": int(len(m) - 1)}
    for k in range(1, 13):
        r = (m / m.shift(k) - 1).dropna()
        if len(r) >= 12:
            q = np.percentile(r, [10, 50, 90])
            out["bands"].append([k, round(float(q[0]) * 100, 1), round(float(q[1]) * 100, 1), round(float(q[2]) * 100, 1)])
    r1 = (m / m.shift(1) - 1).dropna()
    r12 = (m / m.shift(12) - 1).dropna()
    if len(r1):
        out.update(m_up=round(float((r1 > 0).mean()) * 100), m_worst=round(float(r1.min()) * 100, 1), m_best=round(float(r1.max()) * 100, 1))
    if len(r12):
        out.update(y_p10=round(float(np.percentile(r12, 10)) * 100, 1), y_p50=round(float(np.percentile(r12, 50)) * 100, 1),
                   y_worst=round(float(r12.min()) * 100, 1), y_down=round(float((r12 < 0).mean()) * 100))
    return out


ZONE_WARM = 756          # trading days (3 years) before a day's fall is ranked against the days before it
ZONE_REARM = 70         # the add-money alert is armed again once the fall is shallower than this percentile
ZONE_TH = (70, 75, 80, 85, 90, 95)
FWD = 252               # a year of trading days


def past_pct(dd: np.ndarray, warm: int = ZONE_WARM) -> np.ndarray:
    """Each day's fall (dd ≤ 0) ranked against the days before it only (no hindsight): the percentage of past days that
    were less deep (ties count half). NaN for the first `warm` days."""
    import bisect
    depth = -dd
    out = np.full(len(depth), np.nan)
    seen: list = []
    for i, x in enumerate(depth):
        if i >= warm:
            lo, hi = bisect.bisect_left(seen, x), bisect.bisect_right(seen, x)
            out[i] = (lo + (hi - lo) / 2) / len(seen) * 100
        bisect.insort(seen, x)
    return out


def first_days(pct: np.ndarray, th: float, rearm: float = ZONE_REARM) -> list:
    """The days an alert at `th` would have fired: the first day at or past it, again only after the fall was shallower
    than the `rearm` percentile."""
    out, armed = [], True
    for i, p in enumerate(pct):
        if np.isnan(p):
            continue
        if armed and p >= th:
            out.append(i)
            armed = False
        elif p < rearm:
            armed = True
    return out


def daily_pct(v: pd.Series) -> np.ndarray:
    vv = v.values.astype(float)
    return past_pct(vv / np.maximum.accumulate(vv) - 1)


def zones(v: pd.Series, pct: np.ndarray | None = None) -> dict:
    """How deep the pool backtest of today's members is below its high, what share of past days were less deep, and what
    followed the first day of each fall past 70…95th percentile (a year later; the further fall first)."""
    if len(v) < ZONE_WARM + FWD:
        return {}
    vv = v.values.astype(float)
    dd = vv / np.maximum.accumulate(vv) - 1
    pct = past_pct(dd) if pct is None else pct
    fwd = np.full(len(vv), np.nan)
    low = np.full(len(vv), np.nan)
    for i in range(len(vv) - FWD):
        fwd[i] = vv[i + FWD] / vv[i] - 1
        low[i] = vv[i + 1:i + FWD + 1].min() / vv[i] - 1
    def row(idx):
        f = fwd[idx]
        f, l = f[~np.isnan(f)], low[idx][~np.isnan(fwd[idx])]
        if not len(f):
            return {"n": 0}
        return {"n": int(len(f)), "up": int((f > 0).sum()), "med": round(float(np.median(f)) * 100, 1),
                "p10": round(float(np.percentile(f, 10)) * 100, 1), "fall": round(float(np.median(l)) * 100, 1)}
    ok = np.where(~np.isnan(pct))[0]
    rows = {"any": row(ok)}
    for th in ZONE_TH:
        rows[str(th)] = row(np.array(first_days(pct, th), dtype=int))
    hist = -dd
    deep = {str(th): round(-float(np.percentile(hist, th)) * 100, 1) for th in ZONE_TH}
    hi = int(np.where(vv >= np.maximum.accumulate(vv))[0][-1])
    # each threshold's last alert day, and whether the alert is still "used" (not re-armed since)
    last = {}
    for th in ZONE_TH:
        fd = first_days(pct, th)
        if fd:
            j = fd[-1]
            rearmed = bool((pct[j:] < ZONE_REARM).any())
            last[str(th)] = {"day": str(v.index[j].date()), "open": not rearmed}
    first_ok = v.index[ok[0]] if len(ok) else None
    last_fwd = v.index[len(vv) - FWD - 1] if len(vv) > FWD else None
    return {"depth": round(float(dd[-1]) * 100, 1), "pct": None if np.isnan(pct[-1]) else round(float(pct[-1]), 1),
            "day": str(v.index[-1].date()), "high_day": str(v.index[hi].date()), "deep": deep, "rows": rows, "last": last,
            "from": str(first_ok.date()) if first_ok is not None else None,
            "to": str(last_fwd.date()) if last_fwd is not None else None, "rearm": ZONE_REARM}


def _p(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 1)


def weekly(v: pd.Series, pct: np.ndarray | None = None) -> list:
    """A point a week: [time, value (100 at the start), deepest fall below the high (%), highest percentile of the fall that
    week (past days only; None in the first 3 years)]. The last point is the last day."""
    v = v / v.iloc[0] * 100
    dd = v / v.cummax() - 1
    p = pd.Series(pct if pct is not None else np.full(len(v), np.nan), index=v.index)
    w = pd.DataFrame({"v": v.resample("W-FRI").last(), "dd": dd.resample("W-FRI").min(), "p": p.resample("W-FRI").max()}).dropna(subset=["v"])
    out = [[int(v.index[0].timestamp()), 100.0, 0.0, None]] + [[int(t.timestamp()), round(float(r.v), 3), round(float(r.dd) * 100, 2), _p(r.p)]
                                                               for t, r in w.iterrows() if t > v.index[0]]
    last = [int(v.index[-1].timestamp()), round(float(v.iloc[-1]), 3), round(float(dd.iloc[-1]) * 100, 2), _p(p.iloc[-1])]
    if out and out[-1][0] >= last[0]:
        out[-1] = last
    else:
        out.append(last)
    return out


def daily(v: pd.Series, pct: np.ndarray | None = None) -> list:
    """Every day, same fields as weekly(): the Dashboard loads it when you zoom in."""
    v = v / v.iloc[0] * 100
    dd = (v / v.cummax() - 1).values
    p = pct if pct is not None else np.full(len(v), np.nan)
    return [[int(t.timestamp()), round(float(x), 3), round(float(d) * 100, 2), _p(q)] for t, x, d, q in zip(v.index, v.values, dd, p)]


def backtest(sids: list, slot_pct_: float, cap_pct: float, min_pct: float) -> dict:
    """The expected return of this mix: {"ready": True, ...} or {"ready": False, "done": k, "of": n} while the members'
    backtests are still being built (in the background, once per data day)."""
    sids = sorted(dict.fromkeys(sids or []))
    if not sids:
        return {"ready": True, "empty": True}
    key = (tuple(sids), round(float(slot_pct_), 2), round(float(cap_pct), 2), round(float(min_pct), 2), md.now_utc().date().isoformat())
    with _bt_lock:
        if key in _bt_cache:
            return _bt_cache[key]
        job = _bt_jobs.get(key)
        if job is None:
            job = {"done": 0, "of": len(sids), "error": None}
            _bt_jobs[key] = job
            threading.Thread(target=_bt_work, args=(key, sids, slot_pct_, cap_pct, min_pct, job), daemon=True).start()
    return {"ready": False, "done": job["done"], "of": job["of"], "error": job["error"]}


def _bt_work(key, sids, slot_pct_, cap_pct, min_pct, job):
    try:
        R, X, groups, names = {}, {}, {}, {}
        for sid in sids:
            s = S.get(sid)
            eq, ex = _series(sid)
            R[sid], X[sid] = eq.pct_change(), ex
            groups[sid], names[sid] = group_of(s), s.name
            job["done"] += 1
        R, X = pd.DataFrame(R), pd.DataFrame(X)
        avail = X.notna()
        R, X = R.fillna(0.0), X.fillna(0.0)
        v, idle_avg = simulate(R, X, avail, groups, slot_pct_ / 100, cap_pct / 100, min_pct / 100)
        pct = daily_pct(v)
        # the same members with fixed money each (today's way), for comparison
        each = (1 + R.where(avail, 0.0)).cumprod().sum(axis=1)
        out = {"ready": True, "members": [{"id": s, "name": names[s], "group": group_label(groups[s]),
                                           "from": str(X[s][avail[s]].index[0].date()) if avail[s].any() else None} for s in sids],
               "slot_pct": slot_pct_, "cap_pct": cap_pct, "min_pct": min_pct, "idle": round(idle_avg * 100, 1),
               "periods": {k: _stats(v, y) for k, y in (("1Y", 1), ("3Y", 3), ("5Y", 5), ("10Y", 10))},
               "all": _stats(v), "fixed": {k: _stats(each, y) for k, y in (("10Y", 10),)} | {"all": _stats(each)},
               "curve": [[int(t.timestamp()), round(float(x), 2)] for t, x in v.resample("ME").last().items()],
               "ranges": ranges(v), "weekly": weekly(v, pct), "zone": zones(v, pct), "daily": daily(v, pct),
               "daily_tail": [[str(t.date()), round(float(x), 4)] for t, x in v.iloc[-400:].items()],
               "note": "Each member's own backtest (Webull's fee, cash 0%), run through the pool's rules from $100,000. Members join "
                       "when their history starts; several use modelled ETF history before listing. Plan lower: the strategies were "
                       "picked on the same years."}
        with _bt_lock:
            _bt_cache[key] = out
            if len(_bt_cache) > 40:
                _bt_cache.pop(next(iter(_bt_cache)))
    except Exception as e:
        log.exception("pool backtest")
        job["error"] = str(e)[:300]
        with _bt_lock:
            _bt_cache[key] = {"ready": True, "error": str(e)[:300]}
    finally:
        with _bt_lock:
            _bt_jobs.pop(key, None)
