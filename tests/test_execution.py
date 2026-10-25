"""Split plans: lots, rounds, start time, sells before buys, buy sizing, retries, and the paper books."""
from datetime import datetime, timedelta, timezone

import pytest

from app import brokers, db, execution as X, ledger, markethours as mh, marketdata as md
from app import strategies as S
from conftest import NOW


def run_until_done(clock, pid, minutes=240):
    for _ in range(minutes):
        clock.advance(minutes=1)
        X.process(clock.dt)
        if db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] != "active":
            return db.one("SELECT * FROM plans WHERE id=?", (pid,))
    raise AssertionError("plan did not finish")


def test_regime_plan_lots_and_spacing(clean, clock):
    s = S.get("qld_regime")
    ev = s.evaluate(NOW)
    pid = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    assert pid
    orders = db.rows("SELECT * FROM orders WHERE plan_id=? ORDER BY scheduled_at, step", (pid,))
    plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    assert plan["lots"] == 10 and plan["interval_min"] == 5          # regime defaults: 10 lots × 5 min, from the open
    times = sorted({o["scheduled_at"] for o in orders})
    assert times[0] == int(NOW.timestamp())                          # market is open: start now
    assert all(b - a == 300 for a, b in zip(times, times[1:]))
    assert all(o["side"] == "BUY" and o["step"] % 2 == 1 for o in orders)   # nothing held: buys only


def test_plan_fills_and_books_match_the_account(clean, clock):
    s = S.get("qld_regime")
    ev = s.evaluate(NOW)
    pid = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    plan = run_until_done(clock, pid)
    assert plan["status"] == "done"
    v = ledger.value("paper", s.id)
    assert v["cash"] >= 0
    assert v["value"] == pytest.approx(10000, rel=0.01)
    w, tot = ledger.weights("paper", s.id, md.prices(set(ev["target"])))
    for sym, tw in ev["target"].items():
        assert w.get(sym, 0) == pytest.approx(tw, abs=0.03)
    acct = brokers.get("paper").account()
    held = {k: p["qty"] for k, p in acct["positions"].items()}
    books = {}
    for L in ledger.all_for("paper").values():
        for k, q in L["holdings"].items():
            books[k] = books.get(k, 0) + q
    assert {k: q for k, q in books.items() if q} == held
    # a second reconcile on the same target makes no new plan
    assert X.reconcile("paper", S.get("qld_regime"), ev, clock.dt, brokers.get("paper"), db.get_settings()) is None


def test_metals_plan_waits_for_22_00_bangkok(clean, clock):
    early = clock.set(datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc))      # 15:00 Bangkok, market closed
    s = S.get("gold_st30")
    pid = X.build_plan("paper", s, {"UGL": 0.99}, "signal", early, brokers.get("paper"))
    plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    start = datetime.fromtimestamp(plan["start_at"], timezone.utc).astimezone(mh.BKK)
    assert (start.hour, start.minute) == (22, 0) and start.date() == early.astimezone(mh.BKK).date()


def test_exit_starts_at_the_open_not_22_00(clean, clock):
    early = clock.set(datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc))
    s = S.get("gold_st30")
    pid = X.build_plan("paper", s, s.cash_target(), "signal", early, brokers.get("paper"))
    start = datetime.fromtimestamp(db.one("SELECT start_at FROM plans WHERE id=?", (pid,))["start_at"], timezone.utc)
    assert start == mh.next_open(early, "CORE")


def test_sells_come_before_buys_in_each_round(clean, clock):
    s = S.get("gold_st30")
    b = brokers.get("paper")
    px = b.quote("SGOV")["price"]
    q = int(9000 // px)
    b.place("SGOV", "BUY", q, None, "CORE", "seed-sgov")
    fill = b.order("seed-sgov")
    ledger.book_fill("paper", s.id, "SGOV", "BUY", fill["filled_qty"], fill["filled_qty"] * fill["avg_price"])
    pid = X.build_plan("paper", s, {"UGL": 0.99}, "signal", NOW, b)
    rows = db.rows("SELECT * FROM orders WHERE plan_id=? ORDER BY step", (pid,))
    lots = db.one("SELECT lots FROM plans WHERE id=?", (pid,))["lots"]
    for k in range(lots):
        steps = {(o["side"], o["step"]) for o in rows if o["lot"] == k + 1}
        assert ("SELL", 2 * k) in steps and ("BUY", 2 * k + 1) in steps
    assert sum(o["plan_qty"] for o in rows if o["side"] == "SELL") == q
    plan = run_until_done(clock, pid)
    assert plan["status"] == "done"
    L = ledger.get("paper", s.id)
    assert "SGOV" not in L["holdings"] or L["holdings"]["SGOV"] == 0
    assert L["holdings"]["UGL"] > 0 and L["cash"] >= 0


def test_small_plans_use_fewer_lots(clean, clock):
    s = S.get("gold_st30")
    db.run("UPDATE ledger SET cash=900, cap_in=900 WHERE mode='paper' AND strategy=?", (s.id,))
    pid = X.build_plan("paper", s, {"UGL": 0.99}, "signal", NOW, brokers.get("paper"))
    assert db.one("SELECT lots FROM plans WHERE id=?", (pid,))["lots"] == 4      # $891 / $200 smallest lot


def test_pause_all_stops_sending(clean, clock):
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    db.set_settings({"trading_paused": "1"})
    for _ in range(30):
        clock.advance(minutes=1)
        X.process(clock.dt)
    assert db.one("SELECT COUNT(*) n FROM orders WHERE plan_id=? AND status<>'scheduled'", (pid,))["n"] == 0


class NeverFills(brokers.PaperBroker):
    """Accepts orders, never fills them."""

    def place(self, symbol, side, qty, limit, session, cid):
        a = self._acct()
        a["orders"][cid] = {"cid": cid, "symbol": symbol, "side": side, "qty": float(qty), "limit": limit, "status": "SUBMITTED",
                            "filled_qty": 0.0, "avg_price": None, "t": 0}
        self._save(a)
        return {"order_id": cid}

    def order(self, cid):
        o = self._acct()["orders"][cid]
        return {"status": o["status"], "filled_qty": 0.0, "avg_price": None}


def test_unfilled_lot_is_cancelled_retried_then_failed(clean, clock):
    from app import notify
    s = S.get("qld_regime")
    S.update(s.id, exec={"lots": 1, "interval_min": 5})
    nb = NeverFills()
    brokers.set_override("paper", nb)
    s = S.get("qld_regime")
    pid = X.build_plan("paper", s, s.target_for("2x"), "signal", NOW, nb)
    for _ in range(90):
        clock.advance(minutes=1)
        X.process(clock.dt)
    orders = db.rows("SELECT * FROM orders WHERE plan_id=? ORDER BY id", (pid,))
    assert [o["retry"] for o in orders] == [0, 1, 2, 3]                # first try + 3 retries
    assert all(o["status"] == "cancelled" for o in orders)
    assert db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] == "done"
    failed = db.rows("SELECT * FROM line_queue WHERE event='lot_failed'")
    assert failed and failed[0]["critical"] == 1
    assert ledger.get("paper", s.id)["cash"] == pytest.approx(10000)   # nothing booked


def test_target_change_replaces_the_plan(clean, clock):
    s = S.get("qld_regime")
    db.set_settings({"trading_paused": "1"})
    ev = dict(s.evaluate(NOW), target=s.target_for("2x"))
    p1 = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    ev2 = dict(ev, target=s.target_for("off"))
    p2 = X.reconcile("paper", s, ev2, NOW, brokers.get("paper"), db.get_settings())
    assert p2 and p2 != p1
    assert db.one("SELECT status FROM plans WHERE id=?", (p1,))["status"] == "cancelled"


def test_stop_and_sell(clean, clock):
    s = S.get("qld_regime")
    ev = s.evaluate(NOW)
    pid = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    S.update(s.id, control="stopping")
    s = S.get("qld_regime")
    pid2 = X.reconcile("paper", s, ev, clock.dt, brokers.get("paper"), db.get_settings())
    assert db.one("SELECT reason FROM plans WHERE id=?", (pid2,))["reason"] == "stop"
    run_until_done(clock, pid2)
    assert S.row(s.id)["control"] == "stopped"
    L = ledger.get("paper", s.id)
    assert not any(q for q in L["holdings"].values())


def test_one_replacement_per_lot(clean, clock):
    """An old order read as expired after its session must not add a second copy of a lot that was already retried."""
    s = S.get("gold_st30")
    pid = X.build_plan("paper", s, {"UGL": 0.99}, "signal", NOW, brokers.get("paper"))
    o = db.one("SELECT * FROM orders WHERE plan_id=? ORDER BY step, id LIMIT 1", (pid,))
    db.run("UPDATE orders SET status='cancelled', qty=10 WHERE id=?", (o["id"],))
    o = db.one("SELECT * FROM orders WHERE id=?", (o["id"],))
    X._retry(o, 10, NOW, "test", 3)
    X._retry(o, 10, NOW, "test again", 3)                                # same order twice: still one replacement
    reps = db.rows("SELECT * FROM orders WHERE plan_id=? AND step=? AND retry=1", (pid, o["step"]))
    assert len(reps) == 1
    # the replacement is cancelled and retried: the first order read late again adds nothing
    db.run("UPDATE orders SET status='cancelled' WHERE id=?", (reps[0]["id"],))
    X._retry(db.one("SELECT * FROM orders WHERE id=?", (reps[0]["id"],)), 10, NOW, "r1", 3)
    X._retry(o, 10, NOW, "late read of r0", 3)
    assert [r["retry"] for r in db.rows("SELECT retry FROM orders WHERE plan_id=? AND step=? AND status='scheduled'", (pid, o["step"]))] == [2]


def test_duplicate_waiting_orders_are_removed(clean, clock):
    s = S.get("gold_st30")
    pid = X.build_plan("paper", s, {"UGL": 0.99}, "signal", NOW, brokers.get("paper"))
    o = db.one("SELECT * FROM orders WHERE plan_id=? ORDER BY step, id LIMIT 1", (pid,))
    with db.tx() as c:                                                  # what bot 1.0's repair left behind
        for r in (1, 2, 3):
            X._insert_order(c, pid, "paper", s.id, o["step"], o["lot"], o["lots"], o["symbol"], o["side"], NOW, o["session"],
                            plan_qty=5, retry=r, qty=5)
    assert X.dedupe_retries() == 3
    left = db.rows("SELECT retry FROM orders WHERE plan_id=? AND step=? AND status='scheduled'", (pid, o["step"]))
    assert [r["retry"] for r in left] == [3]
    assert X.dedupe_retries() == 0
