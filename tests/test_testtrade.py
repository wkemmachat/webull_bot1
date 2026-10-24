"""Test trade: buy 1 share of a strategy ETF and sell it back, paid from bot unassigned only."""
import pytest

from app import brokers, db, execution as X, golive, ledger, marketdata as md, testtrade as T
from conftest import NOW
from test_webull_rules import REFUSED


def _fund(amount=500.0):
    ledger.fund_in("paper", amount, brokers.get("paper").account()["cash"])


def _strategy_books():
    return [(r["strategy"], round(r["cash"], 2)) for r in db.rows("SELECT strategy, cash FROM ledger WHERE mode='paper' ORDER BY strategy")]


def test_symbols_come_from_the_strategies():
    s = T.symbols()
    assert {"QLD", "USD", "UGL", "AGQ", "SGOV", "BIL", "GLD"} <= set(s)
    assert "QLD + Trend + bear-dip" in s["QLD"]


def test_round_trip_costs_only_spread_and_fees(clean, clock):
    _fund()
    books = _strategy_books()
    T.start("paper", ["SGOV"])
    for _ in range(4):
        clock.advance(seconds=30)
        T.tick("paper")
    t = db.one("SELECT * FROM test_trades WHERE symbol='SGOV'")
    assert t["status"] == "ok" and t["bought"] == 1 and t["sold"] == 1
    cost = t["buy_value"] - t["sell_value"] + t["buy_fee"] + t["sell_fee"]
    assert 0 < cost < 1
    assert ledger.pool_cash("paper") == pytest.approx(500 - cost, abs=0.01)
    assert _strategy_books() == books                                     # no strategy money touched
    assert T.held("paper") == {}
    assert (brokers.get("paper").account()["positions"].get("SGOV") or {}).get("qty", 0) == 0
    assert T.status_for_golive("paper")["SGOV"] == "ok"


def test_only_strategy_symbols_and_small_sizes(clean):
    _fund()
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["TSLA"])
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["SGOV"], qty=50)


def test_needs_money_in_bot_unassigned(clean, clock):
    T.start("paper", ["QLD"])
    t = db.one("SELECT * FROM test_trades WHERE symbol='QLD'")
    assert t["status"] == "failed" and "bot unassigned" in t["result"]
    assert db.one("SELECT COUNT(*) n FROM orders")["n"] == 0


class Refuses(brokers.PaperBroker):
    def place(self, symbol, side, qty, limit, session, cid):
        if symbol == "QLD":
            raise brokers.parse_rejection(REFUSED)
        return super().place(symbol, side, qty, limit, session, cid)


def test_refusal_is_recorded_for_the_checklist(clean, clock):
    _fund()
    brokers.set_override("paper", Refuses())
    T.start("paper", ["QLD"])
    t = db.one("SELECT * FROM test_trades WHERE symbol='QLD'")
    assert t["status"] == "failed" and t["code"] == "OPENAPI_IS_TH_FIRST_ETF_PLACE"
    assert ledger.pool_cash("paper") == pytest.approx(500)
    assert T.status_for_golive("paper")["QLD"] == "permission"
    item = next(i for s in golive.report("paper")["sections"] for i in s["items"] if i["key"] == "t_symbols")
    assert "permission: QLD" in item["detail"]
    X.unblock_symbols("paper")


class NeverFills(brokers.PaperBroker):
    def _try_fill(self, a, o):
        return


def test_buy_that_never_fills_gives_up_cleanly(clean, clock):
    _fund()
    brokers.set_override("paper", NeverFills())
    T.start("paper", ["SGOV"])
    for _ in range(12):
        clock.advance(seconds=70)
        T.tick("paper")
    t = db.one("SELECT * FROM test_trades WHERE symbol='SGOV'")
    assert t["status"] == "failed" and "not filled" in t["result"] and t["tries"] == T.BUY_TRIES
    assert ledger.pool_cash("paper") == pytest.approx(500)


class SellNeverFills(brokers.PaperBroker):
    def _try_fill(self, a, o):
        if o["side"] == "BUY":
            return super()._try_fill(a, o)


def test_sale_that_never_fills_is_held_and_alerted(clean, clock):
    _fund()
    brokers.set_override("paper", SellNeverFills())
    T.start("paper", ["SGOV"])
    for _ in range(30):
        clock.advance(seconds=70)
        T.tick("paper")
    t = db.one("SELECT * FROM test_trades WHERE symbol='SGOV'")
    assert t["status"] == "holding" and T.held("paper") == {"SGOV": 1}
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE critical=1")["n"] >= 1
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["SGOV"])                         # not while it still holds shares
    brokers.set_override("paper", None)
    T.sell_again(t["id"])
    for _ in range(3):
        clock.advance(seconds=30)
        T.tick("paper")
    assert db.one("SELECT status FROM test_trades WHERE id=?", (t["id"],))["status"] == "ok"
    assert T.held("paper") == {}


def test_waits_for_the_market(clean, clock):
    _fund()
    clock.set(NOW.replace(hour=23))                          # 19:00 New York: closed
    T.start("paper", ["SGOV"])
    t = db.one("SELECT * FROM test_trades WHERE symbol='SGOV'")
    assert t["status"] == "queued" and "market" in t["error"]
    clock.set(NOW)
    md.clear_quotes()
    X.process(NOW)                                           # the scheduler moves it on
    for _ in range(3):
        clock.advance(seconds=30)
        X.process(clock.dt)
    assert db.one("SELECT status FROM test_trades WHERE id=?", (t["id"],))["status"] == "ok"
