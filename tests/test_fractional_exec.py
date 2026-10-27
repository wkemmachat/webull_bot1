"""Fractional shares in plans: whole shares per lot, the leftover fraction on the last lot, full exits sell fractions,
and a refused fractional order falls back to whole shares for that ETF (LINE told once)."""
import pytest

from app import brokers, db, execution as X, ledger, moneyops, preview
from app import strategies as S
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)
from test_execution import run_until_done


def frac(mode, on):
    db.set_settings({f"exec_fractional_{mode}": "1" if on else "0"})


def test_setting_defaults_follow_the_golive_test(clean):
    assert X.fractional_setting("live") == {"on": False, "source": "test"}
    assert X.fractional_setting("paper") == {"on": False, "source": "live"}
    db.set_state("fractional:live", {"LIMIT": {"ok": True, "symbol": "QLD", "at": 1}})
    assert X.fractional_on("live") and X.fractional_on("paper")            # paper follows Live
    assert not X.fractional_on("test")                                     # each account has its own test
    frac("paper", False)
    assert not X.fractional_on("paper") and X.fractional_setting("paper")["source"] == "set"
    db.set_settings({"exec_fractional_paper": ""})
    assert X.fractional_on("paper")


def test_split_puts_the_fraction_on_the_last_lot():
    assert X._split(7, 3) == [3, 2, 2]
    assert X._split(7.375, 3) == [3, 2, 2.375]
    assert X._split(0.4, 2) == [0, 0.4]
    assert X._down(2.9999999999, 4) == 3 and X._down(1.23456, 4) == 1.2345 and X._down(1.9, 0) == 1


def test_fractional_plan_spends_the_leftover(clean, clock):
    frac("paper", True)
    s = S.get("qld_regime")
    ev = s.evaluate(NOW)
    pid = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    assert run_until_done(clock, pid)["status"] == "done"
    L = ledger.get("paper", s.id)
    assert any(X.is_fraction(q) for q in L["holdings"].values())
    assert L["cash"] >= 0
    held = {k: p["qty"] for k, p in brokers.get("paper").account()["positions"].items()}
    for k, q in L["holdings"].items():
        assert held[k] == pytest.approx(q)
    lots = db.rows("SELECT * FROM orders WHERE plan_id=? AND side='BUY' AND status='filled' ORDER BY lot", (pid,))
    assert all(not X.is_fraction(o["qty"]) for o in lots[:-1])            # whole shares until the last lot of a symbol


def test_full_exit_sells_fractions_and_withdraw_everything(clean, clock):
    frac("paper", True)
    s = S.get("gold_st30")
    b = brokers.get("paper")
    b.place("UGL", "BUY", 3.375, None, "CORE", "seed-ugl")
    f = b.order("seed-ugl")
    ledger.book_fill("paper", s.id, "UGL", "BUY", f["filled_qty"], f["filled_qty"] * f["avg_price"])
    pid = X.build_plan("paper", s, s.cash_target(), "signal", NOW, b, buys=False)
    sells = db.rows("SELECT plan_qty FROM orders WHERE plan_id=? AND side='SELL'", (pid,))
    assert sum(r["plan_qty"] for r in sells) == pytest.approx(3.375)
    run_until_done(clock, pid)
    assert ledger.get("paper", s.id)["holdings"].get("UGL", 0) == pytest.approx(0, abs=1e-9)


def test_whole_shares_when_off(clean, clock):
    frac("paper", False)
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    assert not any(X.is_fraction(q) for q in ledger.get("paper", s.id)["holdings"].values())


def test_small_buy_below_one_share(clean, clock):
    frac("paper", True)
    b = brokers.get("paper")
    px = b.quote("UGL")["price"]
    assert X._too_small("BUY", 4.0 / px, px) and not X._too_small("BUY", 6.0 / px, px)
    assert not X._too_small("SELL", 0.01, px)                             # a leftover fraction can always be sold


def test_refused_fraction_falls_back_to_whole_shares(clean, clock):
    class Refuse(brokers.PaperBroker):
        def place(self, symbol, side, qty, limit, session, cid):
            if X.is_fraction(qty):
                raise brokers.BrokerRejected("fractional orders are not supported for this symbol", code="OPENAPI_FRAC",
                                             permanent=True)
            return super().place(symbol, side, qty, limit, session, cid)
    brokers.set_override("paper", Refuse())
    frac("paper", True)
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    plan = run_until_done(clock, pid)
    assert plan["status"] == "done"                                       # not cancelled, the ETF is not blocked
    refused = X.fraction_refused("paper")
    assert refused and all(k not in X.blocked_symbols("paper") for k in refused)
    assert not any(X.is_fraction(q) for q in ledger.get("paper", s.id)["holdings"].values())
    n = db.one("SELECT COUNT(*) n FROM line_queue WHERE text LIKE '%refused a fractional order%'")["n"]
    assert n == len(refused)                                              # LINE once per ETF
    sym = next(iter(refused))
    assert not X.fractional_on("paper", sym) and X.fractional_on("paper")
    X.reset_fraction_refusals("paper")
    assert X.fractional_on("paper", sym)


def test_preview_estimate_shows_fractions(clean, clock):
    frac("paper", True)
    s = S.get("qld_regime")
    X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    rows = preview.next_orders("paper")["rows"]
    buys = [i for r in rows for i in r["items"] if i["side"] == "BUY" and i["qty"]]
    assert buys and any(X.is_fraction(i["qty"]) for i in buys)


def test_settings_api(client):
    sign_in(client)
    r = client.post("/api/settings/execution", json={"defaults": {"exec_fractional_live": "1"}, "reset_fractions": ["live"]})
    assert r.status_code == 200 and db.get_setting("exec_fractional_live") == "1"
    v = client.get("/api/settings/execution").json()["fractional"]
    assert v["live"]["on"] and v["live"]["source"] == "set" and v["paper"]["on"]
    assert client.post("/api/settings/execution", json={"defaults": {"exec_fractional_live": "x"}}).status_code == 400
