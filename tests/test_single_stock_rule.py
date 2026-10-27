"""Webull Thailand refuses leveraged ETFs on single stocks below 50M THB: an account rule, not one ETF."""
from app import brokers, db, execution as X, views
from app import strategies as S

MSG = ("HTTP Status: 417, Code: OPENAPI_ONLY_UHNWE_SINGLE_STOCK_REVERSE_ETF_LIMIT, Msg: Non-Ultra High Net Worth clients "
       "(below 50M THB) are not permitted to trade leveraged or inverse ETFs on single stocks., RequestID: x")


def test_the_refusal_is_permanent():
    e = brokers.parse_rejection(MSG)
    assert e.code == brokers.SINGLE_STOCK_LEV_CODE and e.permanent


def test_one_refusal_blocks_every_single_stock_etf_and_falls_back_to_stocks(clean):
    s = S.get("c27_mom2x")
    emap = s.etf_map()
    assert len(emap) > 3
    first = next(iter(emap.values()))
    X.block_symbol("live", first, brokers.SINGLE_STOCK_LEV_CODE, "refused")
    try:
        b = X.blocked_symbols("live")
        assert set(emap.values()) <= set(b) and X.single_stock_refused("live") and not X.single_stock_refused("test")
        assert "QLD" not in b and "GLD" not in b                       # index / commodity ETFs are not affected
        card = views.strategy_card("live", s)
        assert card["notice"] and "works like C2-7 Momentum 1x" in card["notice"]
        assert views.strategy_card("live", S.get("c27_mom"))["notice"] is None
        stock = next(iter(emap))
        assert s.fallback_for(emap[stock]) == stock
    finally:
        X.unblock_symbols("live")
    assert views.strategy_card("live", s)["notice"] is None


def test_startup_applies_the_rule_from_a_refused_test_trade(clean):
    """As on the live server: the refusal is in test_trades.code / result (error is empty)."""
    from app import engine
    db.run("INSERT INTO test_trades(mode, symbol, qty, status, created_at, updated_at, code, result) VALUES(?,?,?,?,?,?,?,?)",
           ("live", "AAPU", 1, "failed", 1, 1, brokers.SINGLE_STOCK_LEV_CODE, "Webull refused the buy: " + MSG))
    try:
        assert not X.single_stock_refused("live")
        engine._single_stock_rule_from_tests()
        assert X.single_stock_refused("live") and "NVDL" in X.blocked_symbols("live")
    finally:
        X.unblock_symbols("live")
