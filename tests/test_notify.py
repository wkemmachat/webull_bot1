"""LINE: instant / digest / off, quiet hours, critical alerts, per-strategy switch."""
from datetime import datetime

import pytest

from app import db, notify


@pytest.fixture
def line(clean):
    sent = []
    notify.set_transport(lambda to, text: (sent.append((to, text)), (True, None))[1])
    db.set_settings({"line_token": "tok", "line_recipients": [{"id": "Uabc", "name": "me", "enabled": True, "scope": "all"}],
                     "line_quiet": "1", "line_quiet_from": "00:30", "line_quiet_to": "07:00",
                     "line_digest_times": ["08:00", "21:00"]})
    db.run("DELETE FROM line_queue")
    return sent


def at(h, m=0):
    return datetime(2026, 10, 21, h, m, tzinfo=notify.TZ)


def test_instant_alerts_are_joined(line):
    notify.send("signal", "Gold BUY")
    notify.send("money", "Added $1,000")
    notify.dispatch(at(12))
    assert len(line) == 1 and "Gold BUY" in line[0][1] and "Added $1,000" in line[0][1] and "2 alerts" in line[0][1]
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE status='sent'")["n"] == 2


def test_quiet_hours_hold_but_critical_goes(line):
    notify.send("signal", "Gold SELL")
    notify.send("lot_failed", "BUY 10 UGL failed")
    notify.dispatch(at(3))
    assert len(line) == 1 and "failed" in line[0][1] and "SELL" not in line[0][1]
    notify.dispatch(at(7, 1))
    assert len(line) == 2 and "Gold SELL" in line[1][1]


def test_digest_at_its_time(line):
    db.set_settings({"line_events": {"signal": "digest"}})
    notify.send("signal", "Silver BUY")
    notify.dispatch(at(7, 59))
    assert not line
    notify.dispatch(at(8, 0))
    assert len(line) == 1 and "Silver BUY" in line[0][1]
    notify.dispatch(at(8, 5))
    assert len(line) == 1                               # once per digest time


def test_off_and_critical_cannot_be_off(line):
    db.set_settings({"line_events": {"signal": "off", "lot_failed": "off"}})
    assert db.one("SELECT status FROM line_queue WHERE id=?", (notify.send("signal", "x"),))["status"] == "skipped"
    assert notify.event_modes()["lot_failed"] == "instant"


def test_strategy_switch(line):
    db.set_settings({"line_auto": "0"})                       # manual switches
    db.run("UPDATE strategies SET line_on=0 WHERE id='gold_sta'")
    assert notify.send("signal", "muted", strategy="gold_sta") is None
    assert notify.send("lot_failed", "still sent", strategy="gold_sta")


def _money(sid, mode="paper", cash=0.0, shares=0.0):
    from app import ledger
    ledger.ensure(mode, sid)
    db.run("UPDATE ledger SET cash=? WHERE mode=? AND strategy=?", (cash, mode, sid))
    db.run("DELETE FROM holdings WHERE mode=? AND strategy=?", (mode, sid))
    if shares:
        db.run("INSERT INTO holdings(mode,strategy,symbol,qty,cost) VALUES(?,?,?,?,?)", (mode, sid, "UGL", shares, 40.0))


def test_automatic_follows_state_and_money(line):
    assert notify.line_auto()                                  # the default
    db.run("UPDATE strategies SET line_on=0, control='active' WHERE id IN ('gold_sta','gold_st30','silver_dc')")
    _money("gold_sta", cash=500)                               # active with cash → on
    _money("gold_st30", shares=3)                              # active with shares only → on
    _money("silver_dc", cash=0.4)                              # crumbs only → off
    assert notify.send("signal", "sent before the sync", strategy="gold_sta")
    changed = dict(notify.sync_auto())
    assert changed.get("gold_sta") is True and changed.get("gold_st30") is True and "silver_dc" not in changed
    on = {r["id"]: r["line_on"] for r in db.rows("SELECT id, line_on FROM strategies")}
    assert on["gold_sta"] == 1 and on["gold_st30"] == 1 and on["silver_dc"] == 0
    assert notify.send("signal", "muted", strategy="silver_dc") is None
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE '%LINE alerts turned on automatically%'")["n"] >= 2
    # stopped: the last message still goes (the switch is on until the next sync), then it turns off
    db.run("UPDATE strategies SET control='stopped' WHERE id='gold_sta'")
    assert notify.send("signal", "stopped · everything sold", strategy="gold_sta")
    assert dict(notify.sync_auto()).get("gold_sta") is False
    assert notify.send("signal", "muted now", strategy="gold_sta") is None
    assert notify.send("lot_failed", "critical always comes", strategy="gold_sta")
    assert notify.sync_auto() == []                            # nothing left to change


def test_automatic_counts_live_money_once_live_is_on(line):
    db.run("UPDATE strategies SET line_on=0, control='active' WHERE id='gold_sta'")
    _money("gold_sta", "paper", cash=10000)
    db.set_settings({"mode_live": "1"})
    _money("gold_sta", "live", cash=0)
    assert not notify.auto_on("gold_sta")                      # paper money does not count when Live is on
    _money("gold_sta", "live", cash=250)
    assert notify.auto_on("gold_sta")


def test_reports_only_recipient(line):
    db.set_settings({"line_recipients": [{"id": "Uabc", "enabled": True, "scope": "all"},
                                         {"id": "Cgroup", "enabled": True, "scope": "reports"}]})
    notify.send("signal", "Gold BUY")
    notify.dispatch(at(12))
    assert [to for to, _ in line] == ["Uabc"]


def test_bad_recipient_id_is_refused(clean):
    with pytest.raises(ValueError):
        notify.save_settings({"recipients": [{"id": "not-an-id", "name": "x"}]})
