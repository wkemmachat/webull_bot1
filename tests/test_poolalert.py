"""Pool alerts and the LINE monthly budget (28 Nov 2026)."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app import db, dip, notify, pool, poolalert

MODE = "paper"


def _on(members):
    pool.set_members(MODE, members)
    pool.set_settings(MODE, on_=True, slot=15.0, cap=25.0, minp=2.0)


@pytest.fixture
def line(clean):
    sent = []
    notify.set_transport(lambda to, text: (sent.append((to, text)), (True, None))[1])
    db.set_settings({"line_token": "tok", "line_recipients": [{"id": "Uabc", "name": "me", "enabled": True, "scope": "all"}],
                     "line_quiet": "0", "line_digest_times": ["08:00", "21:00"], "line_budget": "300"})
    db.run("DELETE FROM line_queue")
    for k in ("line_count", "line_quota", "line_digest_done"):
        db.set_state(k, {})
    yield sent
    notify.set_transport(None)


def at(d, h, m=0, month=11):
    return datetime(2026, month, d, h, m, tzinfo=notify.TZ)


# ---------------------------------------------------------------- the budget
def test_budget_counts_each_push_per_recipient(line):
    db.set_settings({"line_recipients": [{"id": "Uabc", "enabled": True, "scope": "all"}, {"id": "Udef", "enabled": True, "scope": "all"}]})
    notify.send("signal", "Gold BUY")
    notify.dispatch(at(10, 12))
    assert len(line) == 2
    b = notify.budget(at(10, 12))
    assert b["used"] == 2 and b["today"] == 2 and b["per_alert"] == 2 and b["cap"] == 300 and b["reserve"] == 30


def test_on_pace_sends_at_once(line):
    b = notify.budget(at(10, 12))
    assert b["state"] == "ok" and b["allow_today"] >= 8              # (300 − 30) / 21 days left ≈ 12 a day


def test_over_todays_share_routine_alerts_wait_for_the_digest(line):
    db.set_state("line_count", {"month": "2026-11", "n": 120, "days": {"2026-11-10": 12}})
    assert notify.budget(at(10, 12))["state"] == "tight"
    notify.send("signal", "Gold BUY")
    notify.send("lot_failed", "BUY 10 UGL failed")                    # critical: still at once
    notify.dispatch(at(10, 12))
    assert len(line) == 1 and "failed" in line[0][1] and "Gold BUY" not in line[0][1]
    r = db.one("SELECT delivery, status FROM line_queue WHERE text='Gold BUY'")
    assert r["delivery"] == "digest" and r["status"] == "pending"
    notify.dispatch(at(10, 21))                                       # it comes with the evening digest
    assert "Gold BUY" in line[-1][1]


def test_running_low_means_one_digest_a_day(line):
    db.set_state("line_count", {"month": "2026-11", "n": 270, "days": {}})   # 30 left − 30 reserve: nothing free
    assert notify.budget(at(10, 7))["state"] == "stop"
    db.set_state("line_count", {"month": "2026-11", "n": 250, "days": {}})   # 20 free, 21 days of two digests: too few
    assert notify.budget(at(10, 7))["state"] == "low"
    db.set_settings({"line_events": {"signal": "digest"}})
    notify.send("signal", "Silver BUY")
    notify.dispatch(at(10, 21))                                       # not the first digest of the day: waits
    assert not line
    notify.dispatch(at(11, 8))
    assert len(line) == 1 and "Silver BUY" in line[0][1]


def test_stop_keeps_the_reserve_for_critical_alerts(line):
    db.set_state("line_count", {"month": "2026-11", "n": 275, "days": {}})
    notify.send("signal", "Gold BUY")
    notify.send("broker", "Webull token ends")
    notify.dispatch(at(20, 12))
    assert len(line) == 1 and "Webull" in line[0][1]
    assert db.one("SELECT status FROM line_queue WHERE text='Gold BUY'")["status"] == "skipped"


def test_full_sends_nothing_and_a_new_month_starts_again(line):
    db.set_state("line_count", {"month": "2026-11", "n": 300, "days": {}})
    notify.send("lot_failed", "BUY failed")
    notify.dispatch(at(29, 12))
    assert not line and notify.budget(at(29, 12))["state"] == "full"
    assert notify.budget(at(1, 12, month=12))["used"] == 0
    notify.send("lot_failed", "BUY failed again")
    notify.dispatch(at(1, 12, month=12))
    assert len(line) == 1


def test_lines_own_count_and_a_lower_plan_limit_win(line):
    db.set_state("line_quota", {"limit": 200, "used": 150, "at": int(at(10, 9).timestamp())})
    b = notify.budget(at(10, 12))
    assert b["cap"] == 200 and b["used"] == 150


def test_budget_setting(line):
    notify.save_settings({"budget": 500})
    assert notify.budget_cap() == 500 and notify.settings_public()["budget"] == 500
    with pytest.raises(ValueError):
        notify.save_settings({"budget": 5})


# ---------------------------------------------------------------- zones of the pool backtest
def _falls():
    """Ten years of a noisy rising series."""
    idx = pd.bdate_range("2005-01-03", periods=2600)
    r = np.random.default_rng(1).normal(0.0006, 0.012, len(idx))
    return pd.Series(100 * np.cumprod(1 + r), index=idx)


def test_past_only_percentile_and_first_days():
    dd = np.array([0, -1, -2, 0, -3, -1, 0], dtype=float) / 100
    p = pool.past_pct(dd, warm=3)
    assert np.isnan(p[:3]).all() and p[4] == 100.0                    # deeper than every day before it
    assert pool.first_days(np.array([np.nan, 85, 90, 75, 85, 60, 85]), 80) == [1, 6]   # armed again only under the 70th


def test_zones_table_and_now():
    z = pool.zones(_falls())
    assert z["deep"]["80"] < 0 and z["deep"]["90"] < z["deep"]["80"]
    assert z["rows"]["80"]["n"] >= 2 and z["rows"]["any"]["n"] > z["rows"]["80"]["n"] >= z["rows"]["90"]["n"]
    assert z["pct"] is not None and z["day"] == "2014-12-19"


def test_weekly_series_ends_on_the_last_day():
    v = _falls()
    w = pool.weekly(v)
    assert w[0][1] == 100 and w[0][0] == int(v.index[0].timestamp()) and w[-1][0] == int(v.index[-1].timestamp())


# ---------------------------------------------------------------- the alerts
def _bt(pct, depth=-11.4, day="2026-11-25", last=None):
    return {"ready": True, "zone": {"pct": pct, "depth": depth, "day": day, "from": "2005-12-13",
                                    "rows": {"80": {"n": 57, "up": 56, "med": 59.3, "p10": 10.3, "fall": -3.4}},
                                    "last": last or {}}}


def test_zone_alert_once_per_fall_and_rearm(line):
    _on(["qld_split_2c"])
    q = lambda: db.rows("SELECT * FROM line_queue WHERE event='pool_add'")
    poolalert.zone_check(MODE, _bt(60, -3, "2026-11-01"))
    assert not q()
    poolalert.zone_check(MODE, _bt(86, -10.5, "2026-11-02"))
    assert len(q()) == 1 and "56 of 57" in q()[0]["text"] and "Paper" in q()[0]["text"]
    poolalert.zone_check(MODE, _bt(75, -8, "2026-11-03"))           # still the same fall (not under the 70th)
    poolalert.zone_check(MODE, _bt(88, -11, "2026-11-04"))
    assert len(q()) == 1
    poolalert.zone_check(MODE, _bt(50, -2, "2026-11-05"))           # armed again
    poolalert.zone_check(MODE, _bt(82, -9.5, "2026-11-06"))
    assert len(q()) == 2


def test_zone_alert_dropped_by_a_full_month_comes_in_the_next(line, monkeypatch):
    _on(["qld_split_2c"])
    db.set_state("line_count", {"month": "2026-11", "n": 300, "days": {}})
    poolalert.zone_check(MODE, _bt(86, -10.5, "2026-11-27"))
    notify.dispatch(at(28, 12))
    assert not line and db.one("SELECT status FROM line_queue WHERE event='pool_add'")["status"] == "skipped"
    monkeypatch.setattr(notify, "budget", lambda now=None: {"state": "ok"})        # 1 December: a new month
    poolalert.zone_check(MODE, _bt(87, -10.8, "2026-11-30"))
    assert len(db.rows("SELECT * FROM line_queue WHERE event='pool_add'")) == 2
    poolalert.zone_check(MODE, _bt(87, -10.8, "2026-12-01"))
    assert len(db.rows("SELECT * FROM line_queue WHERE event='pool_add'")) == 2     # once


def test_zone_first_look_counts_the_fall_from_its_first_day(line):
    _on(["qld_split_2c"])
    st = poolalert.zone_check(MODE, _bt(89.6, last={"80": {"day": "2026-11-05", "open": True}}))
    assert st["since"] == "2026-11-05" and st["sent"]                  # the day this fall first passed the 80th
    v = poolalert.view(MODE, _bt(89.6, last={"80": {"day": "2026-11-05", "open": True}}))
    assert v["zone"]["th"] == 80 and v["zone"]["row"]["n"] == 57


def test_line_only_for_one_mode(line, monkeypatch):
    _on(["qld_split_2c"])
    monkeypatch.setattr(poolalert, "line_mode", lambda: "live")
    poolalert.zone_check(MODE, _bt(90))
    assert not db.rows("SELECT * FROM line_queue WHERE event='pool_add'")
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE 'Good time to add extra money%'")["n"] == 1


def test_monthly_reminder_on_the_day_or_the_next_weekday(line):
    _on(["qld_split_2c"])
    assert str(poolalert.reminder_day(2026, 11, 1)) == "2026-11-02"   # 1 Nov 2026 is a Sunday
    poolalert.month_check(MODE, at(1, 9))
    assert not db.rows("SELECT * FROM line_queue WHERE event='pool_month'")
    poolalert.month_check(MODE, at(2, 7))                             # its day, before 08:00
    assert not db.rows("SELECT * FROM line_queue WHERE event='pool_month'")
    st = poolalert.month_check(MODE, at(2, 8), _bt(64, -4.1))
    rows = db.rows("SELECT * FROM line_queue WHERE event='pool_month'")
    assert len(rows) == 1 and "November" in rows[0]["text"] and "64th percentile" in rows[0]["text"] and st["show"]
    poolalert.month_check(MODE, at(3, 9))
    assert len(db.rows("SELECT * FROM line_queue WHERE event='pool_month'")) == 1
    assert poolalert.view(MODE, None, at(3, 9))["month"]["name"] == "November"
    poolalert.month_done(MODE, at(3, 9))
    assert poolalert.view(MODE, None, at(3, 9))["month"] is None
    assert poolalert.view(MODE, None, at(1, 9, month=12))["month"]["name"] == "December"   # 1 Dec 2026: a Tuesday


def test_no_stale_reminder_when_first_installed_late_in_the_month(line):
    _on(["qld_split_2c"])
    assert poolalert.view(MODE, None, at(28, 9))["month"] is None      # installed on 28 Nov: November's day is long past
    st = poolalert.month_check(MODE, at(28, 9))
    assert st["done"] and not db.rows("SELECT * FROM line_queue WHERE event='pool_month'")
    poolalert.month_check(MODE, at(1, 9, month=12))
    assert len(db.rows("SELECT * FROM line_queue WHERE event='pool_month'")) == 1   # December comes as usual


def test_gap_alert(line, monkeypatch):
    _on(["qld_split_2c"])
    from datetime import date
    monkeypatch.setattr(pool, "since", lambda mode, c=None: int(datetime(2026, 11, 2, 15, tzinfo=notify.TZ).timestamp()))
    days = [date(2026, 10, 30)] + [date(2026, 11, d) for d in (2, 3, 4, 5, 6, 9)]
    real = [1.0, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95]
    monkeypatch.setattr(poolalert.perf, "real_index", lambda mode, sid: ([days[0]] + days, [1.0] + real))
    tail = [[str(d), 100 + i * 0.2] for i, d in enumerate(days)]
    bt = {"ready": True, "daily_tail": tail}
    g = poolalert.gap(MODE, bt)
    assert g["days"] == 6 and g["real"] == -5.0 and round(g["model"], 1) == 1.2 and g["gap"] < -5
    st = poolalert.gap_check(MODE, bt)
    assert st["show"] and not st["armed"]
    assert len(db.rows("SELECT * FROM line_queue WHERE event='pool_gap'")) == 1
    assert poolalert.view(MODE, bt)["gap"]["gap"] < -5


def test_member_past_its_worst_fall(line):
    _on(["qld_split_2c", "usd_trend_split"])
    db.set_state("dip:qld_split_2c", {"of_worst": 110, "worst10_years": 10, "depth": -27.0, "worst10": -24.7, "day": "2026-11-27"})
    db.set_state("dip:usd_trend_split", {"of_worst": 80, "worst10_years": 10})
    w = poolalert.worst_members(MODE)
    assert [x["id"] for x in w] == ["qld_split_2c"] and w[0]["worst"] == -24.7


def test_settings_and_line_switches(line):
    _on(["qld_split_2c"])
    p = poolalert.set_settings(MODE, {"zone_pct": 85, "month_day": 15, "gap_pts": 4, "line": {"month": False}})
    assert p["zone_pct"] == 85 and p["month_day"] == 15 and p["gap_pts"] == 4.0 and p["line"]["month"] is False
    assert notify.event_modes()["pool_month"] == "off"
    with pytest.raises(ValueError):
        poolalert.set_settings(MODE, {"zone_pct": 83})
    with pytest.raises(ValueError):
        poolalert.set_settings(MODE, {"month_day": 31})


def test_members_get_no_per_strategy_add_alert(clean):
    _on(["qld_split_2c"])
    assert dip.in_pool("qld_split_2c") and not dip.in_pool("usd_trend_split")
    pool.set_settings(MODE, on_=False)
    assert not dip.in_pool("qld_split_2c")


def test_api_alerts_and_month_done(clean, clock):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    _on(["qld_split_2c"])
    with TestClient(app) as c:
        sign_in(c)
        r = c.post("/api/pool/alerts", json={"mode": MODE, "zone_pct": 90, "line": {"gap": False}})
        assert r.status_code == 200 and r.json()["zone_pct"] == 90 and r.json()["line"]["gap"] is False
        assert c.post("/api/pool/alerts", json={"mode": MODE, "zone_pct": 3}).status_code == 400
        assert c.post("/api/pool/month_done", json={"mode": MODE}).json()["done"] is True


def test_daily_points_carry_the_percentile_for_the_zoomed_chart():
    v = _falls()
    pct = pool.daily_pct(v)
    d, w, z = pool.daily(v, pct), pool.weekly(v, pct), pool.zones(v, pct)
    assert len(d) == len(v) and d[0][3] is None and d[-1][3] == round(z["pct"], 1) and d[-1][2] == z["depth"]
    assert all(len(p) == 4 for p in w) and w[-1][3] == d[-1][3]
