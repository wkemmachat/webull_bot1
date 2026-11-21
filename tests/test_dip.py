"""Dip zones: a strategy's underwater percentile, the LINE alert on entering the 85th percentile (only where the add-money
signal works, addmoney.py), and the cards."""
import numpy as np
import pandas as pd

from app import addmoney, db, dip, notify, views
from app import strategies as S


def _series(final_depth):
    idx = pd.bdate_range("2015-01-01", "2026-10-23")
    rng = np.random.default_rng(3)
    v = np.exp(np.cumsum(rng.normal(0.0006, 0.02, len(idx)))) * 100
    peak = v.max()
    v[-1] = peak * (1 + final_depth)                     # the last day: final_depth below the all-time high
    return idx, v


def test_percentile_and_zones():
    t, v = _series(0.0)
    v[-1] = v[:-1].max() * 1.01                           # a new high
    d = dip.from_series(t, v)
    assert d["pct"] == 0 and d["zone"] is None and d["depth"] == 0.0
    t, v = _series(-0.99)
    d = dip.from_series(t, v)
    assert d["pct"] >= 99 and d["zone"] == "deep" and d["depth"] < -90
    assert d["p70"] > d["p80"] > d["p85"] > d["p90"]      # deeper percentiles are more negative
    assert dip.zone_of(75) == "dip" and dip.zone_of(84.9) == "dip" and dip.zone_of(85) == "deep" and dip.zone_of(69.9) is None


def _add(verdict):
    return {"v": addmoney.VERSION, "verdict": verdict, "zone": 85.0, "zone_depth": -15.0, "buy_depth": -9.0, "since": "2009-01-05",
            "entries": [["2011-08-08", 0.23], ["2020-03-16", 1.5]], "n": 30, "up_n": 30, "entry_med": 0.51, "entry_worst": 0.03,
            "zone_days": {"days": 400, "up": 0.98, "med": 0.51, "p10": 0.11, "p90": 1.0, "fall_med": -0.04, "fall_p10": -0.08},
            "any_day": {"days": 3000, "up": 0.94, "med": 0.40, "p10": 0.05, "p90": 0.98, "fall_med": -0.07, "fall_p10": -0.16},
            "wait": {"worse": 0.39, "better": 0.43, "mean": -0.045, "wait_days": 44, "never": 0.12}}


def test_line_once_per_dip_and_rearm(clean, monkeypatch):
    notify.set_transport(lambda *a, **k: (True, ""))
    vals = {"pct": 90.0, "verdict": "good"}

    def fake(s, now=None):
        if s.id != "qld_regime":
            return None
        p = vals["pct"]
        return {"depth": -20.0, "pct": p, "zone": dip.zone_of(p), "p70": -14.0, "p80": -18.0, "p90": -25.0,
                "day": "2026-10-23", "from": "2016-10-24", "years": 10.0}
    monkeypatch.setattr(dip, "compute", fake)
    monkeypatch.setattr(addmoney, "compute", lambda s, now=None: _add(vals["verdict"]) if s.id == "qld_regime" else None)
    q = lambda: db.rows("SELECT * FROM line_queue WHERE event='dip'")
    dip.refresh_all()
    assert len(q()) == 1
    t = q()[0]["text"]
    assert t.startswith("▲ Good time to add money · QLD regime") and "30 of 30 times — every time" in t
    assert "$1,000 added then → typically $1,510 a year later (bad year $1,110)" in t and "typically to $960" in t
    dip.refresh_all()                                    # still deep: no second message
    assert len(q()) == 1
    vals["pct"] = 75.0
    dip.refresh_all()                                    # 70–85: not re-armed yet
    vals["pct"] = 90.0
    dip.refresh_all()
    assert len(q()) == 1
    vals["pct"] = 82.0
    dip.refresh_all()                                    # 80–85: no longer an alert level (was 80 before 20 Nov 2026)
    assert len(q()) == 1
    vals["pct"] = 50.0
    dip.refresh_all()                                    # out of the zones: armed again
    vals["pct"] = 86.0
    dip.refresh_all()
    assert len(q()) == 2
    card = views.strategy_card("paper", S.get("qld_regime"))
    assert card["dip"]["zone"] == "deep" and card["dip"]["pct"] == 86.0 and card["dip"]["verdict"] == "good"
    assert card["dip"]["add_since"] == "2026-10-23"                  # the day it entered the add window (Dashboard "New")
    assert views.topbar()["issues"]["add"] == 1                      # the green badge on Dashboard in the menu
    vals["pct"] = 60.0
    dip.refresh_all()
    assert dip.get("qld_regime")["add_since"] is None and views.topbar()["issues"]["add"] == 0
    assert card["add"]["in_zone"] and card["add"]["label"] == "Good time" and card["add"]["up_n"] == 30


def test_no_alert_where_the_signal_has_no_edge(clean, monkeypatch):
    notify.set_transport(lambda *a, **k: (True, ""))

    def fake(s, now=None):
        return {"depth": -30.0, "pct": 95.0, "zone": "deep", "p70": -14.0, "p80": -18.0, "p90": -25.0,
                "day": "2026-10-23", "from": "2016-10-24", "years": 10.0} if s.id in ("gold_sta", "usd_trend_split") else None
    monkeypatch.setattr(dip, "compute", fake)
    monkeypatch.setattr(addmoney, "compute", lambda s, now=None: _add("none" if s.id == "gold_sta" else "safer"))
    dip.refresh_all()
    rows = db.rows("SELECT * FROM line_queue WHERE event='dip'")
    assert len(rows) == 1 and rows[0]["text"].startswith("▲ OK time to add money (safer, not bigger) · USD")
    ev = db.rows("SELECT * FROM events WHERE strategy='gold_sta'")
    assert any("No add-money alert" in (e["message"] or "") for e in ev)
    assert addmoney.get("gold_sta")["label"] == "No signal"


def test_dip_event_is_a_line_choice():
    assert "dip" in notify.EVENTS


def test_window_is_20_years_and_a_new_window_recomputes(clean):
    from app import dip, db
    assert dip.WINDOW_YEARS == 20
    db.set_state("dip:qld_regime", {"pct": 50, "zone": None, "at": 1, "alerted": False})       # stored by the 10-year version
    assert dip.missing()


def test_a_new_strategy_with_no_zone_yet_is_missing(clean):
    from app import dip, db
    base = {"win": dip.WINDOW_YEARS, "worst10": -30.0, "v": dip.VERSION, "at": 1}
    for s in S.all_instances():
        db.set_state(f"dip:{s.id}", base)
        db.set_state(f"add:{s.id}", {"v": addmoney.VERSION})
    assert not dip.missing()
    db.set_state("add:usd_ibs", None)                           # the add-money odds (20 Nov 2026) not worked out yet
    assert dip.missing()
    db.set_state("addtry:usd_ibs", int(__import__("time").time()))     # too short / failed today: wait a day
    assert not dip.missing()
    db.set_state("dip:rxl_ichi_calm", None)                    # added by an update: nothing stored yet
    assert dip.missing()
    db.set_state("diptry:rxl_ichi_calm", int(__import__("time").time()))   # its backtest just failed: wait for the next close
    assert not dip.missing()
