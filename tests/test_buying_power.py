"""Buys and Webull's buying power (20 Nov 2026): fills not booked yet are not "money that left the account"; when the
buying power is below the cash the buys wait (one message, no top-up plans every few minutes) and resume when it is back;
it is shared between the strategies that buy; orders for less than one share are priced at the market."""
import pytest

from app import brokers, db, execution as X, ledger
from app import strategies as S
from conftest import NOW
from test_execution import run_until_done


def _order(status="submitted", qty=10, limit=33.0, applied=0, side="BUY"):
    db.run("INSERT INTO orders(plan_id, mode, strategy, step, lot, lots, symbol, side, qty, limit_price, status, applied_qty, scheduled_at) "
           "VALUES(0,'paper','qld_regime',1,1,5,'QLD',?,?,?,?,?,0)", (side, qty, limit, status, applied))


def test_unbooked_fill_is_not_money_that_left(clean):
    books = ledger.bot_cash("paper")
    acct = {"cash": books - 330.0, "buying_power": 1e9}           # Webull took $330 for a fill the bot has not booked yet
    g = X.Guard("paper", acct, db.get_settings())
    assert g.allow(100)[0] == 0 and g.kind == "books"             # no order in flight: a real mismatch, blocked
    _order(qty=10, limit=33.0)                                    # a sent buy of 10 × $33 whose fill is not booked
    g = X.Guard("paper", acct, db.get_settings())
    assert g.inflight == pytest.approx(330.0)
    assert g.allow(100) == (100, None)                            # now explained: allowed
    db.run("UPDATE orders SET applied_qty=10")                    # booked: nothing in flight any more
    assert X._inflight_buys("paper") == pytest.approx(0.0)


def _low_bp(monkeypatch, bp):
    real = brokers.PaperBroker.account
    state = {"bp": bp}

    def acct(self):
        a = real(self)
        if state["bp"] is not None:
            a["buying_power"] = state["bp"]
        return a
    monkeypatch.setattr(brokers.PaperBroker, "account", acct)
    return state


def test_low_buying_power_waits_once_and_resumes(clean, clock, monkeypatch):
    state = _low_bp(monkeypatch, 12.67)
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    lots = db.rows("SELECT * FROM orders WHERE plan_id=? AND side='BUY'", (pid,))
    assert lots and all(o["status"] == "skipped" and o["error"].startswith("waiting for Webull buying power") for o in lots)
    w = X.bp_wait("paper")
    assert w and w["bp"] == pytest.approx(12.67) and w["sids"] == ["qld_regime"]
    assert db.one("SELECT COUNT(*) n FROM events WHERE title='Buys wait for Webull buying power'")["n"] == 1
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE 'Buy blocked%'")["n"] == 0        # no error per lot
    msgs = db.rows("SELECT * FROM line_queue WHERE event='lot_failed'")
    assert len(msgs) == 1 and "buying power" in msgs[0]["text"] and not msgs[0]["critical"]
    # no top-up plan while waiting
    assert X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), clock.dt, brokers.get("paper"), db.get_settings()) is None
    # Webull frees the money: the next check resumes the buys
    state["bp"] = None
    db.set_state("bpchk:paper", 0)
    X._bp_watch("paper", brokers.get("paper"))
    assert X.bp_wait("paper") is None
    assert db.one("SELECT COUNT(*) n FROM events WHERE title='Buys resume: buying power is back'")["n"] == 1
    pid2 = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), clock.dt, brokers.get("paper"), db.get_settings())
    assert pid2                                                   # the top-up is planned again
    run_until_done(clock, pid2)
    assert ledger.get("paper", s.id)["holdings"].get("QLD", 0) > 0


def test_a_small_rise_does_not_resume(clean, monkeypatch):
    db.set_state("bpwait:paper", {"at": 1, "bp": 12.0, "cash": 20000, "sids": ["qld_regime"], "blocked": 3})
    X._bp_watch("paper", brokers.get("paper"), {"cash": 20000.0, "buying_power": 60.0})
    assert X.bp_wait("paper")                                     # +$48: still waiting
    X._bp_watch("paper", brokers.get("paper"), {"cash": 20000.0, "buying_power": 900.0})
    assert X.bp_wait("paper") is None                             # +$888: resume


def test_buying_power_is_shared_by_cash(clean):
    for sid in ("qld_regime", "semis_regime"):
        db.run("INSERT INTO plans(mode, strategy, status, reason, lots, interval_min) VALUES('paper', ?, 'active', 'rebalance', 5, 1)", (sid,))
        pid = db.one("SELECT MAX(id) i FROM plans")["i"]
        db.run("INSERT INTO orders(plan_id, mode, strategy, step, lot, lots, symbol, side, status, scheduled_at) "
               "VALUES(?, 'paper', ?, 1, 1, 5, 'QLD', 'BUY', 'scheduled', 0)", (pid, sid))
    acct = {"cash": ledger.bot_cash("paper") + 50000, "buying_power": 1000.0}
    g = X.Guard("paper", acct, db.get_settings())
    g.share_fairly("paper")
    assert g.fair and sum(g.fair.values()) == pytest.approx(1000.0)
    first = g.allow(900, "qld_regime")[0]
    assert first == pytest.approx(500.0, abs=1) and g.kind == "bp"           # its half, not all of it
    g.spent(first, "qld_regime")
    assert g.allow(900, "semis_regime")[0] == pytest.approx(500.0, abs=1)   # the other half is still there


def test_marketable_price_for_less_than_one_share():
    q = {"price": 327.0, "bid": 326.8, "ask": 327.2}
    assert X._marketable(q, "SELL", 327.56) == pytest.approx(round(326.8 * 0.995, 2))
    assert X._marketable(q, "BUY", 326.0) == pytest.approx(round(327.2 * 1.005, 2))
    e = brokers.BrokerRejected("OPENAPI_FRACTION_V2_LIMIT_ORDER_QUANTITY_TOO_SMALL: Fractional limit orders below 1 share must be at a marketable price.")
    assert X._needs_marketable(e)


def test_marketable_refusal_does_not_turn_fractions_off(clean):
    db.set_state("frac_refused:live", {"GLD": {"at": 1, "code": None, "msg": "OPENAPI_FRACTION_V2_LIMIT_ORDER_QUANTITY_TOO_SMALL: "
                                                 "Fractional limit orders below 1 share must be at a marketable price."},
                                       "XYZ": {"at": 1, "code": "FRACTION_NOT_SUPPORTED", "msg": "no fractions"}})
    X.repair_marketable_refusals()
    assert set(X.fraction_refused("live")) == {"XYZ"}
