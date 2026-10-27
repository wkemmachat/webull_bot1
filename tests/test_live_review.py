"""Findings from the first Live allocation (26 Oct 2026): money given to a stopping strategy, waiting cash on strategies
that are already in a position, the health recompute for the C2-7 baskets and the Go-live symbol list."""
import pytest

from app import brokers, db, execution as X, health, ledger, moneyops, testtrade
from app import strategies as S
from conftest import NOW


def test_every_strategy_has_a_working_independent_recompute():
    for s in S.all_instances():
        tbl = health.indicator_table(s, NOW, rows=30)
        assert tbl["rows"], s.id
        assert tbl["max_diff"] < 1e-6, (s.id, tbl["max_diff"])


def test_c27_recompute_checks_supertrend_rsi_and_state():
    tbl = health.indicator_table(S.get("c27_mom"), NOW, rows=20)
    assert "Supertrend · check" in tbl["cols"] and all(r["ok"] for r in tbl["rows"])


def test_stopping_with_nothing_to_sell_becomes_stopped(clean):
    S.update("c27_mom", control="stopping")
    S.update("qld_regime", control="stopping")
    db.run("INSERT OR REPLACE INTO holdings(mode,strategy,symbol,qty,cost) VALUES('paper','qld_regime','QLD',3,300)")
    done = X.finish_stops()
    assert "c27_mom" in done and S.row("c27_mom")["control"] == "stopped"
    assert S.row("qld_regime")["control"] == "stopping"           # still holds QLD: its stop plan finishes it
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE 'C2-7 Momentum 1x: stopped'")["n"] == 1


def test_money_to_a_stopping_strategy_warns(clean):
    S.update("c27_mom", control="stopping")
    ledger.fund_in("live", 1000, 5000)
    r = moneyops.add("live", "c27_mom", 400, "wait")
    assert "will not buy" in r["warning"]
    r2 = moneyops.split("live", {"usd_ibs": 100, "c27_mom": 100}, "now")
    assert len(r2["warnings"]) == 1
    assert moneyops.add("live", "usd_ibs", 50, "now").get("warning") is None


def test_invest_now_ends_the_wait(clean):
    ledger.fund_in("live", 1000, 5000)
    moneyops.add("live", "qld_regime", 500, "wait")
    L = ledger.get("live", "qld_regime")
    assert L["hold_cash"] and ledger.waiting_cash(L) == pytest.approx(500)
    r = moneyops.invest_now("live", "qld_regime")
    assert r["amount"] == pytest.approx(500)
    L = ledger.get("live", "qld_regime")
    assert not L["hold_cash"] and ledger.waiting_cash(L) == 0 and L["applied_target"] is None
    with pytest.raises(ValueError):
        moneyops.invest_now("live", "qld_regime")                # nothing waits any more
    S.update("c27_mom", control="stopped")
    moneyops.add("live", "c27_mom", 100, "wait")
    with pytest.raises(ValueError):
        moneyops.invest_now("live", "c27_mom")                   # a stopped strategy does not buy


def test_golive_symbols_skip_stopped_strategies_and_refused_single_stock_etfs(clean):
    every = set(testtrade.symbols())
    assert "AAPU" in every and "AAPL" in every
    S.update("c27_mom2x", control="stopped")
    need = set(testtrade.status_for_golive("live"))
    assert "AAPU" not in need and "AAPL" in need                 # 1x still active
    S.update("c27_mom2x", control="active")
    X.block_symbol("live", "AAPU", brokers.SINGLE_STOCK_LEV_CODE, "refused")
    try:
        need = set(testtrade.status_for_golive("live"))
        assert not (need & X.single_stock_etfs()) and "QLD" in need
        assert "AAPU" in set(testtrade.status_for_golive("test"))  # the rule is per account
    finally:
        X.unblock_symbols("live")


def test_stopped_strategy_without_money_is_marked_idle(clean):
    from app import views
    S.update("c27_mom2x", control="stopped")
    cards = {c["id"]: c for c in views.strategies_list("live")["strategies"]}
    assert cards["c27_mom2x"]["idle"] is True                    # stopped, nothing in Live
    assert cards["qld_regime"]["idle"] is False                  # active
    paper = {c["id"]: c for c in views.dashboard("paper")["strategies"]}
    assert paper["c27_mom2x"]["idle"] is False                   # stopped but still holds its paper cash
