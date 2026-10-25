"""Add, withdraw and move money between strategies (paper mode)."""
import pytest

from app import brokers, db, execution as X, ledger, marketdata as md, moneyops
from app import strategies as S
from conftest import NOW


def test_paper_start(clean):
    acct = brokers.get("paper").account()
    assert acct["cash"] == 150000
    for r in S.rows():
        assert ledger.get("paper", r["id"])["cap_in"] == 10000
    assert ledger.pool_cash("paper") == 0                                          # bot unassigned starts empty
    assert ledger.outside_cash("paper", acct["cash"]) == pytest.approx(150000 - 10000 * len(S.rows()))   # not for the bot


def test_three_layers(clean):
    cash = lambda: brokers.get("paper").account()["cash"]
    with pytest.raises(ValueError):                                                 # nothing given to the bot yet
        moneyops.add("paper", "gold_sta", 100)
    free = ledger.outside_cash("paper", cash())                                     # 100k − 10k per strategy
    with pytest.raises(ValueError):                                                 # cannot give the bot more than is free
        moneyops.to_bot("paper", free + 0.01)
    moneyops.to_bot("paper", 8000)                                                  # Webull → bot
    assert ledger.pool_cash("paper") == 8000 and ledger.outside_cash("paper", cash()) == pytest.approx(free - 8000)
    moneyops.add("paper", "gold_sta", 2000)                                         # bot → one strategy
    assert ledger.value("paper", "gold_sta")["net_in"] == 12000 and ledger.pool_cash("paper") == 6000
    r = moneyops.split("paper", moneyops.equal_split(4000, ["silver_dc", "silver_st", "qld_regime"]))
    assert r["pool"] == pytest.approx(2000)
    assert ledger.value("paper", "silver_dc")["net_in"] == pytest.approx(11333.34)
    assert ledger.value("paper", "qld_regime")["net_in"] == pytest.approx(11333.33)
    with pytest.raises(ValueError):
        moneyops.split("paper", {"gold_sta": 3000})                                 # more than bot unassigned
    moneyops.withdraw("paper", "gold_sta", 1000)                                    # strategy → bot unassigned
    assert ledger.pool_cash("paper") == pytest.approx(3000)
    with pytest.raises(ValueError):
        moneyops.to_webull("paper", 3000.5)
    moneyops.to_webull("paper", 3000)                                               # bot → Webull
    assert ledger.pool_cash("paper") == 0
    assert ledger.outside_cash("paper", cash()) == pytest.approx(free - 8000 + 3000)
    kinds = [m["kind"] for m in ledger.moves("paper")]
    assert {"to_bot", "to_webull", "add", "withdraw"} <= set(kinds)


def test_equal_split_cents():
    assert moneyops.equal_split(10, ["a", "b", "c"]) == {"a": 3.34, "b": 3.33, "c": 3.33}


def test_waiting_money_is_kept_out_of_the_first_plan(clean, clock):
    moneyops.to_bot("paper", 5000)
    moneyops.add("paper", "qld_regime", 5000, invest="wait")
    assert ledger.waiting_cash(ledger.get("paper", "qld_regime")) == 5000
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    from test_execution import run_until_done
    run_until_done(clock, pid)
    L = ledger.get("paper", "qld_regime")
    assert 5000 <= L["cash"] < 5000 + 10000 * 0.05                 # the $10,000 start money invested, the $5,000 still waits


def test_withdraw_from_cash(clean):
    r = moneyops.withdraw("paper", "silver_dc", 2500)
    assert r["status"] == "done" and ledger.pool_cash("paper") == 2500
    v = ledger.value("paper", "silver_dc")
    assert v["net_in"] == 7500 and v["cash"] == 7500
    with pytest.raises(ValueError):
        moneyops.withdraw("paper", "silver_dc", 999999)


def test_withdraw_sells_when_invested(clean, clock):
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    from test_execution import run_until_done
    run_until_done(clock, pid)
    r = moneyops.withdraw("paper", s.id, 4000)
    assert r["status"] == "pending"
    plan = run_until_done(clock, r["plan_id"])
    assert plan["reason"] == "withdraw" and plan["status"] == "done"
    m = db.one("SELECT * FROM money WHERE plan_id=?", (r["plan_id"],))
    assert m["status"] == "done" and m["done_amount"] == pytest.approx(4000, rel=0.05)
    assert ledger.get("paper", s.id)["cap_out"] == pytest.approx(m["done_amount"])


def test_move(clean):
    r = moneyops.move("paper", "gold_sta", "semis_regime", 3000)
    assert r["status"] == "done"
    assert ledger.value("paper", "gold_sta")["net_in"] == 7000
    assert ledger.value("paper", "semis_regime")["net_in"] == 13000
    with pytest.raises(ValueError):
        moneyops.move("paper", "gold_sta", "gold_sta", 10)


def _sig(sid, t, kind, frm, to):
    db.run("INSERT OR IGNORE INTO signals(strategy,t,kind,from_state,to_state,price,text,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
           (sid, t, kind, frm, to, 1.0, "test", "live", t))


def test_wait_for_next_buy_signal(clean, clock):
    s = S.get("gold_st30")
    db.run("UPDATE ledger SET cash=0, cap_in=0 WHERE mode='paper' AND strategy=?", (s.id,))
    moneyops.to_bot("paper", 5000)
    moneyops.add("paper", s.id, 5000, invest="wait")
    ev = dict(s.evaluate(NOW), target={"UGL": 0.99}, state="long")
    b = brokers.get("paper")
    assert X.reconcile("paper", s, ev, NOW, b, db.get_settings()) is None          # long today, but no NEW buy yet
    t0 = int(NOW.timestamp())
    clock.advance(hours=4)
    _sig(s.id, t0 + 3600, "SELL", "long", "flat")                                    # a sell does not start it
    assert X.waiting_for_buy("paper", s)
    assert X.reconcile("paper", s, dict(ev, target=s.cash_target()), clock.dt, b, db.get_settings()) is None
    assert ledger.get("paper", s.id)["cash"] == 5000
    _sig(s.id, t0 + 7200, "BUY", "flat", "long")                                     # the next buy invests it
    assert X.waiting_for_buy("paper", s) is None
    pid = X.reconcile("paper", s, ev, clock.dt, b, db.get_settings())
    assert pid and db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND side='BUY' AND symbol='UGL'", (pid,))["n"]
    assert not ledger.get("paper", s.id)["hold_cash"]


def test_regime_buy_means_a_step_up():
    q = S.get("qld_regime")
    assert q.is_buy_signal({"kind": "STATE", "from_state": "off", "to_state": "1x"})
    assert q.is_buy_signal({"kind": "STATE", "from_state": "0.5x", "to_state": "2x"})
    assert not q.is_buy_signal({"kind": "STATE", "from_state": "2x", "to_state": "0.5x"})
    assert not q.is_buy_signal({"kind": "STATE", "from_state": "1x", "to_state": "off"})


def test_default_setting_applies_to_add(clean):
    db.set_settings({"new_money_start": "buy"})
    moneyops.to_bot("paper", 2000)
    moneyops.add("paper", "silver_st", 1000)
    assert ledger.get("paper", "silver_st")["hold_cash"]
    moneyops.add("paper", "silver_st", 1000, invest="now")                          # invested now; the first $1,000 still waits
    assert ledger.waiting_cash(ledger.get("paper", "silver_st")) == 1000


def test_move_can_wait(clean):
    moneyops.move("paper", "gold_sta", "semis_regime", 2000, invest="wait")
    assert ledger.get("paper", "semis_regime")["hold_cash"]


def test_waiting_cash_does_not_join_a_running_strategy(clean, clock):
    s = S.get("qld_regime")
    b = brokers.get("paper")
    ev = dict(s.evaluate(NOW), target=s.target_for("2x"))
    from test_execution import run_until_done
    run_until_done(clock, X.reconcile("paper", s, ev, NOW, b, db.get_settings()))
    before = ledger.get("paper", s.id)["holdings"].get("QLD", 0)
    moneyops.to_bot("paper", 5000)
    moneyops.add("paper", s.id, 5000, invest="wait")
    clock.advance(hours=1)
    assert X.reconcile("paper", s, ev, clock.dt, b, db.get_settings()) is None     # no drift rebalance into the new cash
    assert ledger.get("paper", s.id)["holdings"].get("QLD", 0) == before
    w, tot = ledger.weights("paper", s.id, md.prices({"QLD"}))
    assert w["QLD"] == pytest.approx(0.99, abs=0.02)
    r = moneyops.withdraw("paper", s.id, 2000)                                      # withdrawals take waiting cash first
    assert r["status"] == "done" and ledger.waiting_cash(ledger.get("paper", s.id)) == pytest.approx(3000)
