"""Money → Everything: the dialog's value is priced a moment earlier; the server takes all of it at today's prices."""
import pytest

from app import brokers, db, execution as X, ledger, moneyops
from app import strategies as S
from conftest import NOW
from test_execution import run_until_done


def _invest(clock, sid="qld_regime", frac=True):
    db.set_settings({"exec_fractional_paper": "1" if frac else "0"})
    s = S.get(sid)
    run_until_done(clock, X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings()))
    return s


def test_stale_amount_without_everything_explains(clean, clock):
    s = _invest(clock)
    v = ledger.value("paper", s.id)["value"]
    with pytest.raises(ValueError, match="Everything"):
        moneyops.move("paper", s.id, "semis_regime", round(v * 1.001 + 0.05, 2))


@pytest.mark.parametrize("frac", [True, False])
def test_move_everything_sells_all_and_moves_the_proceeds(clean, clock, frac):
    s = _invest(clock, frac=frac)
    v = ledger.value("paper", s.id)["value"]
    before = ledger.value("paper", "semis_regime")["net_in"]
    r = moneyops.move("paper", s.id, "semis_regime", round(v * 1.001 + 0.05, 2), everything=True)   # a slightly stale value
    assert r["status"] == "pending"
    plan = run_until_done(clock, r["plan_id"])
    assert plan["status"] == "done"
    L = ledger.get("paper", s.id)
    assert not L["holdings"] and L["cash"] == pytest.approx(0, abs=0.01)
    got = ledger.value("paper", "semis_regime")["net_in"] - before
    assert got == pytest.approx(v, rel=0.01)


def test_withdraw_everything_from_cash_only(clean):
    v = ledger.value("paper", "silver_dc")["value"]
    r = moneyops.withdraw("paper", "silver_dc", v + 3, everything=True)
    assert r["status"] == "done" and r["amount"] == pytest.approx(v)
    assert ledger.get("paper", "silver_dc")["cash"] == pytest.approx(0, abs=0.01)
