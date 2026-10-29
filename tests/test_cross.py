"""Opposite orders of two strategies on the same day are settled inside the bot: one price, no fee, only the rest goes
to Webull, and the strategies' books still add up to the account."""
import pytest

from app import brokers, db, execution as X, ledger
from app import strategies as S
from conftest import NOW

SELLER, BUYER = "semis_regime", "usd_ibs"


def run_all(clock, pids, minutes=240):
    for _ in range(minutes):
        clock.advance(minutes=1)
        X.process(clock.dt)
        if all(db.one("SELECT status FROM plans WHERE id=?", (p,))["status"] != "active" for p in pids):
            return
    raise AssertionError("plans did not finish")


def books_total(mode="paper"):
    out = {}
    for L in ledger.all_for(mode).values():
        for k, q in L["holdings"].items():
            out[k] = round(out.get(k, 0) + q, 6)
    return {k: q for k, q in out.items() if q > 1e-6}


def account_total(mode="paper"):
    return {k: round(p["qty"], 6) for k, p in brokers.get(mode).account()["positions"].items() if p["qty"] > 1e-6}


def paper_orders(symbol, side):
    a = brokers.get("paper")._acct()
    return [o for o in a["orders"].values() if o["symbol"] == symbol and o["side"] == side]


def seller_holds_usd(clock):
    pid = X.build_plan("paper", S.get(SELLER), {"USD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    run_all(clock, [pid])
    return ledger.get("paper", SELLER)["holdings"]["USD"]


def test_opposite_orders_are_settled_inside_the_bot(clean, clock):
    held = seller_holds_usd(clock)
    sells_before, buys_before = len(paper_orders("USD", "SELL")), len(paper_orders("USD", "BUY"))
    cash_before = brokers.get("paper").account()["cash"]
    sp = X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))   # sells USD
    bp = X.build_plan("paper", S.get(BUYER), {"USD": 0.5}, "signal", clock.dt, brokers.get("paper"))     # buys USD
    run_all(clock, [sp, bp])

    inside = db.rows("SELECT * FROM orders WHERE cross_with IS NOT NULL ORDER BY side")
    assert [o["side"] for o in inside] == ["BUY", "SELL"]
    b, s = inside
    assert b["strategy"] == BUYER and b["cross_with"] == SELLER and s["strategy"] == SELLER and s["cross_with"] == BUYER
    assert b["filled_qty"] == s["filled_qty"] > 0 and b["avg_price"] == s["avg_price"]
    assert b["fee"] == 0 and s["fee"] == 0 and b["broker_order_id"] == "internal" and b["submitted_at"] is None
    moved = s["filled_qty"]
    # Webull (paper) only saw the rest: the buyer needed fewer than the seller had, so it bought no USD at the broker
    assert len(paper_orders("USD", "BUY")) == buys_before
    sold_at_broker = sum(o["filled_qty"] for o in paper_orders("USD", "SELL")[sells_before:])
    assert sold_at_broker == pytest.approx(held - moved, abs=1e-6)
    # books: the seller holds no USD, the buyer holds what moved, and everything still adds up to the account
    assert ledger.get("paper", SELLER)["holdings"].get("USD", 0) == pytest.approx(0, abs=1e-6)
    assert ledger.get("paper", BUYER)["holdings"]["USD"] == pytest.approx(moved)
    assert books_total() == account_total()
    # cash: the bot's books still match the account (the move itself changed nothing at the broker)
    acct = brokers.get("paper").account()
    assert ledger.bot_cash("paper") <= acct["cash"] + 1.0
    assert acct["cash"] != cash_before            # the USD sold at the broker and the GLD bought did change it
    ev = db.rows("SELECT * FROM events WHERE title LIKE 'Settled inside the bot%'")
    assert len(ev) == 2


def test_plan_totals_and_waiting_sells_are_reduced(clean, clock):
    held = seller_holds_usd(clock)
    sp = X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    planned = db.one("SELECT SUM(plan_qty) q FROM orders WHERE plan_id=? AND side='SELL' AND retry=0", (sp,))["q"]
    bp = X.build_plan("paper", S.get(BUYER), {"USD": 0.3}, "signal", clock.dt, brokers.get("paper"))
    X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings())
    moved = db.one("SELECT filled_qty q FROM orders WHERE plan_id=? AND cross_with IS NOT NULL", (sp,))["q"]
    assert 0 < moved < held
    left = db.rows("SELECT * FROM orders WHERE plan_id=? AND side='SELL' AND status='scheduled'", (sp,))
    assert sum(o["plan_qty"] for o in left) == pytest.approx(held - moved, abs=1e-6)
    # the plan still adds up to what it set out to sell (crossed + still to send)
    assert db.one("SELECT SUM(plan_qty) q FROM orders WHERE plan_id=? AND side='SELL' AND retry=0", (sp,))["q"] == pytest.approx(planned)
    # the buyer got all it wanted, so its waiting USD buys are closed
    assert not db.rows("SELECT * FROM orders WHERE plan_id=? AND side='BUY' AND status='scheduled'", (bp,))
    # a second pass finds nothing more to settle
    assert X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings()) == []
    run_all(clock, [sp, bp])
    assert books_total() == account_total()


def test_setting_off_sends_both_to_webull(clean, clock):
    seller_holds_usd(clock)
    db.set_settings({"exec_cross": "0"})
    buys_before = len(paper_orders("USD", "BUY"))
    sp = X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    bp = X.build_plan("paper", S.get(BUYER), {"USD": 0.5}, "signal", clock.dt, brokers.get("paper"))
    run_all(clock, [sp, bp])
    assert not db.rows("SELECT * FROM orders WHERE cross_with IS NOT NULL")
    assert len(paper_orders("USD", "BUY")) > buys_before
    assert books_total() == account_total()


def test_nothing_is_settled_before_either_side_is_due(clean, clock):
    seller_holds_usd(clock)
    later = clock.dt.replace(hour=19)                                  # 15:00 New York: later the same session
    for sid, tgt in ((SELLER, {"GLD": 0.99}), (BUYER, {"USD": 0.5})):
        pid = X.build_plan("paper", S.get(sid), tgt, "signal", clock.dt, brokers.get("paper"))
        db.run("UPDATE orders SET scheduled_at=scheduled_at+? WHERE plan_id=?", (int(later.timestamp() - clock.dt.timestamp()), pid))
    assert X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings()) == []
    assert len(X.cross("paper", later, brokers.get("paper"), db.get_settings())) == 1


def test_not_while_the_market_is_closed_or_paused(clean, clock):
    seller_holds_usd(clock)
    X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    X.build_plan("paper", S.get(BUYER), {"USD": 0.5}, "signal", clock.dt, brokers.get("paper"))
    db.set_settings({"trading_paused": "1"})
    assert X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings()) == []
    db.set_settings({"trading_paused": "0"})
    night = clock.dt.replace(hour=23)                                   # 19:00 New York: closed
    assert X.cross("paper", night, brokers.get("paper"), db.get_settings()) == []
    assert len(X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings())) == 1


def test_fills_and_plans_views_show_it(clean, clock):
    seller_holds_usd(clock)
    sp = X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    X.build_plan("paper", S.get(BUYER), {"USD": 0.5}, "signal", clock.dt, brokers.get("paper"))
    X.cross("paper", clock.dt, brokers.get("paper"), db.get_settings())
    rows = X.fills_view("paper")["rows"]
    inside = [r for r in rows if r.get("cross_with")]
    assert {r["strategy"] for r in inside} == {SELLER, BUYER}
    assert all(r["cross_name"] for r in inside)
    p = [p for p in X.plans_view("paper") if p["id"] == sp][0]
    assert any(o.get("cross_name") == S.get(BUYER).name for o in p["orders"])


def test_next_open_preview_shows_the_inside_part(clean, clock):
    from app import preview
    seller_holds_usd(clock)
    X.build_plan("paper", S.get(SELLER), {"GLD": 0.99}, "signal", clock.dt, brokers.get("paper"))
    X.build_plan("paper", S.get(BUYER), {"USD": 0.5}, "signal", clock.dt, brokers.get("paper"))
    d = preview.next_orders("paper")
    assert d["inside"]["USD"] == pytest.approx(5000, rel=0.1)
    db.set_settings({"exec_cross": "0"})
    assert preview.next_orders("paper")["inside"] == {}
