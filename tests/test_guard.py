"""The money guard: buys can never use money outside the bot's allocation."""
import pytest

from app import brokers, db, execution as X, ledger, moneyops
from app import strategies as S
from conftest import NOW
from test_execution import run_until_done


def test_floor_blocks_buys(clean, clock):
    acct = brokers.get("paper").account()
    db.set_settings({"protect_floor_paper": str(acct["cash"] - 3000)})     # only $3,000 above the floor
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    spent = 10000 - ledger.get("paper", s.id)["cash"]
    assert spent <= 3000 + 1                                              # the floor held
    assert brokers.get("paper").account()["cash"] >= float(db.get_setting("protect_floor_paper")) - 1
    assert db.get_state("guard_block:paper")                               # and the block was recorded
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE event='lot_failed' AND critical=1")["n"] >= 1


def test_books_bigger_than_account_blocks(clean, clock):
    s = S.get("qld_regime")
    a = brokers.get("paper")._acct()
    a["cash"] = 5000                                                       # money left the account outside the bot
    db.set_state("paper_account", a)
    pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    assert ledger.get("paper", s.id)["cash"] == pytest.approx(10000)      # nothing bought
    assert "books show" in (db.get_state("guard_block:paper") or {}).get("why", "")


def test_fees_come_out_of_the_strategy(clean, clock):
    db.set_settings({"paper_fee_pct": "0.1"})
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, dict(s.evaluate(NOW), target=s.target_for("2x")), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    fees = db.one("SELECT SUM(fee) f FROM orders WHERE plan_id=?", (pid,))["f"]
    assert fees > 0
    acct = brokers.get("paper").account()
    # the account's cash and the books agree: what is outside the bot did not shrink by the fees
    assert acct["cash"] - ledger.bot_cash("paper") == pytest.approx(100000 - 70000, abs=0.05)


def test_cannot_allocate_below_floor(clean):
    acct = brokers.get("paper").account()
    db.set_settings({"protect_floor_paper": "25000"})                      # free cash is 30,000
    with pytest.raises(ValueError):
        moneyops.to_bot("paper", 6000)
    moneyops.to_bot("paper", 5000)
