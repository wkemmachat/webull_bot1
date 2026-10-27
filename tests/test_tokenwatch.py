"""Webull login reminders: LINE at 5, 3, 1 days left and when ended; Home banner data."""
from app import brokers, db, tokenwatch, views

DAY = 86400


class FakeWebull(brokers.PaperBroker):
    lapses = None

    def status(self):
        return {"connected": True, "lapses_at": self.lapses}


def _setup(monkeypatch, ends):
    fb = FakeWebull()
    fb.lapses = ends
    brokers.set_override("live", fb)
    db.set_settings({"mode_live": "1"})
    return fb


def test_reminders_once_per_step_and_reset_on_renew(clean, monkeypatch):
    t0 = 1_800_000_000
    fb = _setup(monkeypatch, t0 + 10 * DAY)
    q = lambda: db.rows("SELECT text, critical FROM line_queue WHERE event='broker' ORDER BY id")
    assert tokenwatch.check(t0) == []                                     # 10 days left: nothing
    assert tokenwatch.check(t0 + 5.5 * DAY) == [("live", 5)]              # 4.5 days left
    assert "ends in 5 days" in q()[-1]["text"]
    assert tokenwatch.check(t0 + 6 * DAY) == []                           # still the same step
    assert tokenwatch.check(t0 + 7.5 * DAY) == [("live", 3)]
    assert tokenwatch.check(t0 + 9.5 * DAY) == [("live", 1)] and q()[-1]["critical"] == 1
    assert tokenwatch.check(t0 + 10.1 * DAY) == [("live", 0)] and "ENDED" in q()[-1]["text"]
    assert tokenwatch.check(t0 + 11 * DAY) == []
    fb.lapses = t0 + 26 * DAY                                             # renewed: steps start again
    assert tokenwatch.check(t0 + 11 * DAY) == []
    assert tokenwatch.check(t0 + 21.5 * DAY) == [("live", 5)]
    brokers.set_override("live", None)


def test_bot_off_past_steps_sends_only_the_nearest(clean, monkeypatch):
    t0 = 1_800_000_000
    _setup(monkeypatch, t0 + 0.5 * DAY)
    assert tokenwatch.check(t0) == [("live", 1)]
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE event='broker'")["n"] == 1
    brokers.set_override("live", None)


def test_home_gets_the_login_end(clean, monkeypatch):
    import time
    _setup(monkeypatch, time.time() + 2 * DAY)
    x = [l for l in views.dashboard("paper")["logins"] if l["mode"] == "live"][0]
    assert x["status"] == "soon" and 1.9 < x["days_left"] < 2.1 and x["ends_text"]
    brokers.set_override("live", None)
