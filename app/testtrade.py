"""Test trade: buy a few shares of an ETF the strategies use, then sell them straight back.

Proves, symbol by symbol and mode by mode, that Webull accepts the order, fills it and that the bot reads the fill
and the fees correctly — before a strategy ever needs that ETF. It is not a strategy:
  * money: paid from the bot's unassigned money (Money page → "Bot unassigned"). No strategy's cash or shares are
    touched. The only cost is the spread + fees, booked back to bot unassigned when the shares are sold;
  * the money guard (protected floor, buying power, books ≤ account cash) checks the buy like any other;
  * one test at a time per mode; "Test all" queues them; the 30-second scheduler (and the open page) moves them on.

States: queued → buying → selling → ok        (bought and sold: Webull works for this ETF)
                        ↘ failed              (refused, or the buy did not fill: nothing is held)
                 selling ↘ holding            (bought but the sale did not fill: sell it again, or in the Webull app)
"""
from __future__ import annotations

import json
import logging
import math
import secrets
import time
from datetime import timedelta

from . import brokers, db, ledger, marketdata as md, markethours as mh, notify
from . import strategies as S

log = logging.getLogger("testtrade")
WORKING = ("queued", "buying", "selling")
TRY_S = 120                 # cancel and re-price an unfilled order after this long
BUY_TRIES, SELL_TRIES = 3, 5
MAX_QTY, MAX_VALUE = 5, 1500.0



class TestTradeError(ValueError):
    pass


def symbols() -> dict:
    """{symbol: [strategy names]} — every ETF a (not archived) strategy can hold."""
    out = {}
    for s in S.all_instances():
        for sym in s.trade_symbols() or []:
            out.setdefault(sym, []).append(s.name)
    return dict(sorted(out.items()))


def _now():
    return int(time.time())


def _log(t, text):
    lg = json.loads(t.get("log") or "[]")
    lg.append([_now(), text])
    return json.dumps(lg[-30:])


def _upd(tid, **kw):
    kw["updated_at"] = _now()
    db.run(f"UPDATE test_trades SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), tid))


def _get(tid):
    return db.one("SELECT * FROM test_trades WHERE id=?", (tid,))


def working(mode) -> bool:
    return bool(db.one(f"SELECT COUNT(*) n FROM test_trades WHERE mode=? AND status IN ('queued','buying','selling')", (mode,))["n"])


def held(mode) -> dict:
    """Shares bought by tests and not yet sold: {symbol: qty}."""
    out = {}
    for r in db.rows("SELECT symbol, SUM(bought-sold) q FROM test_trades WHERE mode=? GROUP BY symbol", (mode,)):
        if (r["q"] or 0) > 1e-9:
            out[r["symbol"]] = r["q"]
    return out


# ---------------------------------------------------------------- start
def start(mode, syms, qty=1):
    """Queue test trades for one or more symbols. Returns the new ids."""
    from . import execution
    if mode not in brokers.MODES:
        raise TestTradeError("Unknown mode")
    allowed = symbols()
    syms = [str(s).upper().strip() for s in (syms if isinstance(syms, (list, tuple)) else [syms]) if str(s).strip()]
    if not syms:
        raise TestTradeError("Choose an ETF")
    bad = [s for s in syms if s not in allowed]
    if bad:
        raise TestTradeError(f"{', '.join(bad)} is not used by any strategy")
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        raise TestTradeError("Shares must be a whole number")
    if not 1 <= qty <= MAX_QTY:
        raise TestTradeError(f"Shares: 1 to {MAX_QTY}")
    if db.get_setting("trading_paused") == "1":
        raise TestTradeError("All trading is paused. Resume it first (top right)")
    broker = brokers.get(mode)
    ok, why = broker.ready()
    if not ok:
        raise TestTradeError(f"{brokers.MODE_LABEL[mode]} is not connected: {why}")
    open_now = db.rows("SELECT symbol FROM test_trades WHERE mode=? AND status IN ('queued','buying','selling','holding')", (mode,))
    busy = {r["symbol"] for r in open_now}
    syms = [s for s in dict.fromkeys(syms) if s not in busy]
    if not syms:
        raise TestTradeError("A test for this ETF is already running (or still holds shares)")
    with execution._LOCK:
        ids = []
        with db.tx() as c:
            for s in syms:
                cur = c.execute("INSERT INTO test_trades(mode,symbol,qty,status,created_at,updated_at,log) VALUES(?,?,?,?,?,?,?)",
                                (mode, s, qty, "queued", _now(), _now(), json.dumps([[_now(), f"queued: buy {qty} then sell"]])))
                ids.append(cur.lastrowid)
        db.add_event("info", "testtrade", f"Test trade queued: {', '.join(syms)} ({qty} share{'s' if qty > 1 else ''})", "",
                     mode=mode)
    tick(mode)
    return ids


def sell_again(tid):
    t = _get(tid)
    if not t or t["status"] not in ("holding",):
        raise TestTradeError("Nothing to sell for this test")
    if db.get_setting("trading_paused") == "1":
        raise TestTradeError("All trading is paused. Resume it first (top right)")
    _upd(tid, status="selling", side=None, cid=None, tries=0, error=None, log=_log(t, "sell again (by you)"))
    tick(t["mode"])


def forget(tid):
    """You sold the leftover shares yourself in the Webull app: close the test (the sale is not in the bot's books)."""
    t = _get(tid)
    if not t or t["status"] != "holding":
        raise TestTradeError("Only a test that still holds shares can be closed this way")
    left = (t["bought"] or 0) - (t["sold"] or 0)
    _upd(tid, status="failed", sold=t["bought"], finished_at=_now(),
         result=f"closed by you: {left:.0f} share(s) sold outside the bot", log=_log(t, "closed by you"))
    db.add_event("warn", "testtrade", f"Test trade {t['symbol']} closed by hand",
                 f"{left:.0f} share(s) were sold outside the bot. Add the sale's money to the bot again on the Money page "
                 "(Webull → bot) if you want it back in bot unassigned.", mode=t["mode"])


# ---------------------------------------------------------------- the state machine
def tick(mode, now=None):
    """Move this mode's tests along. Safe to call often; runs under the execution lock."""
    from . import execution
    if not db.one("SELECT COUNT(*) n FROM test_trades WHERE mode=? AND status IN ('queued','buying','selling')", (mode,))["n"]:
        return
    if not execution._LOCK.acquire(timeout=20):
        return
    try:
        now = now or md.now_utc()
        broker = brokers.get(mode)
        ok, why = broker.ready()
        if not ok:
            return
        for t in db.rows("SELECT * FROM test_trades WHERE mode=? AND status IN ('buying','selling') ORDER BY id", (mode,)):
            try:
                _step(t, broker, now)
            except Exception as e:                 # never let one test stop the scheduler
                log.exception("test trade %s", t["id"])
                _upd(t["id"], error=str(e)[:300])
        if not db.one("SELECT COUNT(*) n FROM test_trades WHERE mode=? AND status IN ('buying','selling')", (mode,))["n"]:
            nxt = db.one("SELECT * FROM test_trades WHERE mode=? AND status='queued' ORDER BY id LIMIT 1", (mode,))
            if nxt:
                _begin(nxt, broker, now)
    finally:
        execution._LOCK.release()


def _fail(t, result, code=None, raw=None, notify_it=False):
    _upd(t["id"], status="failed", finished_at=_now(), result=result, code=code, raw=raw if raw is not None else t.get("raw"),
         log=_log(t, result))
    db.add_event("error", "testtrade", f"Test trade {t['symbol']} failed", result, mode=t["mode"])
    if notify_it:
        notify.send("lot_failed", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']}: {result}")


def _market_ok(now):
    close = mh.current_close(now, "CORE")
    return close is not None and (close - now) >= timedelta(minutes=5)


def _begin(t, broker, now):
    from . import execution
    if db.get_setting("trading_paused") == "1":
        return
    if not _market_ok(now):
        _upd(t["id"], error="waiting for the US market to open (regular hours)")
        return
    sym, qty = t["symbol"], t["qty"]
    try:
        q = broker.quote(sym)
    except Exception as e:
        _upd(t["id"], error=f"no price yet: {e}"[:300])
        return
    limit = execution._limit(q, "BUY", _offset())
    value = qty * limit
    if value > MAX_VALUE:
        return _fail(t, f"{qty:.0f} × ${limit:,.2f} = ${value:,.2f} is more than the ${MAX_VALUE:,.0f} test limit. Use 1 share.")
    need = value * 1.01 + 2
    pool = ledger.pool_cash(t["mode"])
    if pool < need:
        return _fail(t, f"bot unassigned has ${pool:,.2f}; this test needs about ${need:,.2f}. "
                        f"Money page → Webull → bot (e.g. $200), then test again.")
    acct = None
    if t["mode"] != "paper":
        try:
            acct = broker.account()
        except brokers.BrokerError as e:
            _upd(t["id"], error=f"cannot read the account: {e}"[:300])
            return
    if acct is not None:
        allowed, why = execution.Guard(t["mode"], acct, db.get_settings()).allow(value)
        if allowed < value:
            return _fail(t, f"blocked by the money guard: {why}")
    _send(t, broker, "BUY", qty, limit, now)


def _offset():
    try:
        return float(db.get_setting("exec_limit_offset_pct") or 0.10) / 100
    except ValueError:
        return 0.001


def _send(t, broker, side, qty, limit, now):
    cid = f"tsbt{t['mode'][0]}{t['id']}{side[0]}{(t['tries'] or 0) + 1}{secrets.token_hex(3)}"[:32]
    status = "buying" if side == "BUY" else "selling"
    _upd(t["id"], status=status, side=side, cid=cid, limit_price=limit, sent_at=_now(), tries=(t["tries"] or 0) + 1,
         o_filled=0, o_value=0, o_fee=0, error=None, first_sent=t.get("first_sent") or _now(),
         log=_log(t, f"{side} {qty:.0f} @ ${limit:,.2f} limit (try {(t['tries'] or 0) + 1})"))
    try:
        broker.place(t["symbol"], side, qty, limit, "CORE", cid)
    except brokers.BrokerRejected as e:
        t = _get(t["id"])
        if side == "BUY":
            if e.permanent:
                from . import execution
                execution.block_symbol(t["mode"], t["symbol"], e.code, str(e))
            return _fail(t, f"Webull refused the buy: {e}", code=e.code)
        _upd(t["id"], status="holding", error=f"Webull refused the sell: {e}"[:300], code=e.code,
             log=_log(t, f"sell refused: {e}"))
        _alert_holding(_get(t["id"]), f"Webull refused the sale: {e}")
        return
    except brokers.BrokerError as e:              # unclear: look it up by the client order id on the next tick
        _upd(t["id"], error=f"sent, no clear answer yet: {e}"[:300])


def _book(t, st, side):
    """Book the change in filled shares / value / fee of the working order into the test and bot unassigned."""
    filled = float(st.get("filled_qty") or 0)
    avg = st.get("avg_price") or t["limit_price"] or 0
    value = filled * avg
    fee = float(st.get("fee") or 0)
    dq, dv, df = filled - (t["o_filled"] or 0), value - (t["o_value"] or 0), fee - (t["o_fee"] or 0)
    if abs(dq) < 1e-9 and abs(df) < 1e-9:
        return t
    cash = (-dv if side == "BUY" else dv) - df
    with db.tx() as c:
        n = c.execute("UPDATE test_trades SET o_filled=?, o_value=?, o_fee=? WHERE id=? AND o_filled=? AND o_fee=?",
                      (filled, value, fee, t["id"], t["o_filled"] or 0, t["o_fee"] or 0)).rowcount
        if n != 1:
            return _get(t["id"])
        if side == "BUY":
            c.execute("UPDATE test_trades SET bought=bought+?, buy_value=buy_value+?, buy_fee=buy_fee+? WHERE id=?",
                      (dq, dv, df, t["id"]))
        else:
            c.execute("UPDATE test_trades SET sold=sold+?, sell_value=sell_value+?, sell_fee=sell_fee+? WHERE id=?",
                      (dq, dv, df, t["id"]))
        ledger._pool_add(c, t["mode"], cash)
    return _get(t["id"])


def _raw(broker, cid):
    fn = getattr(broker, "order_raw", None)
    if not fn:
        return None
    try:
        return json.dumps(fn(cid), default=str)[:4000]
    except Exception as e:
        return f"(could not read: {e})"[:300]


def _step(t, broker, now):
    side = t["side"]
    if t["status"] == "selling" and not t["cid"]:       # first sale (or "sell again")
        return _start_sell(t, broker, now)
    if not t["cid"]:                                   # a buy waiting for a fresh try (market was closed …)
        return _begin(t, broker, now)
    try:
        st = broker.order(t["cid"])
    except brokers.BrokerError as e:
        age = _now() - (t["sent_at"] or _now())
        _upd(t["id"], error=f"order lookup: {e}"[:300])
        if age > 180 and "not found" in str(e):
            t = _get(t["id"])
            if side == "BUY":
                return _fail(t, f"Webull has no such order after 3 minutes ({e})", raw=_raw(broker, t["cid"]))
            _upd(t["id"], cid=None, log=_log(t, "sell order not found: sending again"))
        return
    t = _book(t, st, side)
    status = (st.get("status") or "").upper()
    age = _now() - (t["sent_at"] or _now())
    done = status == "FILLED"
    dead = status in ("CANCELLED", "CANCELED", "FAILED", "REJECTED", "EXPIRED")
    if done or dead:
        t = _get(t["id"])
        raw = _raw(broker, t["cid"]) if dead else t["raw"]
        if side == "BUY":
            if (t["bought"] or 0) >= 1 - 1e-9:
                secs = _now() - (t["first_sent"] or _now())
                _upd(t["id"], status="selling", cid=None, tries=0, buy_secs=secs, raw=raw,
                     log=_log(t, f"bought {t['bought']:.0f} @ ${t['buy_value'] / t['bought']:,.2f} · fee ${t['buy_fee']:,.2f}"))
                return _start_sell(_get(t["id"]), broker, now)
            if t["tries"] >= BUY_TRIES or status in ("FAILED", "REJECTED"):
                return _fail(t, f"buy not filled: Webull says {status} after {t['tries']} tr{'y' if t['tries'] == 1 else 'ies'}",
                             raw=raw)
            _upd(t["id"], cid=None, log=_log(t, f"buy {status.lower()}: trying again at a fresh price"))
            return _begin(_get(t["id"]), broker, now)
        left = (t["bought"] or 0) - (t["sold"] or 0)
        if left <= 1e-9:
            return _finish(t)
        _upd(t["id"], cid=None, raw=raw, log=_log(t, f"sell {status.lower()}: {left:.0f} left"))
        return _start_sell(_get(t["id"]), broker, now)
    if age >= TRY_S or not _market_ok(now):
        try:
            broker.cancel(t["cid"])
            _upd(t["id"], log=_log(t, f"{side.lower()} not filled in {age}s: cancelling"))
        except brokers.BrokerError as e:
            _upd(t["id"], error=f"cancel failed: {e}"[:300], raw=_raw(broker, t["cid"]))


def _start_sell(t, broker, now):
    from . import execution
    left = int(math.floor((t["bought"] or 0) - (t["sold"] or 0) + 1e-9))
    if left < 1:
        return _finish(t)
    if (t["tries"] or 0) >= SELL_TRIES:
        _upd(t["id"], status="holding", cid=None, error=f"the sale did not fill in {SELL_TRIES} tries",
             log=_log(t, "sale did not fill: stopped"))
        return _alert_holding(_get(t["id"]), f"the sale did not fill in {SELL_TRIES} tries")
    if db.get_setting("trading_paused") == "1" or not _market_ok(now):
        _upd(t["id"], status="holding", cid=None, error="market closed or trading paused before the sale",
             log=_log(t, "holding: market closed / paused"))
        return _alert_holding(_get(t["id"]), "the market closed (or trading was paused) before the sale")
    try:
        q = broker.quote(t["symbol"])
    except Exception as e:
        _upd(t["id"], error=f"no price yet: {e}"[:300])
        return
    _send(t, broker, "SELL", left, execution._limit(q, "SELL", _offset()), now)


def _finish(t):
    t = _get(t["id"])
    cost = (t["buy_value"] or 0) - (t["sell_value"] or 0) + (t["buy_fee"] or 0) + (t["sell_fee"] or 0)
    secs = _now() - (t["sent_at"] or _now())
    res = (f"bought {t['bought']:.0f} @ ${t['buy_value'] / max(t['bought'], 1e-9):,.2f}, sold @ "
           f"${t['sell_value'] / max(t['sold'], 1e-9):,.2f} · fees ${t['buy_fee'] + t['sell_fee']:,.2f} · cost ${cost:,.2f}")
    _upd(t["id"], status="ok", finished_at=_now(), sell_secs=secs, result=res, error=None, log=_log(t, "done: " + res))
    from . import execution
    b = execution.blocked_symbols(t["mode"])
    if t["symbol"] in b:                          # it works now: let the strategies trade it again
        b.pop(t["symbol"])
        db.set_state(f"blocked_sym:{t['mode']}", b)
    db.add_event("info", "testtrade", f"Test trade {t['symbol']} OK", res, mode=t["mode"])
    notify.send("lot_filled", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']} OK: {res}")


def _alert_holding(t, why):
    left = (t["bought"] or 0) - (t["sold"] or 0)
    db.add_event("error", "testtrade", f"Test trade {t['symbol']}: {left:.0f} share(s) still held", why, mode=t["mode"])
    notify.send("lot_failed", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']}: {why}. {left:.0f} share(s) are still "
                "held. Go-live page → Sell again, or sell them in the Webull app and press 'I sold it'.", critical=True)


# ---------------------------------------------------------------- views
def view(mode) -> dict:
    syms = symbols()
    from . import execution
    blocked = execution.blocked_symbols(mode)
    rows = db.rows("SELECT * FROM test_trades WHERE mode=? ORDER BY id DESC LIMIT 200", (mode,))
    latest, last_ok = {}, {}
    for r in rows:
        latest.setdefault(r["symbol"], r)
        if r["status"] == "ok":
            last_ok.setdefault(r["symbol"], r)
    out = []
    for s, names in syms.items():
        r = latest.get(s)
        out.append({"symbol": s, "strategies": names, "blocked": blocked.get(s),
                    "last": _pub(r) if r else None, "last_ok": _pub(last_ok[s]) if s in last_ok else None})
    return {"mode": mode, "symbols": out, "pool": ledger.pool_cash(mode), "running": working(mode),
            "market_open": _market_ok(md.now_utc()), "history": [_pub(r) for r in rows[:30]],
            "max_qty": MAX_QTY}


def _pub(r):
    d = dict(r)
    d["log"] = json.loads(r["log"] or "[]")
    d["cost"] = round((r["buy_value"] or 0) - (r["sell_value"] or 0) + (r["buy_fee"] or 0) + (r["sell_fee"] or 0), 4) \
        if r["status"] == "ok" else None
    d["fees"] = round((r["buy_fee"] or 0) + (r["sell_fee"] or 0), 4)
    d["left"] = (r["bought"] or 0) - (r["sold"] or 0)
    d.pop("cid", None)
    return d


def status_for_golive(mode) -> dict:
    """{symbol: 'ok' | 'permission' | 'refused' | 'failed' | None}"""
    out = {}
    for s in symbols():
        r = db.one("SELECT status, code FROM test_trades WHERE mode=? AND symbol=? AND status IN ('ok','failed','holding') "
                   "ORDER BY (status='ok') DESC, id DESC LIMIT 1", (mode, s))
        if not r:
            out[s] = None
        elif r["status"] == "ok":
            out[s] = "ok"
        elif r["code"] == "OPENAPI_IS_TH_FIRST_ETF_PLACE":
            out[s] = "permission"
        elif r["code"]:
            out[s] = "refused"
        else:
            out[s] = "failed"
    return out
