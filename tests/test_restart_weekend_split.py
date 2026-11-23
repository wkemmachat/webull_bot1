"""23 Nov 2026: LINE only for unexpected restarts (deploys and normal restarts go to Logs), digests paused at the weekend,
weekly report fills before a split compared with the open before the split."""
from datetime import datetime

import pytest

from app import db, engine, notify, weekly
from test_notify import line  # noqa: F401  (fixture)


def at(day, h, m=0):                                   # 24 Oct 2026 is a Saturday
    return datetime(2026, 10, day, h, m, tzinfo=notify.TZ)


# ---------------------------------------------------------------- weekend pause
def test_weekend_pause(line):
    notify.send("system", "Friday thing")
    notify.dispatch(at(24, 8, 0))                       # Saturday 08:00 still goes (Friday's US close)
    assert len(line) == 1 and "Friday thing" in line[0][1]
    notify.send("system", "Weekend thing")
    for d, h in ((24, 21), (25, 8), (25, 21)):
        notify.dispatch(at(d, h, 0))
    assert len(line) == 1                               # Saturday evening and Sunday: paused
    notify.dispatch(at(26, 8, 0))                       # Monday 08:00: everything held, once
    assert len(line) == 2 and "Weekend thing" in line[1][1]
    notify.dispatch(at(26, 8, 5))
    assert len(line) == 2


def test_weekend_pause_off_and_instant_alerts(line):
    db.set_settings({"line_weekend_pause": "0"})
    notify.send("system", "Weekend thing")
    notify.dispatch(at(24, 21, 0))
    assert len(line) == 1
    db.set_settings({"line_weekend_pause": "1"})
    notify.send("signal", "Gold BUY")                   # instant alerts are never paused
    notify.dispatch(at(25, 12, 0))
    assert len(line) == 2 and "Gold BUY" in line[1][1]


def test_paused_times_and_next_digest(line):
    assert notify.weekend_paused(at(24, 0, 0), "12:00") and notify.weekend_paused(at(25, 0, 0), "08:00")
    assert not notify.weekend_paused(at(24, 0, 0), "08:00") and not notify.weekend_paused(at(26, 0, 0), "08:00")
    assert notify.weekend_paused(at(26, 0, 0), "06:00")
    assert notify.next_digest(at(24, 13, 0)) == "Mon 08:00"
    assert notify.next_digest(at(21, 9, 0)) == "21:00"
    assert notify.settings_public()["weekend_pause"] is True
    notify.save_settings({"weekend_pause": False})
    assert notify.settings_public()["weekend_pause"] is False and notify.next_digest(at(24, 13, 0)) == "21:00"


# ---------------------------------------------------------------- restarts
def _last_event():
    return db.one("SELECT * FROM events WHERE source='server' ORDER BY id DESC LIMIT 1")


def test_restart_kinds(clean, monkeypatch):
    for k in ("run_start", "run_stop"):
        db.run("DELETE FROM state WHERE k=?", (k,))
    db.run("DELETE FROM line_queue")
    monkeypatch.setattr(engine, "code_version", lambda: "aaaaaaa")
    engine._note_restart()                              # first start with the check: Logs only
    assert _last_event()["title"] == "Bot started"
    engine.mark_stop()
    engine._note_restart()                              # normal restart, same version
    assert "shut down normally" in (_last_event()["message"] or _last_event()["detail"] or "")
    engine.mark_stop()
    monkeypatch.setattr(engine, "code_version", lambda: "bbbbbbb")
    engine._note_restart()                              # deploy
    assert "aaaaaaa → bbbbbbb" in (_last_event()["message"] or _last_event()["detail"] or "")
    assert db.one("SELECT COUNT(*) n FROM line_queue")["n"] == 0
    db.set_state("run_stop", {"at": 1, "version": "bbbbbbb"})   # an old record: this run never shut down normally
    engine._note_restart()
    e = _last_event()
    assert e["title"] == "Bot restarted unexpectedly" and e["level"] == "warn"
    q = db.one("SELECT * FROM line_queue WHERE event='restart'")
    assert q and q["delivery"] == "instant" and "didn't shut down normally" in q["text"]
    assert db.one("SELECT COUNT(*) n FROM events WHERE title='Bot started'")["n"] == 4   # Go-live restart test still sees every start


def test_code_version_reads_git(tmp_path, monkeypatch):
    assert engine.code_version() is None or len(engine.code_version()) == 7


# ---------------------------------------------------------------- split
def test_split_factor():
    assert weekly.split_factor(110.22, 36.75) == 3
    assert weekly.split_factor(36.9, 36.75) == 1
    assert weekly.split_factor(9.2, 36.75) == pytest.approx(0.25)
    assert weekly.split_factor(60.0, 36.75) is None
    assert weekly.split_text(3) == "3-for-1 split" and weekly.split_text(0.25) == "1-for-4 reverse split"


def test_fill_before_split_uses_the_open_before_it(clean, monkeypatch):
    monkeypatch.setattr(weekly, "day_open", lambda sym, d: 36.75)
    t = int(datetime(2026, 11, 18, 15, 0, tzinfo=notify.TZ).timestamp())
    db.run("INSERT INTO orders(mode,strategy,symbol,side,applied_qty,applied_value,submitted_at,updated_at,status) "
           "VALUES('live','rom_vol_ibs','ROM','BUY',7,771.54,?,?,'filled')", (t, t))
    db.run("INSERT INTO orders(mode,strategy,symbol,side,applied_qty,applied_value,submitted_at,updated_at,status) "
           "VALUES('live','rom_vol_ibs','ROM','SELL',3,180,?,?,'filled')", (t, t))       # 60/36.75: no clean ratio
    f = weekly.fills("live", t - 10)
    a, b = f
    assert a["split"] == 3 and a["open"] == pytest.approx(110.25) and a["cost"] == pytest.approx((110.22 - 110.25) * 7)
    assert b["open"] is None and b["cost"] is None
    c = weekly.cost_summary(f)
    assert c["unknown"] == 1 and abs(c["cost_pct"]) < 0.01
    r = {"mode": "live", "from": "2026-11-16", "to": "2026-11-20", "value": 1000, "ret": 0.01, "usd": 10, "strategies": [],
         "week_costs": weekly.cost_summary(f), "since_costs": weekly.cost_summary(f), "since_from": "2026-10-27",
         "worst": dict(a, name="ROM · Trend", cost_pct=0.005)}
    assert "open before the 3-for-1 split" in weekly.text(r)


def test_repair_stored_once(clean, monkeypatch):
    monkeypatch.setattr(weekly, "day_open", lambda sym, d: 36.75)
    t = int(datetime(2026, 11, 18, 15, 0, tzinfo=notify.TZ).timestamp())
    db.run("INSERT INTO orders(mode,strategy,symbol,side,applied_qty,applied_value,submitted_at,updated_at,status) "
           "VALUES('live','rom_vol_ibs','ROM','BUY',7,771.54,?,?,'filled')", (t, t))
    bad = {"mode": "live", "week": "2026-11-16", "from": "2026-11-16", "to": "2026-11-20", "at": t + 86400 * 3, "value": 1000,
           "ret": 0.01, "usd": 10, "strategies": [], "fills": [], "since_from": "2026-11-18",
           "week_costs": {"cost": 514.29}, "since_costs": {"cost": 514.29}, "text": "old"}
    db.set_state("weekly:live", [bad])
    db.run("DELETE FROM state WHERE k='weekly_split_fix'")
    weekly.repair_stored()
    r = weekly.stored("live")[0]
    assert r["week_costs"]["cost"] == pytest.approx(-0.21) and r["value"] == 1000 and "−199" not in r["text"]
    db.set_state("weekly:live", [bad])
    weekly.repair_stored()                              # only once
    assert weekly.stored("live")[0]["text"] == "old"
