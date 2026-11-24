"""24 Nov 2026 (Live): Webull answered 429 "too many requests" to order-status checks at the open; the bot skipped those
orders and saw fills 7-13 minutes late. Order checks are now paced, oldest-checked first, with one open-orders call,
a short cooldown on 429, an alert when an order goes unanswered, a separate fast order loop and price room for sells."""
import logging
import time
from datetime import timedelta

import pytest

from app import brokers, db, engine, execution as X, markethours as mh, marketdata as md
from app import strategies as S
from conftest import NOW
from test_execution import NeverFills
from test_api import client  # noqa: F401


class Busy(NeverFills):
    """Every other status call: 'too many requests'; otherwise the order is filled at its limit."""

    def __init__(self):
        super().__init__()
        self.calls = 0
        self.asked = []

    def order(self, cid):
        self.calls += 1
        if self.calls % 2 == 1:
            raise brokers.RateLimited("Webull order status failed: HTTP Status: 429, Code: TOO_MANY_REQUESTS")
        self.asked.append(cid)
        o = self._acct()["orders"][cid]
        return {"status": "FILLED", "filled_qty": o["qty"], "avg_price": o["limit"]}


def _working(broker, n=3, age_s=20):
    """n submitted SELL orders of one active plan, known to the fake broker."""
    s = S.get("qld_regime")
    pid = db.run("INSERT INTO plans(mode,strategy,reason,status,created_at,interval_min,lots) VALUES('paper',?,'signal','active',?,1,?)",
                 (s.id, int(NOW.timestamp()), n)).lastrowid
    ids = []
    for k in range(n):
        cid = f"t{pid}x{k}"
        broker.place("QLD", "BUY", 1, 70.0, "CORE", cid)
        ids.append(db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,limit_price,scheduled_at,"
                          "submitted_at,status,client_order_id,updated_at,retry) VALUES(?,'paper',?,?,?,?,'QLD','BUY',1,1,70,?,?,"
                          "'submitted',?,?,0)", (pid, s.id, 2 * k + 1, k + 1, n, int(NOW.timestamp()), int(NOW.timestamp()) - age_s,
                                                cid, int(NOW.timestamp()))).lastrowid)
    return pid, ids


def test_too_many_requests_never_starves_an_order(clean, monkeypatch):
    monkeypatch.setattr(X, "COOLDOWN_S", 0)
    b = Busy()
    pid, ids = _working(b, 3)
    for _ in range(4):
        X.poll("paper", NOW, b)
    st = [db.one("SELECT status FROM orders WHERE id=?", (i,))["status"] for i in ids]
    assert st == ["filled", "filled", "filled"]          # 3 fills in 4 passes although every other call was refused
    assert len(set(b.asked)) == 3


def test_cooldown_after_429(clean, monkeypatch):
    monkeypatch.setattr(X, "COOLDOWN_S", 30)
    b = Busy()
    _working(b, 2)
    X.poll("paper", NOW, b)
    assert b.calls == 1                                   # refused: stop asking at once
    X.poll("paper", NOW, b)
    assert b.calls == 1                                   # still cooling down
    assert X.poll("paper", NOW, b, only_id=999999) is None


class OpenList(NeverFills):
    def __init__(self, open_cids):
        super().__init__()
        self.open_cids, self.asked = set(open_cids), []

    def open_ids(self):
        return set(self.open_cids)

    def order(self, cid):
        self.asked.append(cid)
        return super().order(cid)


def test_open_orders_list_saves_calls(clean):
    b = OpenList([])
    pid, ids = _working(b, 2, age_s=20)
    a, c = (db.one("SELECT client_order_id c FROM orders WHERE id=?", (i,))["c"] for i in ids)
    b.open_cids = {a}
    X.poll("paper", NOW, b)
    assert b.asked == [c]                                 # the open one is not asked about while it is young
    db.run("UPDATE orders SET submitted_at=? WHERE id=?", (int(NOW.timestamp()) - 200, ids[0]))
    b.asked.clear()
    X.poll("paper", NOW, b)
    assert a in b.asked                                   # due for re-pricing: read and cancelled as before


def test_unanswered_order_alert_once(clean):
    b = NeverFills()
    pid, ids = _working(b, 1, age_s=200)
    X._unseen_alerts("paper", NOW)
    X._unseen_alerts("paper", NOW)
    ev = db.rows("SELECT * FROM events WHERE title LIKE 'Order status not read%'")
    q = db.rows("SELECT * FROM line_queue WHERE event='lot_failed' AND text LIKE '%No answer from Webull%'")
    assert len(ev) == 1 and len(q) == 1


def test_parse_open_ids():
    js = {"data": [{"client_order_id": "a", "orders": [{"client_order_id": "b"}]}]}
    assert brokers.parse_open_ids(js) == {"a", "b"}
    assert brokers.parse_open_ids({"data": []}) == set()
    assert brokers.parse_open_ids({"msg": "odd"}) is None


def test_sell_price_room(clean):
    assert X.exec_cfg(S.get("qld_regime"))["sell_offset"] == pytest.approx(0.005)
    db.set_settings({"exec_sell_offset_pct": "1"})
    assert X.exec_cfg(S.get("qld_regime"))["sell_offset"] == pytest.approx(0.01)
    q = {"price": 100.0, "bid": 100.0, "ask": 100.1, "time": 0}
    o = {"plan_id": 1, "lot": 1, "symbol": "QLD", "retry": 0, "session": "CORE"}
    assert X.lot_limit(o, q, "SELL", 0.005, NOW) == 99.5


def test_sell_offset_setting_api(client):
    from test_api import sign_in
    sign_in(client)
    assert client.get("/api/settings/execution").json()["defaults"]["exec_sell_offset_pct"] == "0.5"
    assert client.post("/api/settings/execution", json={"defaults": {"exec_sell_offset_pct": "5"}}).status_code == 400
    assert client.post("/api/settings/execution", json={"defaults": {"exec_sell_offset_pct": "0.8"}}).status_code == 200


def test_no_market_data_goes_straight_to_yahoo(clean, monkeypatch):
    b = brokers.WebullBroker(env="test")
    db.set_state("quote_nosub:test", int(time.time()))
    monkeypatch.setattr(b, "_clients", lambda: (_ for _ in ()).throw(AssertionError("Webull was asked")))
    monkeypatch.setattr(md, "live_quote", lambda sym: {"price": 1.0, "source": "yahoo"})
    assert b.quote("QLD")["source"] == "yahoo"


def test_account_cache_and_invalidate(clean, monkeypatch):
    monkeypatch.setattr(brokers, "ACCOUNT_CACHE_S", 15)
    b = brokers.WebullBroker(env="test")
    n = {"k": 0}

    def raw():
        n["k"] += 1
        return "A1", {"total_cash_balance": "100", "account_currency_assets": []}, []
    monkeypatch.setattr(b, "raw_account", raw)
    monkeypatch.setattr(b, "_touch", lambda: None)
    b.account(); b.account()
    assert n["k"] == 1
    b.invalidate_account(); b.account()
    assert n["k"] == 2


def test_pacing(monkeypatch):
    monkeypatch.setattr(brokers, "ORDER_GAP_S", 0.2)
    b = brokers.WebullBroker(env="test")
    t = time.time()
    b._pace(); b._pace()
    assert time.time() - t >= 0.18


def test_orders_busy(clean):
    assert not X.orders_busy(NOW)
    b = NeverFills()
    _working(b, 1)
    assert X.orders_busy(NOW)


def test_no_routine_price_refresh_at_the_open(monkeypatch):
    monkeypatch.setattr(md, "source", lambda: "yahoo")
    d = NOW.astimezone(mh.NY).date()
    while not mh.session_bounds(d):
        d += timedelta(days=1)
    op = mh.session_bounds(d)[0]
    old = (op - timedelta(minutes=45)).timestamp()
    assert engine._daily_due("QLD", op + timedelta(minutes=5), old) is False
    assert engine._daily_due("QLD", op + timedelta(minutes=30), old) is True


def test_stopped_strategies_checked_every_10_minutes(clean, clock):
    engine.evaluate_all(clock.dt)
    S.update("qld_regime", control="stopped")
    db.run("UPDATE strategy_state SET computed_at=? WHERE strategy='qld_regime'", (int(time.time()),))
    assert "qld_regime" not in engine.evaluate_all(clock.dt)
    db.run("UPDATE strategy_state SET computed_at=? WHERE strategy='qld_regime'", (int(time.time()) - 700,))
    assert "qld_regime" in engine.evaluate_all(clock.dt)


def test_sdk_request_dumps_stay_out_of_the_server_log(tmp_path):
    """Even after the SDK's set_file_logger (which sets 'webull.core' to INFO), its messages do not reach the root
    logger (journalctl)."""
    import io
    from webull.core.client import ApiClient
    root_buf = io.StringIO()
    h = logging.StreamHandler(root_buf)
    logging.getLogger().addHandler(h)
    try:
        api = ApiClient("k", "s", "th")
        api.set_file_logger(path=str(tmp_path / "sdk.log"), log_level=logging.INFO)
        brokers.quiet_sdk_log()
        logging.getLogger("webull.core.client").error("x-access-token: SECRET")
    finally:
        logging.getLogger().removeHandler(h)
    assert "SECRET" not in root_buf.getvalue()
    assert "SECRET" in (tmp_path / "sdk.log").read_text()


class LikeWebullTonight(brokers.PaperBroker):
    """24 Nov 2026 at the open: fills at once when the limit crosses, the price falls 4% in 6 minutes, and for the first
    3 minutes every other status call is answered 'too many requests'."""

    def __init__(self, t0):
        self.t0 = t0
        self.calls = 0
        super().__init__(quote_fn=self.px)

    def px(self, sym):
        t = time.time() - self.t0
        p = 70.0 * (1 - 0.04 * min(max(t, 0), 360) / 360)
        return {"price": p, "bid": p, "ask": p + 0.01, "time": int(time.time()), "source": "test"}

    def order(self, cid):
        self.calls += 1
        if time.time() - self.t0 < 180 and self.calls % 2:
            raise brokers.RateLimited("Webull order status failed: HTTP Status: 429, Code: TOO_MANY_REQUESTS")
        return super().order(cid)

    def open_ids(self):
        return {c for c, o in self._acct()["orders"].items() if o["status"] == "SUBMITTED"}


def test_rehearsal_of_tonights_open(clean, clock, monkeypatch):
    """Sell 5 lots x 1 minute while Webull refuses half the status checks: every fill is booked within seconds and the
    plan ends within the planned 5 minutes (tonight: fills seen 7-13 minutes late, plans took 12-28 minutes)."""
    from test_execution import run_until_done
    monkeypatch.setattr(X, "COOLDOWN_S", 3)
    s = S.get("qld_regime")
    S.update(s.id, exec={"lots": 5, "interval_min": 1})
    s = S.get("qld_regime")
    pid = X.build_plan("paper", s, s.target_for("2x"), "signal", clock.dt, brokers.get("paper"))
    run_until_done(clock, pid)                               # hold QLD first (plain paper broker)
    held = brokers.get("paper").account()["positions"]["QLD"]["qty"]
    assert held > 0
    fake = LikeWebullTonight(time.time())
    brokers.set_override("paper", fake)
    try:
        pid = X.build_plan("paper", s, {}, "signal", clock.dt, fake)      # exit: sell everything
        start = time.time()
        for _ in range(12 * 12):                              # the 5-second order loop, 12 minutes
            clock.advance(seconds=5)
            if X.orders_busy(clock.dt):
                X.process(clock.dt)
            if db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] != "active":
                break
        plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
        assert plan["status"] == "done"
        assert time.time() - start <= 6 * 60                # 5 lots, 1 minute apart, finished on time
        orders = db.rows("SELECT * FROM orders WHERE plan_id=? AND applied_qty>0", (pid,))
        acct = fake._acct()["orders"]
        lag = [o["updated_at"] - acct[o["client_order_id"]]["filled_at"] for o in orders]
        assert max(lag) <= 15                               # each fill booked within 15 seconds of Webull's fill
        assert sum(o["applied_qty"] for o in orders) == pytest.approx(held)
        assert fake.calls > 0
    finally:
        brokers.set_override("paper", None)
