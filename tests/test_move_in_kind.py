"""Move between two strategies that hold the same ETF: the shares the receiving strategy wants change hands inside the bot
(one price, no Webull order, no fee); only the rest is raised the usual way. The books still add up to the account."""
import json

import pytest

from app import brokers, db, execution as X, ledger, marketdata as md, moneyops
from app import strategies as S
from conftest import NOW
from test_api import client  # noqa: F401
from test_cross import account_total, books_total, run_all

A, B = "rom_tbd", "rom_vol_ibs"


def frac(on):
    db.set_settings({"exec_fractional_paper": "1" if on else "0"})


def set_target(sid, target, ok=1):
    db.run("INSERT INTO strategy_state(strategy,computed_at,bar_time,state,label,target,ok) VALUES(?,?,?,?,?,?,?) "
           "ON CONFLICT(strategy) DO UPDATE SET target=excluded.target, ok=excluded.ok, bar_time=excluded.bar_time",
           (sid, int(NOW.timestamp()), int(NOW.timestamp()) - 3600, "in", "In", json.dumps(target), ok))


def setup(clock, on=False, empty_b=True):
    """A holds ROM at 99%; B is empty (its money back in bot unassigned) and wants 99% ROM today."""
    frac(on)
    pid = X.build_plan("paper", S.get(A), {"ROM": 0.99}, "signal", clock.dt, brokers.get("paper"))
    run_all(clock, [pid])
    if empty_b:
        moneyops.withdraw("paper", B, 0, everything=True)
        moneyops.to_webull("paper", ledger.pool_cash("paper"))
    set_target(B, {"ROM": 0.99})
    return ledger.get("paper", A)["holdings"]["ROM"]


def broker_orders():
    return len(brokers.get("paper")._acct()["orders"])


def pnl(sid):
    v = ledger.value("paper", sid)
    return v["value"] - v["net_in"]


def test_shares_change_hands_inside_the_bot(clean, clock):
    held = setup(clock)
    n0, cash0 = broker_orders(), brokers.get("paper").account()["cash"]
    pnl_a = pnl(A)
    r = moneyops.move("paper", A, B, 2500)
    assert r["status"] == "done"
    (f,) = r["in_kind"]
    px = md.prices({"ROM"})["ROM"]
    assert f["symbol"] == "ROM" and f["qty"] == int(f["qty"]) and f["qty"] == int(0.99 * 2500 / px)   # whole shares B wants
    # nothing at the broker: no order, the account's cash and positions are as before, and the books still add up
    assert broker_orders() == n0 and brokers.get("paper").account()["cash"] == pytest.approx(cash0)
    assert books_total() == account_total()
    assert ledger.get("paper", A)["holdings"]["ROM"] == pytest.approx(held - f["qty"])
    assert ledger.get("paper", B)["holdings"]["ROM"] == pytest.approx(f["qty"])
    # money: A gave $2,500 (shares + the rest from its cash), B got $2,500; neither made or lost anything by it
    va, vb = ledger.value("paper", A), ledger.value("paper", B)
    assert vb["net_in"] == pytest.approx(2500, abs=0.02) and r["amount"] == pytest.approx(2500, abs=0.02)
    assert va["net_in"] == pytest.approx(7500, abs=0.02)
    assert pnl(A) == pytest.approx(pnl_a, abs=0.05) and pnl(B) == pytest.approx(0, abs=0.05)
    assert vb["cash"] == pytest.approx(2500 - f["value"], abs=0.02)
    # it shows as a done plan with inside-the-bot fills on each side, and in the money list
    plans = db.rows("SELECT * FROM plans WHERE reason='move' ORDER BY id")
    assert [(p["strategy"], p["status"]) for p in plans] == [(A, "done"), (B, "done")]
    orders = db.rows("SELECT * FROM orders WHERE cross_with IS NOT NULL ORDER BY side")
    assert [(o["side"], o["strategy"], o["cross_with"], o["broker_order_id"], o["fee"]) for o in orders] == \
        [("BUY", B, A, "internal", 0.0), ("SELL", A, B, "internal", 0.0)]
    assert json.loads(plans[1]["summary"])["fills"][0]["inside"] == f["qty"]
    ms = db.rows("SELECT * FROM money WHERE kind='move' ORDER BY id")
    assert ms[0]["status"] == "done" and ms[0]["amount"] == pytest.approx(f["value"]) and "no Webull order" in ms[0]["note"]
    assert all(m["status"] == "done" for m in ms)
    assert not db.rows("SELECT * FROM plans WHERE status='active'")
    # B is at its target, so its next check plans nothing worth sending
    w, _ = ledger.weights("paper", B, md.prices({"ROM"}))
    assert w["ROM"] == pytest.approx(0.99, abs=0.035)


def test_fractions_and_no_cash_left_in_the_sender(clean, clock):
    setup(clock, on=True)
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))     # A has no cash for the 1% B keeps as cash
    n0 = broker_orders()
    r = moneyops.move("paper", A, B, 2500)
    assert r["status"] == "done" and r.get("short", 0) < X.MIN_FRACTION_USD      # a crumb under $5 stays in A
    (f,) = r["in_kind"]
    assert f["qty"] != int(f["qty"]) and round(f["qty"], 2) == f["qty"]             # a fraction, to 0.01 like Webull's fills
    assert f["value"] == pytest.approx(2500, abs=X.MIN_FRACTION_USD)               # all of it as shares: nothing to sell
    assert broker_orders() == n0 and books_total() == account_total()
    assert not db.rows("SELECT * FROM plans WHERE status='active'")
    w, _ = ledger.weights("paper", B, md.prices({"ROM"}))
    assert 0.99 <= w["ROM"] <= 1.0


def test_less_than_a_share_short_moves_a_little_less(clean, clock):
    setup(clock, on=False)
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    n0 = broker_orders()
    r = moneyops.move("paper", A, B, 2500)
    px = md.prices({"ROM"})["ROM"]
    assert r["status"] == "done" and broker_orders() == n0
    assert 0 <= r.get("short", 0) < px and r["amount"] == pytest.approx(2500 - r.get("short", 0), abs=0.02)
    assert ledger.value("paper", B)["net_in"] == pytest.approx(r["amount"], abs=0.02)
    assert not db.rows("SELECT * FROM plans WHERE status='active'")


def test_everything(clean, clock):
    held = setup(clock, on=False)
    n0 = broker_orders()
    va = ledger.value("paper", A)["value"]
    r = moneyops.move("paper", A, B, va, everything=True)
    assert r["status"] == "done" and r["in_kind"][0]["qty"] == held                 # every share, nothing sold
    assert broker_orders() == n0
    L = ledger.get("paper", A)
    assert L["holdings"].get("ROM", 0) == 0 and L["cash"] == pytest.approx(0, abs=0.01)
    assert ledger.value("paper", B)["net_in"] == pytest.approx(va, abs=0.05)
    assert books_total() == account_total()


def test_rest_of_a_big_move_is_sold_as_before(clean, clock):
    held = setup(clock, on=False)
    set_target(B, {"ROM": 0.5})                                                     # B wants only half in ROM
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    r = moneyops.move("paper", A, B, 4000)
    assert r["status"] == "pending" and r["in_kind"][0]["value"] <= 0.52 * 4000
    p = db.one("SELECT * FROM plans WHERE id=?", (r["plan_id"],))
    assert p["strategy"] == A and p["status"] == "active" and json.loads(p["on_done"])["move_to"] == B
    # B waits for the cash before it trades, so it does not sell the ROM it just got and buy it back later
    s = S.get(B)
    ev = dict(s.evaluate(clock.dt), ok=True, target={"ROM": 0.5})
    assert ledger.move_rest_pending("paper", B)
    assert X.reconcile("paper", s, ev, clock.dt, brokers.get("paper"), db.get_settings()) is None
    run_all(clock, [r["plan_id"]])
    assert not ledger.move_rest_pending("paper", B)
    assert ledger.value("paper", B)["net_in"] == pytest.approx(4000, abs=60)       # the sale's price may move a little
    assert books_total() == account_total()


@pytest.mark.parametrize("case", ["wait", "paused", "no_state", "failed_state", "other_symbol", "active_plan"])
def test_falls_back_to_cash(clean, clock, case):
    setup(clock, on=False)
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))     # so the old way has to sell
    invest = "now"
    if case == "wait":
        invest = "wait"
    elif case == "paused":
        S.update(B, control="paused")
    elif case == "no_state":
        db.run("DELETE FROM strategy_state WHERE strategy=?", (B,))
    elif case == "failed_state":
        set_target(B, {"ROM": 0.99}, ok=0)
    elif case == "other_symbol":
        set_target(B, {"USD": 0.99})
    elif case == "active_plan":
        assert X.build_plan("paper", S.get(A), {"ROM": 0.5}, "signal", clock.dt, brokers.get("paper"))
    r = moneyops.move("paper", A, B, 2500, invest=invest)
    assert "in_kind" not in r and r["status"] == "pending"
    assert not db.rows("SELECT * FROM orders WHERE cross_with IS NOT NULL")


def test_api_reports_the_shares(client, clock):
    from test_api import sign_in
    sign_in(client)
    setup(clock)
    r = client.post("/api/money/move", json={"mode": "paper", "strategy": A, "other": B, "amount": 1000, "invest": "now"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "done" and d["in_kind"][0]["symbol"] == "ROM"
    m = client.get("/api/money?mode=paper").json()
    assert any("no Webull order" in (x.get("note") or "") for x in m["moves"])


def test_receiver_with_a_running_plan_gets_cash(clean, clock):
    setup(clock, on=False, empty_b=False)                                           # B still has its $10,000 start money
    assert X.build_plan("paper", S.get(B), {"ROM": 0.99}, "signal", clock.dt, brokers.get("paper"))
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    r = moneyops.move("paper", A, B, 2500)
    assert "in_kind" not in r and r["status"] == "pending"


def test_rest_that_cannot_be_raised_keeps_the_shares_and_warns(clean, clock, monkeypatch):
    setup(clock)
    set_target(B, {"ROM": 0.5})
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    monkeypatch.setattr(X, "build_plan", lambda *a, **k: None)                    # e.g. no price for the sale
    r = moneyops.move("paper", A, B, 4000)
    assert r["status"] == "done" and r["warning"] and r["amount"] == r["in_kind_value"] > 0
    assert ledger.value("paper", B)["net_in"] == pytest.approx(r["amount"])          # the books say what really moved
    assert books_total() == account_total()


def test_plain_move_does_not_wait_for_the_check(clean, clock):
    from app import engine
    setup(clock)
    set_target(B, {"USD": 0.99})                                                    # nothing A holds: the cash way, no lock
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    assert engine._lock.acquire(blocking=False)
    try:
        r = moneyops.move("paper", A, B, 1000)
    finally:
        engine._lock.release()
    assert r["status"] == "pending" and "in_kind" not in r


def test_extra_shares_stay_inside_half_the_band(clean, clock):
    setup(clock, on=True)
    band = S.get(B).params["rebalance_band_pct"]
    S.update(B, params={"rebalance_band_pct": 1})
    try:
        db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
        r = moneyops.move("paper", A, B, 2500)
    finally:
        S.update(B, params={"rebalance_band_pct": band})
    assert r["status"] == "pending"                                                 # the rest is sold, not over-weighted:
    assert 0.99 * 2500 < r["in_kind_value"] <= (0.99 + 0.005) * 2500 + 0.01        # at most half the 1% band above target


def test_rest_that_throws_does_not_freeze_the_receiver(clean, clock, monkeypatch):
    setup(clock)
    set_target(B, {"ROM": 0.5})
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))

    def boom(*a, **k):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(X, "build_plan", boom)
    r = moneyops.move("paper", A, B, 4000)
    assert r["status"] == "done" and "database is locked" in r["warning"]
    assert not db.rows("SELECT * FROM money WHERE status='pending'")                # the rest's row is marked failed
    assert db.one("SELECT COUNT(*) n FROM money WHERE status='failed' AND other=?", (B,))["n"] == 1
    assert not ledger.move_rest_pending("paper", B)


def test_a_new_signal_does_not_wait_for_the_rest(clean, clock):
    setup(clock)
    set_target(B, {"ROM": 0.5})
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy=?", (A,))
    r = moneyops.move("paper", A, B, 4000)
    assert r["status"] == "pending"
    s, b = S.get(B), brokers.get("paper")
    ev = dict(s.evaluate(clock.dt), ok=True)
    assert X.reconcile("paper", s, dict(ev, target={"ROM": 0.5}), clock.dt, b, db.get_settings()) is None   # same signal: waits
    pid = X.reconcile("paper", s, dict(ev, target={}), clock.dt, b, db.get_settings())                    # an exit: sells now
    assert pid and db.one("SELECT reason FROM plans WHERE id=?", (pid,))["reason"] in ("signal", "stop")


def test_money_actions_do_not_overlap(clean):
    assert moneyops._MONEY.acquire(blocking=False)
    import threading
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("e", pytest.raises(ValueError, moneyops.withdraw, "paper", A, 100)))
    t.start(); t.join()
    moneyops._MONEY.release()
    assert "Another money action" in str(out["e"].value)
