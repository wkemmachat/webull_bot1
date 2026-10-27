"""Idle-cash box (waiting money / cash inside the rebalance band, Invest now / Top up now) and the Portfolio page."""
import pytest

from app import brokers, db, execution as X, idle, ledger, moneyops, portfolio
from app import strategies as S
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)
from test_execution import run_until_done


def _invested(clock, sid="qld_regime"):
    db.set_settings({"exec_fractional_paper": "1"})
    s = S.get(sid)
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    _store_state(s)
    return s


def _store_state(s):
    import json
    ev = s.evaluate(NOW)
    db.run("INSERT OR REPLACE INTO strategy_state(strategy,computed_at,bar_time,state,label,target,signal_time,ok,error,detail) "
           "VALUES(?,?,?,?,?,?,?,1,NULL,?)", (s.id, 1, ev["bar_time"], ev["state"], ev["label"], json.dumps(ev["target"]),
                                             ev.get("signal_time"), json.dumps({"checks": ev.get("checks"), **(ev.get("detail") or {})})))


def test_small_top_up_shows_as_band_cash_and_tops_up(clean, clock):
    s = _invested(clock)
    assert idle.view("paper", s) is None                               # fully invested: no box
    ledger.fund_in("paper", 300, 1e9)
    moneyops.add("paper", s.id, 300, "now")                            # 3% of $10,300: inside the 10% band
    v = idle.view("paper", s)
    assert v and 150 < v["band"] < 400 and v["action"] == "topup" and v["waiting"] == 0
    assert "band" in v and v["buys"] and v["next_buy"]
    r = idle.topup_now("paper", s.id)
    p = db.one("SELECT * FROM plans WHERE id=?", (r["plan_id"],))
    assert not db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND side='SELL'", (p["id"],))["n"]
    run_until_done(clock, p["id"])
    assert ledger.get("paper", s.id)["cash"] < 150
    assert idle.view("paper", s) is None
    with pytest.raises(ValueError):
        idle.topup_now("paper", "c27_mom")                             # baskets never top up


def test_waiting_money_offers_invest_now(clean, clock):
    s = _invested(clock)
    ledger.fund_in("paper", 1000, 1e9)
    moneyops.add("paper", s.id, 1000, "wait")
    v = idle.view("paper", s)
    assert v["waiting"] == pytest.approx(1000) and v["action"] == "invest" and v["waiting_since"]
    S.update(s.id, control="paused")
    assert idle.view("paper", S.get(s.id)) is None                    # not active: no box


def test_next_buy_text_for_regime_states():
    s = S.get("qld_regime")
    assert "SMA200" in idle.next_buy_text(s, {"state": "off", "detail": {"sma_long": 600.0, "close": 590.0}})
    assert "full size" in idle.next_buy_text(s, {"state": "2x", "detail": {}})
    assert "volatility" in idle.next_buy_text(s, {"state": "0.5x", "detail": {"vol": 0.35}})


def test_suggest_moves_uses_unassigned_first():
    rows = [{"id": "a", "gap": -400.0}, {"id": "b", "gap": 300.0}, {"id": "c", "gap": 250.0}, {"id": "d", "gap": 20.0}]
    m = portfolio.suggest_moves(rows, 200.0)
    assert m[0] == {"kind": "give", "to": "b", "amount": 200.0}
    assert {"kind": "move", "from": "a", "to": "c", "amount": 250.0} in m
    assert {"kind": "move", "from": "a", "to": "b", "amount": 100.0} in m
    assert all(x.get("to") != "d" for x in m)                         # under $50: no move


def test_portfolio_view_mix_exposure_and_plan(clean, clock):
    _invested(clock)
    from app import expected
    expected.set_plan({"qld_regime": 50, "semis_regime": 50})
    v = portfolio.view("paper")
    ids = {r["id"] for r in v["rows"]}
    assert "qld_regime" in ids and v["total"] > 0
    assert any(e["market"] == "Nasdaq-100 2x" for e in v["exposure"])
    assert sum(e["pct"] for e in v["exposure"]) == pytest.approx(100, abs=0.1)
    q = next(r for r in v["rows"] if r["id"] == "qld_regime")
    assert q["target"] == pytest.approx(0.5 * (v["total"] + v["unassigned"]), abs=1)
    assert portfolio.market_of("AAPL") == "Big tech stocks" and portfolio.market_of("SGOV") == "T-bills"


def test_portfolio_and_strategy_api(client):
    sign_in(client)
    r = client.get("/api/portfolio?mode=paper")
    assert r.status_code == 200 and "exposure" in r.json()
    d = client.get("/api/strategies/qld_regime?mode=paper").json()
    assert "idle" in d
    r = client.post("/api/money/topup", json={"mode": "paper", "strategy": "c27_mom"})
    assert r.status_code == 400
