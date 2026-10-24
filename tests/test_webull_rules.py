"""Webull refusals (seen on the TH test server) and order-detail parsing (developer.webull.co.th order-detail schema)."""
import pytest

from app import brokers, db, execution as X, ledger
from app import strategies as S
from conftest import NOW

REFUSED = ("Webull place order failed: HTTP Status: 417, Code: OPENAPI_IS_TH_FIRST_ETF_PLACE, Msg: In order to place an order "
           "for this symbol, please activate Leveraged & Inverse ETFs trading.\r\n, RequestID: 872e8c63")


def test_parse_rejection():
    r = brokers.parse_rejection(REFUSED)
    assert r.code == "OPENAPI_IS_TH_FIRST_ETF_PLACE" and r.permanent and "Leveraged" in str(r)
    r = brokers.parse_rejection("HTTP Status: 417, Code: OPENAPI_TICKER_IS_DENY, Msg: The current security is not available.")
    assert r.permanent
    r = brokers.parse_rejection("HTTP Status: 400, Code: ORDER_PRICE_INVALID, Msg: price out of range")
    assert r and not r.permanent
    assert brokers.parse_rejection("HTTP Status: 502, Code: GATEWAY") is None          # may have been placed
    assert brokers.parse_rejection("timeout") is None


def test_parse_order_detail():
    js = {"client_order_id": "c1", "combo_type": "NORMAL", "orders": [{
        "client_order_id": "c1", "order_id": "x", "symbol": "QLD", "side": "BUY", "status": "FILLED", "filled_quantity": "10",
        "filled_price": "100.5", "commission": {"actual_commission": "1.0", "receivable_commission": "1.0"},
        "fees": [{"type": "GST", "actual_value": "0.07", "receivable_value": "0.07"}]}]}
    d = brokers.WebullBroker.parse_detail(js, "c1")
    assert d == {"status": "FILLED", "filled_qty": 10.0, "avg_price": 100.5, "fee": pytest.approx(1.07)}
    with pytest.raises(brokers.BrokerError):
        brokers.WebullBroker.parse_detail({"client_order_id": "c1", "orders": []}, "c1")   # not placed → not "SUBMITTED"


class Refuses(brokers.PaperBroker):
    def place(self, symbol, side, qty, limit, session, cid):
        if symbol == "QLD":
            raise brokers.parse_rejection(REFUSED)
        return super().place(symbol, side, qty, limit, session, cid)


def test_permanent_refusal_blocks_symbol_and_cancels_plan(clean, clock):
    b = Refuses()
    brokers.set_override("paper", b)
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, b, db.get_settings())
    clock.advance(minutes=1)
    X.process(clock.dt)
    assert db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] == "cancelled"
    assert "QLD" in X.blocked_symbols("paper")
    assert ledger.get("paper", s.id)["cash"] == pytest.approx(10000)
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE event='lot_failed' AND critical=1")["n"] == 1
    clock.advance(minutes=5)
    assert X.reconcile("paper", S.get("qld_regime"), dict(s.evaluate(NOW), target=s.target_for("2x")), clock.dt, b,
                       db.get_settings()) is None                      # no new plan while QLD is refused
    X.unblock_symbols("paper")


def test_old_stuck_refused_order_is_settled(clean, clock):
    s = S.get("qld_regime")
    pid = X.build_plan("paper", s, s.target_for("2x"), "signal", NOW, brokers.get("paper"))
    o = db.one("SELECT * FROM orders WHERE plan_id=? ORDER BY id LIMIT 1", (pid,))
    db.run("UPDATE orders SET status='submitted', qty=5, client_order_id='old1', submitted_at=?, error=? WHERE id=?",
           (int(NOW.timestamp()), REFUSED, o["id"]))
    clock.advance(minutes=1)
    X.process(clock.dt)
    assert db.one("SELECT status FROM orders WHERE id=?", (o["id"],))["status"] == "failed"
    assert db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] == "cancelled"
    X.unblock_symbols("paper")


CANNOT = ("Webull cancel order failed: HTTP Status: 417, Code: OPENAPI_ORDER_CANNOT_OPERATE, Msg: The current status cannot "
          "be modified.\r\n, RequestID: 1")


class StuckAtWebull(brokers.PaperBroker):
    """Webull test server: the order is accepted, never fills, and cannot be cancelled."""
    def _try_fill(self, a, o):
        return

    def cancel(self, cid):
        raise brokers.BrokerError(CANNOT)


def test_refused_cancel_is_not_a_refused_order(clean, clock):
    b = StuckAtWebull()
    brokers.set_override("paper", b)
    s = S.get("gold_sta")
    pid = X.build_plan("paper", s, {"SGOV": 0.99}, "signal", NOW, b)
    db.run("UPDATE orders SET scheduled_at=? WHERE plan_id=?", (int(NOW.timestamp()), pid))
    X.process(NOW)
    first = db.one("SELECT * FROM orders WHERE plan_id=? AND status='submitted'", (pid,))
    assert first
    for _ in range(12):
        clock.advance(minutes=2)
        X.process(clock.dt)
    o = db.one("SELECT * FROM orders WHERE id=?", (first["id"],))
    assert o["status"] == "submitted" and o["error"].startswith("cancel failed")      # still open: no replacement sent
    assert db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND retry>0", (pid,))["n"] == 0
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE critical=1 AND text LIKE '%Could not cancel%'")["n"] == 1


def test_repair_rechecks_orders_wrongly_marked_refused(clean, clock):
    s = S.get("gold_sta")
    pid = X.build_plan("paper", s, {"SGOV": 0.99}, "signal", NOW, brokers.get("paper"))
    o = db.one("SELECT * FROM orders WHERE plan_id=? ORDER BY id LIMIT 1", (pid,))
    b = brokers.get("paper")
    b.place("SGOV", "BUY", 5, 1000.0, "CORE", "filled1")                 # it really filled at the broker
    db.run("UPDATE orders SET status='failed', qty=5, side='BUY', symbol='SGOV', client_order_id='filled1', submitted_at=?, "
           "error=? WHERE id=?", (int(NOW.timestamp()), "refused: " + CANNOT, o["id"]))
    db.set_state("repair_cancel_refusals", None)
    X.process(NOW)
    o = db.one("SELECT * FROM orders WHERE id=?", (o["id"],))
    assert o["status"] == "filled" and o["applied_qty"] == 5                  # the fill is booked now
    assert ledger.get("paper", s.id)["holdings"].get("SGOV") == 5
