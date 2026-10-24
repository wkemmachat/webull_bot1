"""Price feed hiccups: no Yahoo calls while COMEX is closed, back-off on failures, LINE only when it lasts and matters."""
from datetime import datetime, timezone

import pytest

from app import db, engine, marketdata as md, metals
from conftest import NOW


def test_comex_close_clock():
    sat = datetime(2026, 10, 24, 3, 56, tzinfo=timezone.utc)            # Fri 23:56 New York (the LINE alert)
    assert metals.last_close(sat).isoformat() == "2026-10-23T21:00:00+00:00"   # Fri 17:00 New York
    assert metals.last_close(NOW) is None                                # Wed 11:00 New York: open
    brk = datetime(2026, 10, 21, 21, 30, tzinfo=timezone.utc)            # 17:30 New York daily break
    assert metals.last_close(brk).isoformat() == "2026-10-21T21:00:00+00:00"


def test_no_downloads_on_the_weekend(clean, clock, monkeypatch):
    monkeypatch.setattr(md, "source", lambda: "yahoo")
    sat = clock.set(datetime(2026, 10, 24, 3, 56, tzinfo=timezone.utc))
    db.set_state("data_updated:GC:1h", int(datetime(2026, 10, 23, 21, 40, tzinfo=timezone.utc).timestamp()))
    assert metals.due("GC", sat) is False
    db.set_state("data_updated:GC:1h", int(datetime(2026, 10, 23, 20, 0, tzinfo=timezone.utc).timestamp()))
    assert metals.due("GC", sat) is True                                 # still needs the closing bars once


def _line(kind="data"):
    return [r["text"] for r in db.rows("SELECT text FROM line_queue WHERE event=? ORDER BY id", (kind,))]


def test_failures_back_off_and_alert_once(clean, clock, monkeypatch):
    calls = []
    real = metals.update

    def flaky(sym):
        calls.append(sym)
        if sym == "GC" and broken["on"]:
            raise md.DataError("Yahoo returned no 1h data for GC=F")
        return real(sym)
    broken = {"on": True}
    monkeypatch.setattr(metals, "update", flaky)
    db.set_state("data_status", {})
    engine.refresh_data(clock.dt)
    assert _line() == []                                                 # one hiccup: no LINE
    n = calls.count("GC")
    clock.advance(seconds=30)
    engine.refresh_data(clock.dt)
    assert calls.count("GC") == n                                        # waits 1 minute before retrying
    for _ in range(40):
        clock.advance(minutes=1)
        engine.refresh_data(clock.dt)
    assert calls.count("GC") < 12                                        # 1, 2, 4, 8 … minutes apart
    msgs = _line()
    assert len(msgs) == 1 and "GC:1h" in msgs[0] and "does not trade on old prices" in msgs[0]
    broken["on"] = False
    for _ in range(35):
        clock.advance(minutes=1)
        engine.refresh_data(clock.dt)
    assert any("OK again" in m for m in _line())
    assert (db.get_state("data_status") or {})["GC:1h"]["ok"] is True
