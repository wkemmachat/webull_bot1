"""Split execution: turn a strategy's target into lots of limit orders sent a few minutes apart.

A PLAN moves one strategy from what it holds to its target (e.g. SGOV → AGQ, or 100% QLD → 25% QLD + 74% BIL).
It has N rounds spaced M minutes apart from a start time (a set Bangkok time, or as soon as the market is
open). In every round the sells go first, then the buys, so cash is freed before it is spent:
  step 2k   = round k sells (fixed share counts decided when the plan is made)
  step 2k+1 = round k buys  (sized when sent: the strategy's free cash toward each symbol's target)
Lots are limit orders slightly through the market. A lot that does not fill within the interval is
cancelled and re-sent at a fresh price, up to `retries` times; then LINE is told (critical).

Order states: scheduled → sending → submitted → filled | partial | cancelled | failed | skipped
(unknown = the broker call failed: the bot looks the order up by its client order id before ever
sending a replacement). Everything that sends orders or books fills runs under one lock.
"""
from __future__ import annotations

import json
import logging
import math
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from . import brokers, db, ledger, marketdata as md, markethours as mh, notify, testtrade
from . import strategies as S

log = logging.getLogger("execution")
OPEN = ("scheduled", "sending", "submitted", "unknown")
WORKING = ("sending", "submitted", "unknown")
EQUITY_EVERY_S = 30 * 60
_LOCK = threading.RLock()


def _ts(dt):
    return int(dt.timestamp())


def _dt(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def _q(n):
    return ",".join("?" * n)


def _f(v, d):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def exec_cfg(strat, settings=None) -> dict:
    s = settings or db.get_settings()
    base = {"lots": int(_f(s.get("exec_lots"), 10)), "interval_min": _f(s.get("exec_interval_min"), 10),
            "start_mode": s.get("exec_start_mode", "time"), "start_time": s.get("exec_start_time", "22:00"),
            "exit_mode": s.get("exec_exit_mode", "asap"), "session": s.get("exec_session", "CORE")}
    if strat is not None:
        base.update({k: v for k, v in (strat.EXEC_DEFAULTS or {}).items() if v not in (None, "")})
        base.update({k: v for k, v in (strat.row.get("exec") or {}).items() if v not in (None, "")})
    base["lots"] = max(1, min(60, int(_f(base["lots"], 10))))
    base["interval_min"] = max(0.5, min(120, _f(base["interval_min"], 10)))
    if base["session"] not in ("CORE", "ALL"):
        base["session"] = "CORE"
    base.update({"offset": _f(s.get("exec_limit_offset_pct"), 0.10) / 100, "retries": int(_f(s.get("exec_retries"), 3)),
                 "min_lot_usd": _f(s.get("exec_min_lot_usd"), 200), "min_trade_usd": _f(s.get("exec_min_trade_usd"), 100),
                 "max_order_usd": _f(s.get("exec_max_order_usd"), 25000)})
    return base


def describe_cfg(c) -> str:
    when = f"from {c['start_time']} BKK" if c["start_mode"] == "time" else "from the market open"
    return f"{c['lots']} lots × {c['interval_min']:g} min {when}"


# ---------------------------------------------------------------- plans
def active_plan(mode, sid):
    return db.one("SELECT * FROM plans WHERE mode=? AND strategy=? AND status='active' ORDER BY id DESC LIMIT 1", (mode, sid))


def _split(q: int, n: int) -> list:
    base, rem = divmod(int(q), n)
    return [base + (1 if k < rem else 0) for k in range(n)]


def _insert_order(c, plan_id, mode, sid, step, lot, lots, symbol, side, when, session, plan_qty=None, retry=0, qty=None):
    c.execute("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,session,scheduled_at,status,updated_at,retry) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (plan_id, mode, sid, step, lot, lots, symbol, side, qty, plan_qty, session, _ts(when), "scheduled", int(time.time()), retry))


def build_plan(mode, strat, target: dict, reason: str, now, broker=None, buys=True, sell_override: dict | None = None,
               on_done: dict | None = None, note: str = "", signal_id=None, settings=None, goal: dict | None = None):
    """Create a plan that moves `strat` toward `target`. Returns plan id, or None when nothing needs trading."""
    c_ = exec_cfg(strat, settings)
    broker = broker or brokers.get(mode)
    L = ledger.get(mode, strat.id)
    syms = set(L["holdings"]) | set(target)
    px = {}
    for s in syms:
        try:
            px[s] = broker.quote(s)["price"]
        except Exception as e:
            log.warning("plan %s: no price for %s: %s", strat.id, s, e)
            return None
    E = ledger.tradable_cash(L) + sum(q * px[s] for s, q in L["holdings"].items())   # cash waiting for a buy signal left out
    sells = {}
    if sell_override is not None:
        sells = {s: int(q) for s, q in sell_override.items() if int(q) >= 1}
    else:
        for s, held in L["holdings"].items():
            keep = math.floor(target.get(s, 0) * E / px[s]) if s in target else 0
            q = int(math.floor(held - keep + 1e-9))
            if q >= 1 and (q * px[s] >= c_["min_trade_usd"] or s not in target):
                sells[s] = q
    need = {}
    if buys:
        for s, w in target.items():
            v = w * E - L["holdings"].get(s, 0) * px[s]
            if v >= max(c_["min_trade_usd"], px[s]):
                need[s] = v
    if not sells and not need:
        return None
    sell_v = sum(q * px[s] for s, q in sells.items())
    trade_v = max(sell_v, sum(need.values()))
    lots = max(1, min(c_["lots"], int(trade_v // max(1.0, c_["min_lot_usd"]))))
    cash_like = set(strat.cash_target()) | {strat.params.get("off_symbol")} - {None}
    exitish = not need or all(s in cash_like for s in need) or reason in ("stop", "withdraw", "move")
    smode = c_["start_mode"] if (not exitish or c_["exit_mode"] == "same") else "asap"
    sess = c_["session"]
    start = mh.start_time(now, smode, c_["start_time"], sess)
    resume = (lambda t: mh.start_time(t, smode, c_["start_time"], sess)) if smode == "time" else None
    times = mh.spread_lots(start, lots, c_["interval_min"], sess, resume)
    with db.tx() as c:
        cur = c.execute("INSERT INTO plans(mode,strategy,reason,status,created_at,start_at,target,note,on_done,lots,interval_min,signal_id,goal) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (mode, strat.id, reason, "active", int(time.time()), _ts(start), json.dumps(target), note,
                         json.dumps(on_done) if on_done else None, lots, c_["interval_min"], signal_id,
                         json.dumps(goal) if goal is not None else None))
        pid = cur.lastrowid
        split = {s: _split(q, lots) for s, q in sells.items()}
        for k, t in enumerate(times):
            for s in sorted(sells):
                if split[s][k] >= 1:
                    _insert_order(c, pid, mode, strat.id, 2 * k, k + 1, lots, s, "SELL", t, sess, plan_qty=split[s][k])
            for s in sorted(need, key=lambda x: -need[x]):
                _insert_order(c, pid, mode, strat.id, 2 * k + 1, k + 1, lots, s, "BUY", t, sess)
    parts = [f"sell {q} {s}" for s, q in sells.items()] + [f"buy ≈${v:,.0f} {s}" for s, v in need.items()]
    db.add_event("info", "orders", f"{strat.name}: plan created ({reason})",
                 f"{', '.join(parts)} · {lots} lot(s) every {c_['interval_min']:g} min from {local(start)}", strategy=strat.id, mode=mode)
    return pid


def local(dt) -> str:
    return dt.astimezone(mh.BKK).strftime("%a %d %b %H:%M")


def cancel_plan(plan_id, reason="cancelled", broker=None) -> bool:
    with _LOCK:
        p = db.one("SELECT * FROM plans WHERE id=?", (plan_id,))
        if not p or p["status"] != "active":
            return False
        try:
            broker = broker or brokers.get(p["mode"])
        except Exception:
            broker = None
        for o in db.rows("SELECT * FROM orders WHERE plan_id=? AND status IN ('submitted','unknown')", (plan_id,)):
            try:
                if broker and o["client_order_id"]:
                    broker.cancel(o["client_order_id"])
            except Exception as e:
                log.warning("cancel %s: %s", o["client_order_id"], e)
        now = int(time.time())
        with db.tx() as c:
            c.execute("UPDATE orders SET status='cancelled', error=?, updated_at=? WHERE plan_id=? AND status='scheduled'",
                      (reason, now, plan_id))
            c.execute("UPDATE plans SET status='cancelled', note=COALESCE(note,'') || ?, finished_at=? WHERE id=?",
                      (f" · {reason}", now, plan_id))
            c.execute("UPDATE money SET status='cancelled', note=COALESCE(note,'') || ' · plan cancelled' WHERE plan_id=? AND status='pending'",
                      (plan_id,))
        db.add_event("warn", "orders", f"Plan #{plan_id} cancelled", reason, strategy=p["strategy"], mode=p["mode"])
        return True


def start_now(plan_id) -> bool:
    with _LOCK:
        p = db.one("SELECT * FROM plans WHERE id=? AND status='active'", (plan_id,))
        if not p:
            return False
        rows = db.rows("SELECT id, step FROM orders WHERE plan_id=? AND status='scheduled' ORDER BY step, id", (plan_id,))
        sess = "CORE"
        start = mh.next_open(md.now_utc(), sess)
        rounds = sorted({r["step"] // 2 for r in rows})
        times = mh.spread_lots(start, len(rounds), p["interval_min"] or 10, sess) if rounds else []
        when = dict(zip(rounds, times))
        with db.tx() as c:
            for r in rows:
                c.execute("UPDATE orders SET scheduled_at=?, updated_at=? WHERE id=?", (_ts(when[r["step"] // 2]), int(time.time()), r["id"]))
            c.execute("UPDATE plans SET start_at=? WHERE id=?", (_ts(start), plan_id))
        return True


def respace(plan_id, new_start, interval, session):
    rows = db.rows("SELECT id, step FROM orders WHERE plan_id=? AND status='scheduled' ORDER BY step, scheduled_at, id", (plan_id,))
    if not rows:
        return
    rounds = sorted({r["step"] // 2 for r in rows})
    times = dict(zip(rounds, mh.spread_lots(new_start, len(rounds), interval, session)))
    with db.tx() as c:
        for r in rows:
            c.execute("UPDATE orders SET scheduled_at=MAX(scheduled_at, ?), updated_at=? WHERE id=?",
                      (_ts(times[r["step"] // 2]), int(time.time()), r["id"]))


# ---------------------------------------------------------------- sending
def _pending_sell(mode, symbol, sid=None):
    q = (f"SELECT COALESCE(SUM(COALESCE(qty,0)-COALESCE(applied_qty,0)),0) q FROM orders WHERE mode=? AND symbol=? AND side='SELL' "
         f"AND status IN ({_q(len(WORKING))})")
    args = [mode, symbol, *WORKING]
    if sid:
        q += " AND strategy=?"
        args.append(sid)
    return db.one(q, tuple(args))["q"]


def _pending_buy(mode, sid, symbol=None):
    q = (f"SELECT COALESCE(SUM((COALESCE(qty,0)-COALESCE(applied_qty,0))*COALESCE(limit_price,0)),0) v FROM orders "
         f"WHERE mode=? AND strategy=? AND side='BUY' AND status IN ({_q(len(WORKING))})")
    args = [mode, sid, *WORKING]
    if symbol:
        q += " AND symbol=?"
        args.append(symbol)
    return db.one(q, tuple(args))["v"]


def _limit(q, side, offset):
    if side == "BUY":
        return round((q.get("ask") or q["price"]) * (1 + offset), 2)
    return round((q.get("bid") or q["price"]) * (1 - offset), 2)


def _claim(oid, cid):
    with db.tx() as c:
        n = c.execute("UPDATE orders SET status='sending', client_order_id=?, submitted_at=?, updated_at=? WHERE id=? AND status='scheduled'",
                      (cid, int(time.time()), int(time.time()), oid)).rowcount
    return n == 1


def _release(oid):
    db.run("UPDATE orders SET status='scheduled', client_order_id=NULL, submitted_at=NULL WHERE id=? AND status='sending'", (oid,))


FEE_RESERVE = 0.0011            # Webull TH: 0.10% + 7% VAT per trade


def _buy_qty(mode, strat, plan, o, limit, broker, cash_buffer):
    """Size a buy lot: free cash shared across the plan's buy symbols by what each still needs, spread over the lots left."""
    L = ledger.get(mode, strat.id)
    target = json.loads(plan["target"] or "{}")
    buys = [r["symbol"] for r in db.rows("SELECT DISTINCT symbol FROM orders WHERE plan_id=? AND side='BUY'", (plan["id"],))]
    px = {}
    for s in set(L["holdings"]) | set(buys):
        px[s] = limit if s == o["symbol"] else broker.quote(s)["price"]
    cash = ledger.tradable_cash(L)
    E = cash + sum(q * px[s] for s, q in L["holdings"].items())
    need = {}
    for s in buys:
        need[s] = max(0.0, target.get(s, 0) * E - L["holdings"].get(s, 0) * px[s] - _pending_buy(mode, strat.id, s))
    cash_keep = max(0.0, (1 - sum(target.values())) * E) if target else 0.0
    free = max(0.0, cash - _pending_buy(mode, strat.id) - cash_keep * 0.5)
    tot = sum(need.values())
    if tot <= 0 or free <= 0:
        return 0
    alloc = min(need[o["symbol"]], free * need[o["symbol"]] / tot)
    left = db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND symbol=? AND side='BUY' AND status IN ('scheduled','sending')",
                  (plan["id"], o["symbol"]))["n"]
    value = alloc / max(1, left)
    if limit <= 0:
        return 0
    q = int(math.floor(value / limit))
    # last lot: whole shares leave up to one share of cash unbought (a $380 ETF on $10,000 = 3.8%). Round to the nearest
    # share when the extra one still fits in the free cash with Webull's fee (0.107%) on top.
    if left <= 1 and value - q * limit > 0.5 * limit and (q + 1) * limit * (1 + FEE_RESERVE) <= free:
        q += 1
    return q


class Guard:
    """Hard limit for buys, checked against Webull's own numbers right before each order:
      1. the bot's cash in its books (strategies + bot unassigned) must not be more than the account's cash;
      2. after the order, account cash must stay at or above the protected floor (Money page);
      3. the order must fit in Webull's buying power.
    Any money that is not the bot's therefore stays untouched even if the books were wrong."""

    def __init__(self, mode, acct, settings):
        self.mode, self.ok = mode, acct is not None and acct.get("cash") is not None
        self.cash = float(acct["cash"]) if self.ok else None
        bp = (acct or {}).get("buying_power")
        self.bp = float(bp) if bp is not None else None
        try:
            self.floor = max(0.0, float(settings.get(f"protect_floor_{mode}") or 0))
        except ValueError:
            self.floor = 0.0
        self.bot_cash = ledger.bot_cash(mode) if self.ok else None

    def allow(self, value):
        """(allowed_value, reason). allowed_value may be smaller than asked; 0 = block."""
        if not self.ok:
            return 0.0, "cannot read the account cash"
        if self.bot_cash > self.cash + 1.0:
            return 0.0, (f"the bot's books show ${self.bot_cash:,.2f} cash but the account has ${self.cash:,.2f} "
                         "(money left the account?)")
        room = self.cash - self.floor
        if self.bp is not None:
            room = min(room, self.bp)
        if room <= 0:
            return 0.0, f"account cash ${self.cash:,.2f} is at the protected floor ${self.floor:,.2f}"
        return min(value, room), (None if value <= room else f"only ${room:,.2f} above the protected floor / buying power")

    def spent(self, value):
        if self.ok:
            self.cash -= value
            self.bot_cash -= value
            if self.bp is not None:
                self.bp -= value


def _blocked(mode, o, strat, why):
    db.run("UPDATE orders SET status='skipped', qty=0, error=?, updated_at=? WHERE id=?",
           (f"blocked by the money guard: {why}"[:300], int(time.time()), o["id"]))
    db.add_event("error", "orders", f"Buy blocked: {o['symbol']} for {strat.name}", why, strategy=strat.id, mode=mode)
    db.set_state(f"guard_block:{mode}", {"at": int(time.time()), "why": why})
    last = db.get_state(f"guard_alert:{mode}", 0)
    if time.time() - last > 3600:
        notify.send("lot_failed", f"{brokers.MODE_LABEL[mode]} · BUY BLOCKED by the money guard: {why}. "
                    "No money outside the bot's allocation was used. Check the Money page.", critical=True)
        db.set_state(f"guard_alert:{mode}", int(time.time()))


def send_due(mode, now, broker, settings, positions=None, acct=None):
    if settings.get("trading_paused") == "1":
        return []
    guard = Guard(mode, acct, settings) if acct is not None or mode != "paper" else None
    due = db.rows("SELECT * FROM orders WHERE mode=? AND status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at, step, id",
                  (mode, _ts(now)))
    sent = []
    for o in due:
        o = db.one("SELECT * FROM orders WHERE id=?", (o["id"],))
        if o["status"] != "scheduled":
            continue
        plan = db.one("SELECT * FROM plans WHERE id=?", (o["plan_id"],))
        if not plan or plan["status"] != "active":
            continue
        if db.one(f"SELECT COUNT(*) n FROM orders WHERE plan_id=? AND step<? AND status IN ({_q(len(OPEN))})",
                  (o["plan_id"], o["step"], *OPEN))["n"]:
            continue                               # this round's sells (or the previous round) first
        strat = S.get(o["strategy"])
        if strat is None:
            continue
        c_ = exec_cfg(strat, settings)
        sess = o["session"] or c_["session"]
        close = mh.current_close(now, sess)
        if close is None or (close - now) < timedelta(minutes=3):
            respace(o["plan_id"], mh.next_open(now + timedelta(minutes=5), sess), plan["interval_min"] or c_["interval_min"], sess)
            continue
        cid = f"tsb{mode[0]}{o['plan_id']}x{o['id']}r{o['retry']}{secrets.token_hex(2)}"[:32]
        if not _claim(o["id"], cid):
            continue
        try:
            q = broker.quote(o["symbol"])
            limit = _limit(q, o["side"], c_["offset"])
        except Exception as e:
            _release(o["id"])
            log.warning("no price for %s: %s (next minute)", o["symbol"], e)
            continue
        L = ledger.get(mode, o["strategy"])
        if o["side"] == "SELL":
            held = L["holdings"].get(o["symbol"], 0.0)
            avail = max(0.0, held - _pending_sell(mode, o["symbol"], o["strategy"]))
            if positions is not None:
                real = ((positions.get(o["symbol"]) or {}).get("qty") or 0.0) - _pending_sell(mode, o["symbol"])
                avail = min(avail, max(0.0, real))
            want = o["qty"] if o["qty"] else o["plan_qty"]
            last_lot = not db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND symbol=? AND side='SELL' AND status='scheduled' AND id<>?",
                                  (o["plan_id"], o["symbol"], o["id"]))["n"]
            qty = math.floor(avail) if (last_lot and plan["reason"] in ("stop",)) else min(math.floor(avail), int(want or 0))
        else:
            try:
                qty = _buy_qty(mode, strat, plan, o, limit, broker, c_)
            except Exception as e:
                _release(o["id"])
                log.warning("sizing %s: %s", o["symbol"], e)
                continue
            if o["qty"]:
                qty = min(qty, int(o["qty"]))
        if c_["max_order_usd"] > 0 and qty * limit > c_["max_order_usd"]:
            qty = math.floor(c_["max_order_usd"] / limit)
        if o["side"] == "BUY" and guard is not None and qty >= 1:
            allowed, why = guard.allow(qty * limit)
            if allowed < qty * limit:
                q2 = int(math.floor(allowed / limit))
                if q2 < 1:
                    _blocked(mode, o, strat, why or "no room")
                    continue
                db.add_event("warn", "orders", f"Buy reduced by the money guard: {o['symbol']}", f"{qty} → {q2} shares · {why}",
                             strategy=strat.id, mode=mode)
                qty = q2
        if qty < 1:
            db.run("UPDATE orders SET status='skipped', qty=0, limit_price=?, error=?, updated_at=? WHERE id=?",
                   (limit, "nothing to trade (less than 1 share)", int(time.time()), o["id"]))
            continue
        db.run("UPDATE orders SET qty=?, limit_price=?, updated_at=? WHERE id=?", (qty, limit, int(time.time()), o["id"]))
        if o["lot"] == 1 and o["step"] in (0, 1) and o["retry"] == 0:
            first = db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND status NOT IN ('scheduled','skipped')", (o["plan_id"],))["n"]
            if first <= 1:
                notify.send("plan_start", f"{brokers.MODE_LABEL[mode]} · {strat.name}: plan started — {plan['lots']} lot(s) every "
                            f"{plan['interval_min']:g} min", strategy=strat.id)
        if o["side"] == "BUY" and guard is not None:
            guard.spent(qty * limit)
        try:
            res = broker.place(o["symbol"], o["side"], qty, limit, sess, cid)
            new, err = "submitted", None
            db.run("UPDATE orders SET broker_order_id=? WHERE id=?", (str((res or {}).get("order_id") or ""), o["id"]))
        except brokers.BrokerRejected as e:            # refused for sure: nothing was placed
            if o["side"] == "BUY" and guard is not None:
                guard.spent(-qty * limit)
            db.run("UPDATE orders SET status='failed', error=?, updated_at=? WHERE id=? AND status='sending'",
                   (f"refused: {e}"[:300], int(time.time()), o["id"]))
            sent.append(o["id"])
            if e.permanent:
                block_symbol(mode, o["symbol"], e.code, str(e), strat)
                cancel_plan(o["plan_id"], f"Webull refuses {o['symbol']}: {e.code}", broker)
            elif plan["status"] == "active":
                _retry(o, qty, now, f"refused: {e}", int(_f(settings.get("exec_retries"), 3)))
            continue
        except brokers.BrokerError as e:
            new, err = "unknown", str(e)[:300]
        db.run("UPDATE orders SET status=?, error=?, updated_at=? WHERE id=? AND status='sending'", (new, err, int(time.time()), o["id"]))
        sent.append(o["id"])
        poll(mode, now, broker, only_id=o["id"])
        if o["side"] == "SELL" and guard is not None and guard.ok:     # cash from a sale is the strategy's again
            got = db.one("SELECT COALESCE(applied_value,0) v FROM orders WHERE id=?", (o["id"],))["v"]
            guard.cash += got
            guard.bot_cash += got
    return sent


def _retry(o, qty_left, now, why, retries):
    strat_name = (S.row(o["strategy"]) or {}).get("name", o["strategy"])
    if o["retry"] + 1 > retries:
        notify.send("lot_failed", f"{brokers.MODE_LABEL[o['mode']]} · {strat_name}: {o['side']} {qty_left:.0f} {o['symbol']} failed "
                    f"{retries + 1} times ({why}). Please check Webull.", strategy=o["strategy"], critical=True)
        db.add_event("error", "orders", f"Lot failed: {o['side']} {qty_left:.0f} {o['symbol']}", why, strategy=o["strategy"], mode=o["mode"])
        return
    when = mh.next_open(now + timedelta(minutes=1), o["session"] or "CORE")
    with db.tx() as c:
        # one replacement per lot: skip when this order was already retried, or another order for the same lot is still open
        # (an old order whose status is read late — e.g. after a restart — must not add a second copy of the lot)
        dup = c.execute(f"SELECT COUNT(*) n FROM orders WHERE plan_id=? AND step=? AND symbol=? AND side=? AND id<>? "
                        f"AND (retry>? OR status IN ({_q(len(OPEN))}))",
                        (o["plan_id"], o["step"], o["symbol"], o["side"], o["id"], o["retry"], *OPEN)).fetchone()["n"]
        if dup:
            return
        _insert_order(c, o["plan_id"], o["mode"], o["strategy"], o["step"], o["lot"], o["lots"], o["symbol"], o["side"], when,
                      o["session"], plan_qty=qty_left, retry=o["retry"] + 1, qty=qty_left)


# ---------------------------------------------------------------- symbols the broker refuses


def _session_over(o, now) -> bool:
    """Has the trading session this order was sent in closed (plus 5 minutes)?"""
    sent = _dt(o["submitted_at"] or _ts(now))
    close = mh.current_close(sent, o["session"] or "CORE")
    if close is None:                                      # sent outside the session: the next one counts
        nxt = mh.next_open(sent, o["session"] or "CORE")
        close = mh.current_close(nxt, o["session"] or "CORE")
    return close is not None and now >= close + timedelta(minutes=5)


def blocked_symbols(mode) -> dict:
    b = db.get_state(f"blocked_sym:{mode}") or {}
    return b                    # kept until you press "try again" (Orders) or a Test trade of the symbol passes


def single_stock_etfs() -> set:
    """Every single-stock leveraged ETF the strategies know (the 2x ETF lists of the momentum strategies)."""
    out = set()
    for s in S.all_instances():
        if hasattr(s, "etf_map"):
            out |= set(s.etf_map().values())
    return out


def single_stock_refused(mode) -> bool:
    """Webull refused a single-stock leveraged ETF for this account (needs 50M THB+): a rule for the account, not one ETF."""
    return any((v or {}).get("code") == brokers.SINGLE_STOCK_LEV_CODE for v in blocked_symbols(mode).values())


def block_symbol(mode, symbol, code, msg, strat=None):
    b = blocked_symbols(mode)
    first = symbol not in b
    b[symbol] = {"code": code, "msg": msg[:300], "at": int(time.time()), "hint": brokers.PERMANENT_HINTS.get(code, "")}
    if code == brokers.SINGLE_STOCK_LEV_CODE:           # an account rule: every single-stock 2x ETF is refused, not only this one
        for x in single_stock_etfs() - set(b):
            b[x] = {"code": code, "msg": f"same Webull rule as {symbol}", "at": int(time.time()),
                    "hint": brokers.PERMANENT_HINTS.get(code, ""), "rule": True}
    db.set_state(f"blocked_sym:{mode}", b)
    if first:
        name = strat.name if strat else ""
        db.add_event("error", "orders", f"Webull refuses {symbol}", f"{msg} · {brokers.PERMANENT_HINTS.get(code, '')}",
                     strategy=strat.id if strat else None, mode=mode)
        tail = (" The bot now holds the stocks themselves instead of their 2x ETFs, in this mode." if code == brokers.SINGLE_STOCK_LEV_CODE
                else f" The bot stops trading {symbol} until you fix it and press 'Try again' on the Orders page (or a Test trade of it passes).")
        notify.send("lot_failed", f"{brokers.MODE_LABEL[mode]} · Webull refuses {symbol}{' (' + name + ')' if name else ''}: {msg}\n"
                    f"{brokers.PERMANENT_HINTS.get(code, '')}{tail}",
                    strategy=strat.id if strat else None, critical=True)


def unblock_symbols(mode):
    db.set_state(f"blocked_sym:{mode}", {})


def poll(mode, now, broker, only_id=None, settings=None):
    settings = settings or db.get_settings()
    retries = int(_f(settings.get("exec_retries"), 3))
    q = f"SELECT * FROM orders WHERE mode=? AND status IN ({_q(len(WORKING))})" + (" AND id=?" if only_id else "")
    args = (mode, *WORKING, only_id) if only_id else (mode, *WORKING)
    for o in db.rows(q, args):
        plan = db.one("SELECT * FROM plans WHERE id=?", (o["plan_id"],))
        err = o["error"] or ""
        # only a refused PLACE settles an order; a refused CANCEL ("status cannot be modified") means the order is
        # already final at Webull (filled or cancelled): its real status is read below
        rej = brokers.parse_rejection(err) if "HTTP Status" in err and "place order" in err and not err.startswith("cancel failed") else None
        if rej and o["status"] in ("unknown", "submitted") and not (o["applied_qty"] or 0):
            # an older bot version kept refused orders open: settle them now
            db.run("UPDATE orders SET status='failed', error=?, updated_at=? WHERE id=?", (f"refused: {rej}"[:300], int(time.time()), o["id"]))
            if rej.permanent:
                block_symbol(mode, o["symbol"], rej.code, str(rej), S.get(o["strategy"]))
                if plan and plan["status"] == "active":
                    cancel_plan(plan["id"], f"Webull refuses {o['symbol']}: {rej.code}", broker)
            elif plan and plan["status"] == "active":
                _retry(o, o["qty"] or 0, now, f"refused: {rej}", retries)
            continue
        interval = (plan or {}).get("interval_min") or 10
        timeout = timedelta(minutes=max(2.0, interval - 0.5))
        age = now - _dt(o["submitted_at"] or _ts(now))
        if o["status"] == "sending" and age < timedelta(minutes=2):
            continue
        try:
            st = broker.order(o["client_order_id"])
        except brokers.BrokerError as e:
            if o["status"] in ("unknown", "sending") or "not found" in str(e):
                checks = (o["checks"] or 0) + 1
                db.run("UPDATE orders SET checks=?, error=?, updated_at=? WHERE id=?", (checks, str(e)[:300], int(time.time()), o["id"]))
                if checks >= 3 and age >= timedelta(minutes=3):
                    db.run("UPDATE orders SET status='failed', updated_at=? WHERE id=?", (int(time.time()), o["id"]))
                    if plan and plan["status"] == "active":
                        _retry(o, o["qty"] or 0, now, f"not placed: {e}", retries)
            else:
                log.warning("order status %s: %s", o["client_order_id"], e)
            continue
        filled = float(st.get("filled_qty") or 0)
        avg = st.get("avg_price") or o["limit_price"] or 0
        dq = filled - (o["applied_qty"] or 0)
        if dq > 1e-9:
            dv = filled * avg - (o["applied_value"] or 0)
            with db.tx() as c:
                n = c.execute("UPDATE orders SET applied_qty=?, applied_value=? WHERE id=? AND applied_qty=?",
                              (filled, filled * avg, o["id"], o["applied_qty"] or 0)).rowcount
            if n == 1:
                ledger.book_fill(mode, o["strategy"], o["symbol"], o["side"], dq, dv)
                notify.send("lot_filled", f"{brokers.MODE_LABEL[mode]} · {o['side']} {dq:.0f} {o['symbol']} @ ${avg:,.2f} "
                            f"(lot {o['lot']}/{o['lots']})", strategy=o["strategy"])
        fee = float(st.get("fee") or 0.0)
        if fee > (o["fee"] or 0) + 1e-9:                  # broker fees come out of the strategy's cash, not yours
            with db.tx() as c:
                n = c.execute("UPDATE orders SET fee=? WHERE id=? AND COALESCE(fee,0)=?", (fee, o["id"], o["fee"] or 0)).rowcount
                if n == 1:
                    c.execute("UPDATE ledger SET cash=cash-?, updated_at=? WHERE mode=? AND strategy=?",
                              (fee - (o["fee"] or 0), int(time.time()), mode, o["strategy"]))
        status = (st.get("status") or "SUBMITTED").upper()
        new = None
        if status == "FILLED":
            new = "filled"
        elif status in ("CANCELLED", "CANCELED", "FAILED", "REJECTED", "EXPIRED"):
            new = "partial" if filled > 0 else ("cancelled" if status in ("CANCELLED", "CANCELED", "EXPIRED") else "failed")
        else:
            new = "submitted" if o["status"] != "submitted" else None
            close = mh.current_close(now, o["session"] or "CORE")
            stop = age > timeout or close is None or (close - now) < timedelta(minutes=2) or not plan or plan["status"] != "active"
            if stop:
                try:
                    broker.cancel(o["client_order_id"])
                except brokers.BrokerError as e:
                    log.warning("cancel %s: %s", o["client_order_id"], e)
                    if "CANNOT_OPERATE" in str(e) and _session_over(o, now):
                        # a DAY order cannot fill after its session closed: it expired, whatever Webull's detail says
                        new = "partial" if filled > 0 else "cancelled"
                        db.run("UPDATE orders SET error=? WHERE id=?",
                               ("expired: day order from a closed session (Webull would not cancel it)", o["id"]))
                        db.add_event("info", "orders", f"Old order treated as expired: {o['side']} {o['qty']:.0f} {o['symbol']}",
                                     f"Sent {local(_dt(o['submitted_at'] or _ts(now)))}; its trading session is over, so it can no "
                                     f"longer fill. Filled before: {filled:.0f}.", strategy=o["strategy"], mode=mode)
                        status = "EXPIRED"
                    else:
                        checks = (o["checks"] or 0) + 1
                        db.run("UPDATE orders SET checks=?, error=? WHERE id=?", (checks, f"cancel failed: {e}"[:300], o["id"]))
                        if checks == 5:
                            notify.send("lot_failed", f"{brokers.MODE_LABEL[mode]} · Could not cancel {o['side']} {o['qty']:.0f} "
                                        f"{o['symbol']} (lot {o['lot']}/{o['lots']}): {e}. The bot will not send a replacement "
                                        "while it may still be open. Please check it in the Webull app.", strategy=o["strategy"], critical=True)
        db.run("UPDATE orders SET filled_qty=?, avg_price=?, status=COALESCE(?,status), updated_at=? WHERE id=?",
               (filled, avg if filled else o["avg_price"], new, int(time.time()), o["id"]))
        if new in ("partial", "cancelled", "failed"):
            left = (o["qty"] or 0) - filled
            if left >= 1 and plan and plan["status"] == "active":
                _retry(o, left, now, f"order {status.lower()} with {left:.0f} left", retries)


def dedupe_retries() -> int:
    """Keep one waiting order per lot. Bot 1.0's one-time re-check (repair_cancel_refusals) could give a lot several
    replacement orders when old orders were read as expired after the session; they would all have been sent at the
    next open. The newest attempt of each lot stays, the extra copies are marked skipped."""
    rows = db.rows("SELECT o.id, o.plan_id, o.step, o.symbol, o.side, o.retry, o.mode, o.strategy FROM orders o JOIN plans p ON p.id=o.plan_id "
                   "WHERE p.status='active' AND o.status='scheduled' ORDER BY o.plan_id, o.step, o.symbol, o.side, o.retry DESC, o.id DESC")
    seen, extra = set(), []
    for r in rows:
        k = (r["plan_id"], r["step"], r["symbol"], r["side"])
        if k in seen:
            extra.append(r)
        else:
            seen.add(k)
    if extra:
        with db.tx() as c:
            for r in extra:
                c.execute("UPDATE orders SET status='skipped', qty=0, error=?, updated_at=? WHERE id=?",
                          ("duplicate replacement for the same lot (removed)", int(time.time()), r["id"]))
        for (mode, sid), n in {(r["mode"], r["strategy"]): sum(1 for x in extra if (x["mode"], x["strategy"]) == (r["mode"], r["strategy"]))
                               for r in extra}.items():
            db.add_event("warn", "orders", f"Removed {n} duplicate waiting order(s)",
                         "Several replacement orders were waiting for the same lot; only the newest one is kept, so the lot is "
                         "bought or sold once.", strategy=sid, mode=mode)
    return len(extra)


def repair_cancel_refusals():
    """Bot 1.0 (24 Oct) wrongly marked orders as refused when Webull refused to CANCEL them (OPENAPI_ORDER_CANNOT_OPERATE,
    i.e. the order was already final). Read those orders again so a fill that really happened is booked."""
    if db.get_state("repair_cancel_refusals"):
        return 0
    rows = db.rows("SELECT id FROM orders WHERE status='failed' AND error LIKE '%ORDER_CANNOT_OPERATE%' AND client_order_id IS NOT NULL "
                   "AND COALESCE(applied_qty,0)=0")
    for r in rows:
        db.run("UPDATE orders SET status='submitted', checks=0, error='re-checking (was marked refused by mistake)' WHERE id=?", (r["id"],))
    db.set_state("repair_cancel_refusals", int(time.time()))
    if rows:
        db.add_event("warn", "orders", f"Re-checking {len(rows)} order(s) wrongly marked refused",
                     "Webull had refused to cancel them because they were already final; their real status is read again and any fill is booked.")
    return len(rows)


def finish_plans(mode):
    for p in db.rows("SELECT * FROM plans WHERE mode=? AND status='active'", (mode,)):
        if db.one(f"SELECT COUNT(*) n FROM orders WHERE plan_id=? AND status IN ({_q(len(OPEN))})", (p["id"], *OPEN))["n"]:
            continue
        rows = db.rows("SELECT * FROM orders WHERE plan_id=? AND filled_qty>0", (p["id"],))
        parts = {}
        for o in rows:
            k = (o["side"], o["symbol"])
            q, v = parts.get(k, (0.0, 0.0))
            parts[k] = (q + o["filled_qty"], v + o["filled_qty"] * (o["avg_price"] or 0))
        summary = [{"side": s, "symbol": sym, "qty": q, "avg": v / q if q else None, "value": v} for (s, sym), (q, v) in parts.items()]
        retried = db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND retry>0", (p["id"],))["n"]
        db.run("UPDATE plans SET status='done', finished_at=?, summary=? WHERE id=?",
               (int(time.time()), json.dumps({"fills": summary, "retried": retried}), p["id"]))
        strat = S.get(p["strategy"])
        name = strat.name if strat else p["strategy"]
        if p["reason"] not in ("withdraw", "move"):
            ledger.set_applied_target(mode, p["strategy"], json.loads(p.get("goal") or p["target"] or "{}"))
        od = json.loads(p["on_done"] or "null")
        if od:
            _on_done(mode, p, od)
        if p["reason"] == "stop":
            row = S.row(p["strategy"])
            if row and row["control"] == "stopping":
                S.update(p["strategy"], control="stopped")
        txt = "\n".join(f"{x['side']} {x['qty']:.0f} {x['symbol']} @ ${x['avg']:,.2f} avg" for x in summary if x["qty"])
        db.add_event("info", "orders", f"{name}: plan #{p['id']} done", txt or "nothing filled", strategy=p["strategy"], mode=mode)
        if summary:
            notify.send("plan_done", f"{brokers.MODE_LABEL[mode]} · {name} · plan done ({p['reason']})\n{txt}"
                        + (f"\n{retried} lot(s) needed a retry" if retried else ""), strategy=p["strategy"])


def _on_done(mode, plan, od):
    from . import moneyops
    try:
        moneyops.after_plan(mode, plan, od)
    except Exception as e:
        log.exception("after plan")
        db.add_event("error", "money", "Money step after plan failed", str(e), strategy=plan["strategy"], mode=mode)


# ---------------------------------------------------------------- deciding when to trade
def _drift(mode, strat, target, prices):
    w, tot = ledger.weights(mode, strat.id, prices)
    if tot <= 0:
        return 0.0
    keys = set(w) | set(target)
    return max((abs(w.get(k, 0.0) - target.get(k, 0.0)) for k in keys), default=0.0)


def waiting_for_buy(mode, strat, L=None):
    """None if the strategy may buy; else the time since when it has been waiting for its next BUY signal."""
    L = L or ledger.get(mode, strat.id)
    since = L.get("hold_cash") or 0
    if not since:
        return None
    for sig in db.rows("SELECT * FROM signals WHERE strategy=? AND t>? ORDER BY t", (strat.id, since)):
        if strat.is_buy_signal(sig):
            return None
    return since


def reconcile(mode, strat, ev, now, broker, settings):
    """Start, keep or replace this strategy's plan so its holdings follow its target."""
    if not ev or not ev.get("ok"):
        return None
    row = strat.row
    control = row.get("control", "active")
    if control == "stopped":
        return None
    L = ledger.get(mode, strat.id)
    if (L["cap_in"] or 0) <= 0 and L["cash"] <= 0 and not L["holdings"]:
        return None
    target = dict(ev["target"])
    if hasattr(strat, "fallback_for"):                  # e.g. a 2x ETF Webull refuses → hold the stock itself
        blk0 = blocked_symbols(mode)
        for sym in [x for x in target if x in blk0]:
            alt = strat.fallback_for(sym)
            if alt and alt not in blk0:
                target[alt] = round(target.get(alt, 0) + target.pop(sym), 4)
    reason = "signal"
    buys = control == "active"
    if control == "stopping":
        target, reason, buys = {}, "stop", False
    if L["hold_cash"] and control == "active" and waiting_for_buy(mode, strat, L) is None:
        # "Add money → wait for the next BUY signal": the buy came, so the waiting cash joins the strategy now
        amt = ledger.waiting_cash(L)
        ledger.end_wait(mode, strat.id)
        L = ledger.get(mode, strat.id)
        db.add_event("info", "money", f"{strat.name}: buy signal — ${amt:,.2f} waiting cash is invested now", "", strategy=strat.id, mode=mode)
        notify.send("money", f"{brokers.MODE_LABEL[mode]} · {strat.name}: buy signal, so the ${amt:,.2f} that was waiting in cash "
                    "is invested now.", strategy=strat.id)
        ap0 = active_plan(mode, strat.id)
        if ap0 and ap0["reason"] not in ("withdraw", "move"):
            cancel_plan(ap0["id"], "waiting cash joins the plan", broker)   # re-plan with all the money
        ledger.set_applied_target(mode, strat.id, None)
    ap = active_plan(mode, strat.id)
    tkey = json.dumps(target, sort_keys=True)
    if ap:
        if ap["reason"] in ("withdraw", "move") or json.dumps(json.loads(ap.get("goal") or ap["target"] or "{}"), sort_keys=True) == tkey:
            return None
        cancel_plan(ap["id"], "the target changed", broker)
    applied = L["applied_target"]
    changed = applied is None or json.dumps(json.loads(applied), sort_keys=True) != tkey
    if not changed:
        cool = db.get_state(f"noplan:{mode}:{strat.id}")
        if cool and cool.get("k") == tkey and time.time() - cool.get("t", 0) < 1800:
            return None
        syms = set(L["holdings"]) | set(target)
        prices = md.prices(syms)
        if any(prices.get(s) is None for s in syms):
            return None
        if _drift(mode, strat, target, prices) <= strat.rebalance_band():
            return None
        reason = "rebalance" if reason == "signal" else reason
    blk = blocked_symbols(mode)
    if buys and any(s in blk for s in target if target.get(s, 0) > 0):
        return None                                     # Webull refuses one of the target symbols: wait (see block_symbol)
    goal = None
    if buys and hasattr(strat, "adjust_target"):
        # basket strategies keep what they hold (no top-ups / trims) and only buy what is new; the plan remembers the goal
        syms = set(L["holdings"]) | set(target)
        prices = md.prices(syms) if syms else {}
        if any(prices.get(s) is None for s in syms):
            return None
        w, _ = ledger.weights(mode, strat.id, prices)
        goal, target = target, strat.adjust_target(target, w)
    pid = build_plan(mode, strat, target, reason, now, broker, buys=buys, settings=settings, goal=goal)
    if pid is None:
        if changed:
            ledger.set_applied_target(mode, strat.id, goal if goal is not None else target)
        db.set_state(f"noplan:{mode}:{strat.id}", {"k": tkey, "t": int(time.time())})
    return pid


# ---------------------------------------------------------------- equity + benchmark
def record_equity(mode, now=None, force=False):
    key = f"eq_last:{mode}"
    if not force and time.time() - (db.get_state(key) or 0) < EQUITY_EVERY_S:
        return None
    t = _ts(now or md.now_utc())
    led = ledger.all_for(mode)
    if not led:
        return None
    syms = set()
    strats = {s.id: s for s in S.all_instances(include_archived=True)}
    for sid, L in led.items():
        syms |= set(L["holdings"])
        if sid in strats and strats[sid].benchmark_symbol():
            syms.add(strats[sid].benchmark_symbol())
    prices = md.prices(syms)
    bench = db.get_state(f"bench:{mode}") or {}
    tot_v = tot_c = tot_b = 0.0
    rows = []
    for sid, L in led.items():
        net = (L["cap_in"] or 0) - (L["cap_out"] or 0)
        v = L["cash"]
        for s, q in L["holdings"].items():
            if prices.get(s) is None:
                return None
            v += q * prices[s]
        b = bench.get(sid) or {}
        bs = strats[sid].benchmark_symbol() if sid in strats else None
        bpx = prices.get(bs) if bs else None
        if bs and bpx:
            if b.get("sym") != bs:
                b = {"sym": bs, "shares": 0.0, "net": 0.0}
            if abs(net - b.get("net", 0.0)) > 0.005:
                b["shares"] = max(0.0, b["shares"] + (net - b["net"]) / bpx)
                b["net"] = net
            bench[sid] = b
            bv = b["shares"] * bpx
        else:
            bv = net
        rows.append((mode, t, sid, v, net, bv))
        tot_v, tot_c, tot_b = tot_v + v, tot_c + net, tot_b + bv
    rows.append((mode, t, "*", tot_v, tot_c, tot_b))
    with db.tx() as c:
        c.executemany("INSERT OR REPLACE INTO equity(mode,t,strategy,value,capital,bench) VALUES(?,?,?,?,?,?)", rows)
    db.set_state(f"bench:{mode}", bench)
    db.set_state(key, int(time.time()))
    return tot_v


def equity_series(mode, sid="*", days=90, max_points=400):
    since = int(time.time()) - int(days * 86400)
    r = db.rows("SELECT t, value, capital, bench FROM equity WHERE mode=? AND strategy=? AND t>=? ORDER BY t", (mode, sid, since))
    step = max(1, math.ceil(len(r) / max_points))
    pts = r[::step]
    if r and pts[-1] is not r[-1]:
        pts.append(r[-1])
    return pts


# ---------------------------------------------------------------- the pass every tick
def process(now=None, settings=None):
    if not _LOCK.acquire(blocking=False):
        return {"busy": True}
    try:
        s = settings or db.get_settings()
        now = now or md.now_utc()
        out = {}
        try:
            repair_cancel_refusals()
            dedupe_retries()
        except Exception as e:
            log.warning("repair: %s", e)
        modes = brokers.enabled_modes(s)
        for m in brokers.MODES:
            busy = db.one(f"SELECT COUNT(*) n FROM orders WHERE mode=? AND status IN ({_q(len(OPEN))})", (m, *OPEN))["n"]
            if m not in modes and not busy and not testtrade.working(m):
                continue
            try:
                broker = brokers.get(m, s)
                ok, why = broker.ready()
                if not ok:
                    out[m] = {"ready": False, "why": why}
                    due = db.one("SELECT COUNT(*) n FROM orders WHERE mode=? AND status='scheduled' AND scheduled_at<=?", (m, _ts(now)))["n"]
                    last = db.get_state(f"not_ready_alert:{m}", 0)
                    if due and time.time() - last > 6 * 3600:
                        notify.send("broker", f"{brokers.MODE_LABEL[m]}: {due} lot(s) are due but Webull is not connected: {why}",
                                    critical=True)
                        db.set_state(f"not_ready_alert:{m}", int(time.time()))
                    continue
                poll(m, now, broker, settings=s)
                positions, acct = None, None
                due_sides = {r["side"] for r in db.rows("SELECT DISTINCT side FROM orders WHERE mode=? AND status='scheduled' "
                                                        "AND scheduled_at<=?", (m, _ts(now)))}
                if due_sides:
                    try:
                        acct = broker.account()            # fresh numbers for the money guard and the sell check
                        positions = (acct.get("positions") or {}) if m != "paper" else None
                    except brokers.BrokerError as e:
                        log.warning("account for the money guard: %s", e)
                        positions = {} if m != "paper" else None
                sent = send_due(m, now, broker, s, positions, acct)
                finish_plans(m)
                try:
                    testtrade.tick(m, now)
                except Exception as e:
                    log.warning("test trades %s: %s", m, e)
                try:
                    record_equity(m, now)
                except Exception as e:
                    log.warning("equity %s: %s", m, e)
                out[m] = {"ready": True, "sent": len(sent)}
            except Exception as e:
                log.exception("execution %s", m)
                out[m] = {"ready": False, "why": str(e)}
        db.set_state("exec_last", int(time.time()))
        return out
    finally:
        _LOCK.release()


def plans_view(mode, status=None, limit=30, sid=None):
    q, args = "SELECT * FROM plans WHERE mode=?", [mode]
    if status == "queued":
        q += " AND status='active' AND id NOT IN (SELECT plan_id FROM orders WHERE status NOT IN ('scheduled'))"
    elif status == "running":
        q += " AND status='active' AND id IN (SELECT plan_id FROM orders WHERE status NOT IN ('scheduled'))"
    elif status == "done":
        q += " AND status IN ('done','cancelled')"
    if sid:
        q += " AND strategy=?"
        args.append(sid)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    out = db.rows(q, tuple(args))
    names = {r["id"]: r for r in S.rows(include_archived=True)}
    for p in out:
        p["orders"] = db.rows("SELECT id,step,lot,lots,symbol,side,qty,plan_qty,limit_price,scheduled_at,submitted_at,status,filled_qty,"
                              "avg_price,error,retry,client_order_id,updated_at FROM orders WHERE plan_id=? ORDER BY step, scheduled_at, id",
                              (p["id"],))
        r = names.get(p["strategy"]) or {}
        p["name"], p["color"] = r.get("name", p["strategy"]), r.get("color")
        p["target"] = json.loads(p["target"] or "{}")
        p["summary"] = json.loads(p["summary"] or "null")
        sched = [o["scheduled_at"] for o in p["orders"] if o["scheduled_at"]]
        p["window"] = [min(sched), max(sched)] if sched else None
        p["state"] = ("queued" if p["status"] == "active" and all(o["status"] == "scheduled" for o in p["orders"])
                      else "running" if p["status"] == "active" else p["status"])
    return out


def fills_view(mode, sid=None, side=None, limit=50, offset=0, since=None):
    q = ("SELECT o.id, o.plan_id, o.strategy, o.symbol, o.side, o.filled_qty, o.avg_price, o.updated_at, o.lot, o.lots, o.retry, "
         "p.reason, p.note FROM orders o JOIN plans p ON p.id=o.plan_id WHERE o.mode=? AND o.filled_qty>0")
    args = [mode]
    if sid:
        q += " AND o.strategy=?"
        args.append(sid)
    if side in ("BUY", "SELL"):
        q += " AND o.side=?"
        args.append(side)
    if since:
        q += " AND o.updated_at>=?"
        args.append(int(since))
    total = db.one(q.replace("SELECT o.id, o.plan_id, o.strategy, o.symbol, o.side, o.filled_qty, o.avg_price, o.updated_at, o.lot, "
                             "o.lots, o.retry, p.reason, p.note", "SELECT COUNT(*) n"), tuple(args))["n"]
    q += " ORDER BY o.updated_at DESC, o.id DESC LIMIT ? OFFSET ?"
    rows = db.rows(q, (*args, limit, offset))
    names = {r["id"]: r for r in S.rows(include_archived=True)}
    for r in rows:
        x = names.get(r["strategy"]) or {}
        r["name"], r["color"] = x.get("name", r["strategy"]), x.get("color")
        r["value"] = (r["filled_qty"] or 0) * (r["avg_price"] or 0)
    return {"rows": rows, "total": total}
