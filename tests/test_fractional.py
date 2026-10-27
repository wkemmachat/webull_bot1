"""Fractional-share test (Go-live → Test trade): half a share by limit or market order, sold straight back."""
import pytest

from app import brokers, db, ledger, testtrade
from conftest import NOW


def test_quantity_text():
    assert brokers.qty_text(5) == "5" and brokers.qty_text(5.0) == "5"
    assert brokers.qty_text(0.5) == "0.5" and brokers.qty_text(1.25) == "1.25" and brokers.qty_text(0.1234567) == "0.123457"


def _run(clock, mode="paper", **kw):
    ledger.fund_in(mode, 2000, 1e9)
    ids = testtrade.start(mode, ["QLD"], **kw)
    for _ in range(6):
        testtrade.tick(mode)
    return db.one("SELECT * FROM test_trades WHERE id=?", (ids[0],))


@pytest.mark.parametrize("ot", ["LIMIT", "MARKET"])
def test_half_a_share_bought_and_sold(clean, clock, ot):
    t = _run(clock, fractional=True, order_type=ot)
    assert t["status"] == "ok", (t["result"], t["error"], t["log"])
    assert t["qty"] == 0.5 and t["bought"] == pytest.approx(0.5) and t["sold"] == pytest.approx(0.5)
    assert t["order_type"] == ot and "0.5" in t["result"]
    st = testtrade.fraction_status("paper")
    assert st[ot]["ok"] and st["verdict"]
    v = testtrade.view("paper")
    assert v["fractional_tests"][0]["id"] == t["id"]
    assert all(s["last"] is None or s["last"]["id"] != t["id"] for s in v["symbols"])   # not the ETF's whole-share test
    assert "QLD" not in testtrade.held("paper")


def test_refused_fraction_does_not_block_the_etf(clean, clock):
    class Refuse(brokers.PaperBroker):
        def place(self, symbol, side, qty, limit, session, cid):
            if testtrade.is_fraction(qty):
                raise brokers.BrokerRejected("OPENAPI_FRACTION_NOT_SUPPORTED: fractional orders not allowed", code="OPENAPI_X",
                                             permanent=True)
            return super().place(symbol, side, qty, limit, session, cid)
    brokers.set_override("paper", Refuse())
    t = _run(clock, fractional=True)
    assert t["status"] == "failed" and t["code"] == "OPENAPI_X"
    from app import execution
    assert "QLD" not in execution.blocked_symbols("paper")
    st = testtrade.fraction_status("paper")
    assert st["LIMIT"]["ok"] is False and "refused" in st["verdict"]
    assert testtrade.status_for_golive("paper").get("QLD") is None          # the whole-share test is still to do


def test_whole_share_tests_are_unchanged(clean, clock):
    t = _run(clock, qty=2, order_type="MARKET")                              # order type only for the fractional test
    assert t["status"] == "ok", t["result"]
    assert t["qty"] == 2 and (t["order_type"] or "LIMIT") == "LIMIT"
    with pytest.raises(testtrade.TestTradeError):
        testtrade.start("paper", ["QLD", "QQQ"], fractional=True)
