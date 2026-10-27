"""Go-live list after the first Live week: only funded strategies' ETFs count, explained errors do not block, and Test
trades chase thin ETFs like lots do."""
import time

from app import brokers, db, execution as X, golive, ledger, moneyops, testtrade
from conftest import NOW


def _item(rep, key):
    return next(i for sec in rep["sections"] for i in sec["items"] if i["key"] == key)


def test_only_funded_strategies_count(clean):
    every = set(testtrade.status_for_golive("live"))
    assert "QLD" in every and "UGL" in every                         # nothing funded yet: every active strategy
    ledger.fund_in("live", 1000, 5000)
    moneyops.add("live", "usd_ibs", 500, "wait")
    need = set(testtrade.status_for_golive("live"))
    assert "USD" in need and "GLD" in need and "UGL" not in need and "AAPL" not in need


def test_single_stock_refusal_is_explained(clean):
    X.block_symbol("live", "AAPU", brokers.SINGLE_STOCK_LEV_CODE, "refused")
    try:
        it = _item(golive.report("live"), "errors")
        assert it["status"] == "ok" and "explained" in it["detail"]
    finally:
        X.unblock_symbols("live")


def test_failed_test_trade_explained_by_a_later_pass(clean):
    db.add_event("error", "testtrade", "Test trade ROM failed", "buy not filled", mode="live")
    assert _item(golive.report("live"), "errors")["status"] == "todo"
    now = int(time.time())
    db.run("INSERT INTO test_trades(mode,symbol,qty,status,created_at,finished_at,updated_at) VALUES('live','ROM',1,'ok',?,?,?)",
           (now, now + 5, now + 5))
    it = _item(golive.report("live"), "errors")
    assert it["status"] == "ok" and "ROM test trade passed" in it["detail"]


def test_test_trade_limit_chases_and_widens():
    q = {"price": 100.0, "ask": 100.0, "bid": 99.9}
    assert testtrade._test_limit(q, "BUY", 0) == 100.1
    assert testtrade._test_limit(q, "BUY", 2) == round(100.1 * 1.01, 2)
    assert testtrade._test_limit(q, "BUY", 9) == round(100.1 * 1.02, 2)          # capped
    thin = {"price": 145.0}
    assert testtrade._test_limit(thin, "BUY", 0) == round(round(145 * 1.001, 2) * 1.005, 2)
    assert testtrade._test_limit(thin, "SELL", 1) == round(round(145 * 0.999, 2) * 0.99, 2)


def test_health_treats_the_handled_single_stock_rule_as_ok(clean, clock):
    from app import health
    X.block_symbol("paper", "AAPU", brokers.SINGLE_STOCK_LEV_CODE, "refused")
    try:
        rep = health.run(send=False)
        it = next(i for i in rep["items"] if i["id"] == "refused_paper")
        assert it["status"] == "ok" and "50M THB" in it["detail"]
        X.block_symbol("paper", "QLD", "OPENAPI_TICKER_IS_DENY", "denied")
        it = next(i for i in health.run(send=False)["items"] if i["id"] == "refused_paper")
        assert it["status"] == "error" and "QLD" in it["detail"]
    finally:
        X.unblock_symbols("paper")
