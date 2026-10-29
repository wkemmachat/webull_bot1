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

from . import brokers, db, hk, ledger, marketdata as md, markethours as mh, notify
from . import strategies as S

log = logging.getLogger("testtrade")
WORKING = ("queued", "buying", "selling")
TRY_S = 120                 # cancel and re-price an unfilled order after this long
BUY_TRIES, SELL_TRIES = 3, 5
MAX_QTY, MAX_VALUE = 5, 1500.0
FRACTION = 0.5              # the fractional-share test buys half a share
ORDER_TYPES = ("LIMIT", "MARKET")
HK_MAX_LOTS, HK_MAX_VALUE = 2, 15000.0      # Hong Kong test: 1–2 board lots, at most HK$15,000



class TestTradeError(ValueError):
    pass


def funded(mode) -> set:
    """Strategies that hold money in this mode (cash, shares or a running plan)."""
    out = set()
    for s in S.all_instances():
        L = ledger.get(mode, s.id)
        if L["cash"] > 0.5 or L["holdings"] or db.one("SELECT 1 x FROM plans WHERE mode=? AND strategy=? AND status='active'",
                                                       (mode, s.id)):
            out.add(s.id)
    return out


def symbols(in_use=False, mode=None) -> dict:
    """{symbol: [strategy names]} — every ETF a (not archived) strategy can hold. in_use: only strategies that are not
    stopped (what Go-live needs tested); with a mode, only the ones that have money there (all of them while none has)."""
    out = {}
    have = funded(mode) if mode else set()
    for s in S.all_instances():
        if in_use and (s.row or {}).get("control") == "stopped":
            continue
        if in_use and have and s.id not in have:
            continue
        for sym in (s.test_symbols() if hasattr(s, "test_symbols") else s.trade_symbols()) or []:
            out.setdefault(sym, []).append(s.name)
    return dict(sorted(out.items()))


def _now():
    return int(time.time())


def _m(x, sym):
    """Money in the symbol's currency: $12.30 or HK$12.30."""
    return hk.money(x, sym)


def _log(t, text):
    lg = json.loads(t.get("log") or "[]")
    lg.append([_now(), text])
    return json.dumps(lg[-30:])


def _upd(tid, **kw):
    kw["updated_at"] = _now()
    db.run(f"UPDATE test_trades SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), tid))


def _get(tid):
    return db.one("SELECT * FROM test_trades WHERE id=?", (tid,))


def is_fraction(q) -> bool:
    q = float(q or 0)
    return abs(q - round(q)) > 1e-9


def qs(q) -> str:
    """Share count for messages: 1 → "1", 0.5 → "0.5"."""
    q = float(q or 0)
    return f"{q:.0f}" if not is_fraction(q) else f"{q:.6f}".rstrip("0").rstrip(".")


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
def start(mode, syms, qty=1, fractional=False, order_type="LIMIT"):
    """Queue test trades for one or more symbols. Returns the new ids. fractional: buy and sell half a share of ONE ETF
    (does Webull accept fractional orders through the API, as a limit or a market order?)."""
    from . import execution
    if mode not in brokers.MODES:
        raise TestTradeError("Unknown mode")
    allowed = set(symbols())
    syms = [hk.norm(s) for s in (syms if isinstance(syms, (list, tuple)) else [syms]) if str(s).strip()]
    if not syms:
        raise TestTradeError("Choose an ETF")
    if any(hk.is_hk(s) for s in syms):
        # Webull Thailand does not allow Hong Kong trading for this account (checked in the Webull app, 29 Oct 2026)
        raise TestTradeError("Hong Kong test trades are off: Webull Thailand does not allow Hong Kong trading for this account")
    bad = [s for s in syms if s not in allowed]
    if bad:
        raise TestTradeError(f"{', '.join(bad)} is not used by any strategy")
    hks = [s for s in syms if hk.is_hk(s)]
    if hks and len(hks) != len(syms):
        raise TestTradeError("Test Hong Kong and US ETFs separately")
    if hks:
        if fractional:
            raise TestTradeError("Hong Kong orders are whole board lots only (no fractions)")
        try:
            lots = int(qty)
        except (TypeError, ValueError):
            raise TestTradeError("Lots must be a whole number")
        if not 1 <= lots <= HK_MAX_LOTS:
            raise TestTradeError(f"Lots: 1 to {HK_MAX_LOTS}")
        return _start_hk(mode, hks, lots)
    order_type = str(order_type or "LIMIT").upper()
    if order_type not in ORDER_TYPES:
        raise TestTradeError("Order type: LIMIT or MARKET")
    if fractional:
        if len(syms) != 1:
            raise TestTradeError("The fractional test runs on one ETF at a time")
        qty = FRACTION
    else:
        order_type = "LIMIT"
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
                what = f"{qs(qty)} ({order_type.lower()} order, fractional test)" if fractional else qs(qty)
                cur = c.execute("INSERT INTO test_trades(mode,symbol,qty,status,created_at,updated_at,log,order_type) VALUES(?,?,?,?,?,?,?,?)",
                                (mode, s, qty, "queued", _now(), _now(), json.dumps([[_now(), f"queued: buy {what} then sell"]]),
                                 order_type))
                ids.append(cur.lastrowid)
        db.add_event("info", "testtrade", f"Test trade queued: {', '.join(syms)} ({qs(qty)} share{'s' if qty > 1 else ''}"
                     + (f", fractional {order_type.lower()} test" if fractional else "") + ")", "", mode=mode)
    tick(mode)
    return ids


def _start_hk(mode, syms, lots):
    """Queue Hong Kong test trades: buy `lots` board lots, sell them straight back. Paid from bot HKD."""
    from . import execution
    if db.get_setting("trading_paused") == "1":
        raise TestTradeError("All trading is paused. Resume it first (top right)")
    broker = brokers.get(mode)
    ok, why = broker.ready()
    if not ok:
        raise TestTradeError(f"{brokers.MODE_LABEL[mode]} is not connected: {why}")
    busy = {r["symbol"] for r in db.rows("SELECT symbol FROM test_trades WHERE mode=? AND status IN "
                                         "('queued','buying','selling','holding')", (mode,))}
    syms = [s for s in dict.fromkeys(syms) if s not in busy]
    if not syms:
        raise TestTradeError("A test for this ETF is already running (or still holds shares)")
    with execution._LOCK:
        ids = []
        with db.tx() as c:
            for s in syms:
                q = lots * hk.lot(s)
                cur = c.execute("INSERT INTO test_trades(mode,symbol,qty,status,created_at,updated_at,log,order_type) VALUES(?,?,?,?,?,?,?,?)",
                                (mode, s, q, "queued", _now(), _now(),
                                 json.dumps([[_now(), f"queued: buy {lots} lot{'s' if lots > 1 else ''} ({q} shares) then sell "
                                                      "(Hong Kong, enhanced limit order, paid in HKD)"]]), "LIMIT"))
                ids.append(cur.lastrowid)
        db.add_event("info", "testtrade", f"Hong Kong test trade queued: {', '.join(syms)} ({lots} lot{'s' if lots > 1 else ''})", "",
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
         result=f"closed by you: {qs(left)} share(s) sold outside the bot", log=_log(t, "closed by you"))
    db.add_event("warn", "testtrade", f"Test trade {t['symbol']} closed by hand",
                 f"{qs(left)} share(s) were sold outside the bot. Add the sale's money to the bot again on the Money page "
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
    if hk.is_hk(t["symbol"]) and t.get("cid"):        # only answers from Webull count (not "bot HKD too low")
        _hk_result(t, False, result, code)
    if is_fraction(t["qty"]):
        _fraction_result(t, False, result, code)
    db.add_event("error", "testtrade", f"Test trade {t['symbol']} failed", result, mode=t["mode"])
    if notify_it:
        notify.send("lot_failed", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']}: {result}")


def _market_ok(now, sym=None):
    if sym is not None and hk.is_hk(sym):
        return hk.is_open(now, 5)
    close = mh.current_close(now, "CORE")
    return close is not None and (close - now) >= timedelta(minutes=5)


def _begin(t, broker, now):
    from . import execution
    if db.get_setting("trading_paused") == "1":
        return
    sym, qty = t["symbol"], t["qty"]
    if not _market_ok(now, sym):
        _upd(t["id"], error=hk.status(now)["text"] if hk.is_hk(sym) else "waiting for the US market to open (regular hours)")
        return
    try:
        q = broker.quote(sym)
    except Exception as e:
        _upd(t["id"], error=f"no price yet: {e}"[:300])
        return
    limit = _test_limit(q, "BUY", t["tries"] or 0, sym)
    value = qty * limit
    if hk.is_hk(sym):
        return _begin_hk(t, broker, now, qty, limit, value)
    if value > MAX_VALUE:
        return _fail(t, f"{qs(qty)} × ${limit:,.2f} = ${value:,.2f} is more than the ${MAX_VALUE:,.0f} test limit. Use 1 share.")
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


def _begin_hk(t, broker, now, qty, limit, value):
    """Hong Kong buy: checked against bot HKD and the account's HKD cash (the USD money guard does not apply)."""
    sym = t["symbol"]
    if value > HK_MAX_VALUE:
        return _fail(t, f"{qs(qty)} × HK${limit:,.3f} = HK${value:,.2f} is more than the HK${HK_MAX_VALUE:,.0f} test limit. Use 1 lot.")
    need = value * 1.01 + 20
    have = ledger.hk_cash(t["mode"])
    if have < need:
        return _fail(t, f"bot HKD has HK${have:,.2f}; this test needs about HK${need:,.2f}. Convert USD to HKD in the Webull app, "
                        "then Money → Hong Kong dollars → Allocate HKD to the bot, and test again.")
    if t["mode"] != "paper":
        try:
            acct = broker.account()
        except brokers.BrokerError as e:
            _upd(t["id"], error=f"cannot read the account: {e}"[:300])
            return
        acct_hkd = acct.get("cash_hkd")
        if acct_hkd is None or acct_hkd < value:
            return _fail(t, f"the Webull account shows HK${(acct_hkd or 0):,.2f} of HKD cash; this test needs HK${value:,.2f}")
    _send(t, broker, "BUY", qty, limit, now)


def _market(t) -> bool:
    return (t.get("order_type") or "LIMIT").upper() == "MARKET"


def _test_limit(q, side, tries, sym=None):
    """Like a lot: through the quote, 0.5% wider when Webull shows no bid/ask (thin ETFs such as ROM), and each new try
    0.5% further (at most 2%). A limit only caps the price; a liquid ETF still fills at the market. Hong Kong prices go
    onto HKEX's tick table (HK$0.01 steps for HK$0.50–10)."""
    from . import execution
    base = execution._limit(q, side, _offset())
    sign = 1 if side == "BUY" else -1
    extra = (execution.STALE_EXTRA if not q.get("ask" if side == "BUY" else "bid") else 0.0) \
        + min(execution.CHASE_STEP * tries, execution.CHASE_CAP)
    if sym is not None and hk.is_hk(sym):
        return hk.round_price(base * (1 + sign * extra), side)
    return round(base * (1 + sign * extra), 2)


def _offset():
    try:
        return float(db.get_setting("exec_limit_offset_pct") or 0.10) / 100
    except ValueError:
        return 0.001


def _send(t, broker, side, qty, limit, now):
    cid = f"tsbt{t['mode'][0]}{t['id']}{side[0]}{(t['tries'] or 0) + 1}{secrets.token_hex(3)}"[:32]
    status = "buying" if side == "BUY" else "selling"
    mkt = _market(t)
    _upd(t["id"], status=status, side=side, cid=cid, limit_price=limit, sent_at=_now(), tries=(t["tries"] or 0) + 1,
         o_filled=0, o_value=0, o_fee=0, error=None, first_sent=t.get("first_sent") or _now(),
         log=_log(t, f"{side} {qs(qty)} " + (f"at market (≈ {_m(limit, t['symbol'])})" if mkt else
                                            f"@ {_m(limit, t['symbol']) if not hk.is_hk(t['symbol']) else 'HK$' + hk.price_text(limit)} limit")
                  + f" (try {(t['tries'] or 0) + 1})"))
    try:
        broker.place(t["symbol"], side, qty, None if mkt else limit, "CORE", cid)
    except brokers.BrokerRejected as e:
        t = _get(t["id"])
        if side == "BUY":
            if e.permanent and not is_fraction(t["qty"]) and not hk.is_hk(t["symbol"]):   # a refused fraction says nothing about the ETF
                from . import execution
                execution.block_symbol(t["mode"], t["symbol"], e.code, str(e))
            return _fail(t, f"Webull refused the {'fractional ' if is_fraction(t['qty']) else ''}buy: {e}", code=e.code)
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
        if hk.is_hk(t["symbol"]):
            ledger._hk_add(c, t["mode"], cash)        # Hong Kong tests are paid in HKD from bot HKD
        else:
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
            if (t["bought"] or 0) >= float(t["qty"]) - 1e-9:
                secs = _now() - (t["first_sent"] or _now())
                _upd(t["id"], status="selling", cid=None, tries=0, buy_secs=secs, raw=raw,
                     log=_log(t, f"bought {qs(t['bought'])} @ {_m(t['buy_value'] / t['bought'], t['symbol'])} · fee "
                                 f"{_m(t['buy_fee'], t['symbol'])}"))
                return _start_sell(_get(t["id"]), broker, now)
            if t["tries"] >= BUY_TRIES or status in ("FAILED", "REJECTED"):
                return _fail(t, f"buy not filled: Webull says {status} after {t['tries']} tr{'y' if t['tries'] == 1 else 'ies'}",
                             raw=raw)
            _upd(t["id"], cid=None, log=_log(t, f"buy {status.lower()}: trying again at a fresh price"))
            return _begin(_get(t["id"]), broker, now)
        left = (t["bought"] or 0) - (t["sold"] or 0)
        if left <= 1e-9:
            return _finish(t)
        _upd(t["id"], cid=None, raw=raw, log=_log(t, f"sell {status.lower()}: {qs(left)} left"))
        return _start_sell(_get(t["id"]), broker, now)
    if age >= TRY_S or not _market_ok(now, t["symbol"]):
        try:
            broker.cancel(t["cid"])
            _upd(t["id"], log=_log(t, f"{side.lower()} not filled in {age}s: cancelling"))
        except brokers.BrokerError as e:
            _upd(t["id"], error=f"cancel failed: {e}"[:300], raw=_raw(broker, t["cid"]))


def _start_sell(t, broker, now):
    from . import execution
    rest = (t["bought"] or 0) - (t["sold"] or 0)
    left = round(rest, 6) if is_fraction(t["qty"]) else int(math.floor(rest + 1e-9))
    if hk.is_hk(t["symbol"]) and left >= 1:
        n = hk.lot(t["symbol"])
        whole = (left // n) * n                     # HKEX's normal board takes whole lots only
        if whole < 1:
            _upd(t["id"], status="holding", cid=None, error=f"{left} share(s) is an odd lot (board lot {n}): sell it in the Webull app",
                 log=_log(t, "odd lot left: sell it in the Webull app"))
            return _alert_holding(_get(t["id"]), f"{left} share(s) is an odd lot (less than the {n}-share board lot)")
        left = whole
    if left < (1e-6 if is_fraction(t["qty"]) else 1):
        return _finish(t)
    if (t["tries"] or 0) >= SELL_TRIES:
        _upd(t["id"], status="holding", cid=None, error=f"the sale did not fill in {SELL_TRIES} tries",
             log=_log(t, "sale did not fill: stopped"))
        return _alert_holding(_get(t["id"]), f"the sale did not fill in {SELL_TRIES} tries")
    if db.get_setting("trading_paused") == "1" or not _market_ok(now, t["symbol"]):
        _upd(t["id"], status="holding", cid=None, error="market closed or trading paused before the sale",
             log=_log(t, "holding: market closed / paused"))
        return _alert_holding(_get(t["id"]), "the market closed (or trading was paused) before the sale")
    try:
        q = broker.quote(t["symbol"])
    except Exception as e:
        _upd(t["id"], error=f"no price yet: {e}"[:300])
        return
    _send(t, broker, "SELL", left, _test_limit(q, "SELL", t["tries"] or 0, t["symbol"]), now)


def _finish(t):
    t = _get(t["id"])
    cost = (t["buy_value"] or 0) - (t["sell_value"] or 0) + (t["buy_fee"] or 0) + (t["sell_fee"] or 0)
    secs = _now() - (t["sent_at"] or _now())
    sym = t["symbol"]
    res = (f"bought {qs(t['bought'])} @ {_m(t['buy_value'] / max(t['bought'], 1e-9), sym)}, sold @ "
           f"{_m(t['sell_value'] / max(t['sold'], 1e-9), sym)} · fees {_m(t['buy_fee'] + t['sell_fee'], sym)} · cost {_m(cost, sym)}")
    _upd(t["id"], status="ok", finished_at=_now(), sell_secs=secs, result=res, error=None, log=_log(t, "done: " + res))
    if is_fraction(t["qty"]):
        _fraction_result(t, True, res)
        db.add_event("info", "testtrade", f"Fractional test {t['symbol']} OK ({(t.get('order_type') or 'LIMIT').lower()} order)", res,
                     mode=t["mode"])
        notify.send("lot_filled", f"{brokers.MODE_LABEL[t['mode']]} · Fractional test {t['symbol']} OK "
                    f"({(t.get('order_type') or 'LIMIT').lower()} order): {res}")
        return
    if hk.is_hk(sym):
        _hk_result(t, True, res)
        db.add_event("info", "testtrade", f"Hong Kong test trade {sym} OK", res, mode=t["mode"])
        notify.send("lot_filled", f"{brokers.MODE_LABEL[t['mode']]} · Hong Kong test trade {sym} ({hk.name(sym)}) OK: {res}")
        return
    from . import execution
    b = execution.blocked_symbols(t["mode"])
    if t["symbol"] in b:                          # it works now: let the strategies trade it again
        b.pop(t["symbol"])
        db.set_state(f"blocked_sym:{t['mode']}", b)
    db.add_event("info", "testtrade", f"Test trade {t['symbol']} OK", res, mode=t["mode"])
    notify.send("lot_filled", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']} OK: {res}")


def _alert_holding(t, why):
    left = (t["bought"] or 0) - (t["sold"] or 0)
    db.add_event("error", "testtrade", f"Test trade {t['symbol']}: {qs(left)} share(s) still held", why, mode=t["mode"])
    notify.send("lot_failed", f"{brokers.MODE_LABEL[t['mode']]} · Test trade {t['symbol']}: {why}. {qs(left)} share(s) are still "
                "held. Go-live page → Sell again, or sell them in the Webull app and press 'I sold it'.", critical=True)


# ---------------------------------------------------------------- views
def view(mode) -> dict:
    syms = symbols()
    from . import execution
    blocked = execution.blocked_symbols(mode)
    rows = db.rows("SELECT * FROM test_trades WHERE mode=? ORDER BY id DESC LIMIT 200", (mode,))
    latest, last_ok = {}, {}
    for r in rows:
        if is_fraction(r["qty"]):
            continue                                  # shown in the fractional block, not as the ETF's test
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
            "max_qty": MAX_QTY, "fractional": fraction_status(mode),
            "fractional_tests": [_pub(r) for r in rows if is_fraction(r["qty"])][:6]}


def _fraction_result(t, ok, text, code=None):
    """Remember, per mode and order type, whether Webull accepted a fractional order (the base for a fractional setting)."""
    k = f"fractional:{t['mode']}"
    st = db.get_state(k) or {}
    st[(t.get("order_type") or "LIMIT").upper()] = {"ok": bool(ok), "text": str(text)[:300], "code": code, "symbol": t["symbol"],
                                                     "at": _now()}
    db.set_state(k, st)


def fraction_status(mode) -> dict:
    """{'LIMIT': {...} | None, 'MARKET': {...} | None, 'verdict': text}"""
    st = db.get_state(f"fractional:{mode}") or {}
    lim, mkt = st.get("LIMIT"), st.get("MARKET")
    if lim and lim["ok"]:
        v = ("Webull accepts fractional LIMIT orders: the bot adds the leftover fraction to the last lot of each buy "
             "(Execution → Fractional shares).")
    elif mkt and mkt["ok"]:
        v = ("Webull accepts fractional orders only as MARKET orders" if lim else "Webull accepts fractional MARKET orders")\
            + (": the bot could buy whole shares by limit order and only the leftover fraction at market." if lim else
               ". Run the limit test too.")
    elif lim or mkt:
        v = "Webull refused fractional orders through the API so far." + ("" if (lim and mkt) else " Try the other order type.")
    else:
        v = "Not tested yet."
    return {"LIMIT": lim, "MARKET": mkt, "verdict": v}


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
    """{symbol: 'ok' | 'permission' | 'refused' | 'failed' | None} for the ETFs of strategies that are not stopped. Single-stock
    2x ETFs are left out once Webull's 50M THB rule applies to this account (the bot holds the stocks instead)."""
    from . import execution
    skip = execution.single_stock_etfs() if execution.single_stock_refused(mode) else set()
    out = {}
    for s in [x for x in symbols(in_use=True, mode=mode) if x not in skip]:
        r = db.one("SELECT status, code FROM test_trades WHERE mode=? AND symbol=? AND qty>=1 AND status IN ('ok','failed','holding') "
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


# ---------------------------------------------------------------- Hong Kong
def _hk_result(t, ok, text, code=None):
    """Remember per mode and symbol whether Webull bought (and sold) the Hong Kong ETF through the API."""
    k = f"hk_test:{t['mode']}"
    st = db.get_state(k) or {}
    st[t["symbol"]] = {"ok": bool(ok), "text": str(text)[:300], "code": code, "at": _now()}
    db.set_state(k, st)


HK_HINTS = {
    "permission": "Webull refused: this account may not trade Hong Kong through the API (Webull Thailand's OpenAPI documents US "
                  "stocks only). Ask Webull Thailand support whether OpenAPI Hong Kong trading can be turned on.",
    "party": "Webull asks for the Hong Kong investor ID (BCAN). Ask Webull for your BCAN and enter it on the Webull page.",
}


def hk_hint(code, text) -> str | None:
    t = f"{code or ''} {text or ''}".upper()
    if "PARTY" in t or "BCAN" in t:
        return HK_HINTS["party"]
    if any(w in t for w in ("MARKET", "NOT_SUPPORT", "PERMISSION", "DENY", "NO_AUTH", "NOT_OPEN", "UNSUPPORT", "ILLEGAL",
                            "INVALID_SYMBOL", "TICKER")):
        return HK_HINTS["permission"]
    return "Webull refused the order: read Webull's own answer below; if it is about the market or permissions, ask Webull " \
           "Thailand support whether OpenAPI Hong Kong trading can be turned on."


def hk_status(mode) -> dict:
    """{symbol: {'state': 'ok'|'refused'|'failed'|None, 'text', 'code', 'at', 'hint'}} for the three Hong Kong ETFs."""
    st = db.get_state(f"hk_test:{mode}") or {}
    out = {}
    for s in hk.TEST_SYMBOLS:
        r = st.get(s)
        if not r:
            out[s] = {"state": None}
        else:
            out[s] = {"state": "ok" if r["ok"] else ("refused" if r.get("code") else "failed"), "text": r.get("text"),
                      "code": r.get("code"), "at": r.get("at"),
                      "hint": hk_hint(r.get("code"), r.get("text")) if (not r["ok"] and r.get("code")) else None}
    return out


def hk_view(mode) -> dict:
    """The Hong Kong block of the Go-live test trade box."""
    now = md.now_utc()
    rows = db.rows("SELECT * FROM test_trades WHERE mode=? ORDER BY id DESC LIMIT 200", (mode,))
    stat = hk_status(mode)
    prices = {}
    for s in hk.TEST_SYMBOLS:
        try:
            prices[s] = md.quote(s, max_age=300)["price"]
        except Exception:
            prices[s] = None
    out = []
    for s, p in hk.PRODUCTS.items():
        last = next((r for r in rows if r["symbol"] == s), None)
        ok = next((r for r in rows if r["symbol"] == s and r["status"] == "ok"), None)
        n = hk.lot(s)
        out.append({"symbol": s, "name": p["short"], "full_name": p["name"], "lot": n, "price": prices[s],
                    "lot_value": round(n * prices[s], 2) if prices[s] else None, "result": stat[s],
                    "last": _pub(last) if last else None, "last_ok": _pub(ok) if ok else None})
    return {"symbols": out, "bot_hkd": ledger.hk_cash(mode), "market": hk.status(now), "max_lots": HK_MAX_LOTS,
            "running": any(r["status"] in WORKING for r in rows if hk.is_hk(r["symbol"]))}
