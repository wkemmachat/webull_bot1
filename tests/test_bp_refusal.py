"""Webull's "Insufficient Buying Power" (25 Nov 2026): a money matter, not "no fractional shares". The lot is sent again
sized to what Webull frees, or the buys wait for buying power; the old wrong whole-share switches are undone; the money
guard counts buys sent after a cached account read; the Webull check reads the open-orders list."""
import json
import time

import pytest

from app import brokers, db, execution as X, ledger, webull_check
from app import strategies as S
from conftest import NOW
from test_execution import run_until_done
from test_fractional_exec import frac

BP_ERR = "OPENAPI_ORDER_BUYING_POWER_NOT_ENOUGH: Insufficient Buying Power"


class BpShort(brokers.PaperBroker):
    """Refuses any buy above `cap` dollars for buying power (and reports that cap as its buying power)."""

    def __init__(self, cap):
        self.cap, self.refused = cap, []
        super().__init__()

    def account(self):
        a = super().account()
        a["buying_power"] = self.cap
        return a

    def place(self, symbol, side, qty, limit, session, cid):
        if side == "BUY" and qty * limit > self.cap:
            self.refused.append((symbol, qty))
            raise brokers.BrokerRejected(BP_ERR, code="OPENAPI_ORDER_BUYING_POWER_NOT_ENOUGH")
        return super().place(symbol, side, qty, limit, session, cid)


def test_buying_power_refusal_resizes_the_lot_and_keeps_fractions(clean, clock, monkeypatch):
    frac("paper", True)
    b = BpShort(cap=1e9)
    brokers.set_override("paper", b)
    try:
        s = S.get("qld_regime")
        pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, b, db.get_settings())
        first = db.one("SELECT * FROM orders WHERE plan_id=? AND side='BUY' ORDER BY id LIMIT 1", (pid,))
        assert first
        b.cap = 1500.0                                           # Webull frees $1,500 only (cash still looks fine to the guard)
        monkeypatch.setattr(X.Guard, "allow", lambda self, value, sid=None: (value, None))
        run_until_done(clock, pid)
        assert b.refused                                         # Webull refused at least one lot
        assert X.fraction_refused("paper") == {}                 # ... and fractions stay on
        resized = db.rows("SELECT * FROM events WHERE title LIKE 'Buy resized for Webull buying power%'")
        assert resized
        retries = db.rows("SELECT * FROM orders WHERE plan_id=? AND side='BUY' AND retry>0", (pid,))
        assert retries and all(o["qty"] * o["limit_price"] <= 1500.0 * X.BP_FIT for o in retries if o["qty"])
        assert not db.rows("SELECT * FROM line_queue WHERE text LIKE '%refused a fractional order%'")
        assert all(o["status"] == "filled" for o in retries)       # the resized lot went through
    finally:
        brokers.set_override("paper", None)


def test_buying_power_refusal_with_nothing_free_waits(clean, clock, monkeypatch):
    frac("paper", True)
    b = BpShort(cap=1e9)
    brokers.set_override("paper", b)
    try:
        s = S.get("qld_regime")
        pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, b, db.get_settings())
        b.cap = 2.0                                              # nothing worth a lot
        monkeypatch.setattr(X.Guard, "allow", lambda self, value, sid=None: (value, None))
        run_until_done(clock, pid)
        w = X.bp_wait("paper")
        assert w and w["sids"] == ["qld_regime"]
        assert db.one("SELECT COUNT(*) n FROM events WHERE title='Buys wait for Webull buying power'")["n"] == 1
        assert X.fraction_refused("paper") == {}
    finally:
        brokers.set_override("paper", None)


def test_old_buying_power_switches_are_undone(clean):
    db.set_state("frac_refused:live", {
        "USD": {"at": 1, "code": "OPENAPI_ORDER_BUYING_POWER_NOT_ENOUGH", "msg": BP_ERR},
        "QLD": {"at": 2, "code": None, "msg": "Webull place order failed: " + BP_ERR},
        "XYZ": {"at": 3, "code": "FRACTION_NOT_SUPPORTED", "msg": "no fractions"}})
    X.repair_bp_refusals()
    assert set(X.fraction_refused("live")) == {"XYZ"}
    ev = db.one("SELECT * FROM events WHERE title LIKE 'Fractional shares back on%'")
    assert ev and "USD" in ev["title"] and "QLD" in ev["title"]
    X.repair_bp_refusals()                                       # once: nothing left to undo
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE 'Fractional shares back on%'")["n"] == 1


def test_real_fraction_refusal_still_switches_to_whole_shares(clean):
    e = brokers.BrokerRejected("fractional orders are not supported for this symbol", code="OPENAPI_FRAC")
    assert not X._bp_refusal(e)
    assert X._bp_refusal(brokers.BrokerRejected(BP_ERR, code="OPENAPI_ORDER_BUYING_POWER_NOT_ENOUGH"))


def test_guard_counts_buys_sent_after_the_cached_read(clean):
    read_at = time.time() - 10
    acct = {"cash": ledger.bot_cash("paper") + 1e6, "buying_power": 5000.0, "_read_at": read_at}
    for sent, qty in ((int(read_at) - 30, 10), (int(read_at) + 5, 20)):     # one before the read, one after
        db.run("INSERT INTO orders(plan_id, mode, strategy, step, lot, lots, symbol, side, qty, limit_price, status, applied_qty, "
               "scheduled_at, submitted_at) VALUES(0,'paper','qld_regime',1,1,5,'QLD','BUY',?,50.0,'submitted',0,0,?)", (qty, sent))
    g = X.Guard("paper", acct, db.get_settings())
    assert g.bp == pytest.approx(5000.0 - 20 * 50.0)            # only the buy sent after the read: $1,000
    g = X.Guard("paper", {**acct, "_read_at": None}, db.get_settings())
    assert g.bp == pytest.approx(5000.0)                         # a fresh read (no time) is taken as it is


def test_cached_account_carries_its_read_time(monkeypatch):
    w = brokers.WebullBroker.__new__(brokers.WebullBroker)
    w.env = "live"
    monkeypatch.setattr(brokers, "ACCOUNT_CACHE_S", 15)
    monkeypatch.setattr(brokers.WebullBroker, "_account", lambda self: {"cash": 1.0, "buying_power": 1.0})
    brokers._ACCT_CACHE.clear()
    a = w.account()
    assert abs(a["_read_at"] - time.time()) < 2
    assert w.account()["_read_at"] == a["_read_at"]              # the cached copy keeps the time of the real read
    brokers._ACCT_CACHE.clear()


def test_webull_check_prints_the_open_orders_list(capsys):
    class Order:
        def get_order_open(self, aid, page_size=None):
            return "res"

    class Fake:
        def _clients(self):
            return type("T", (), {"order_v3": Order()})(), None

        def _acct_id(self):
            return "A1"

        _call = staticmethod(brokers.WebullBroker._call)

        def _json(self, res, what):
            return {"data": [{"client_order_id": "tsbl600x1r0ab12", "status": "SUBMITTED"}, {"client_order_id": "manual1"}]}
    webull_check.open_orders(Fake())
    out = capsys.readouterr().out
    assert "readable · 2 open now (1 sent by the bot): tsbl600x1r0ab12" in out

    class Unknown(Fake):
        def _json(self, res, what):
            return {"msg": "ok"}
    webull_check.open_orders(Unknown())
    assert "NOT understood" in capsys.readouterr().out

    class Down(Fake):
        def _json(self, res, what):
            raise brokers.BrokerError("Webull open orders failed (404): not found")
    webull_check.open_orders(Down())
    assert "NOT readable" in capsys.readouterr().out
