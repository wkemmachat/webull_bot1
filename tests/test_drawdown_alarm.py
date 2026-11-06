"""Deep-fall warning (today's fall vs the worst 10-year fall before it) and "What your money is in" (exposure by underlying)."""
import numpy as np
import pandas as pd
import pytest

from app import db, dip, exposure, ledger, notify, views
from app import strategies as S


def _path(points):
    """A value series through (date, value) points, straight lines between them (business days)."""
    idx = pd.bdate_range(points[0][0], points[-1][0])
    s = pd.Series(np.nan, index=idx)
    for d, v in points:
        s[pd.Timestamp(d)] = v
    return s.interpolate()


def test_worst_fall_before_this_one():
    s = _path([("2008-01-02", 100), ("2008-11-20", 30),                 # −70% in 2008 (only in the whole backtest)
               ("2018-08-29", 300), ("2018-12-24", 210),                 # −30% in 2018 (the worst of the last 10 years)
               ("2026-06-02", 500), ("2026-11-05", 320)])                 # today: −36% below the June high
    d = dip.from_series(s.index, s.values)
    assert d["peak_day"] == "2026-06-02" and d["depth"] == pytest.approx(-36.0)
    assert d["worst10"] == pytest.approx(-30.0) and d["worst10_from"] == "2018-08-29" and d["worst10_to"] == "2018-12-24"
    assert d["worst_all"] == pytest.approx(-70.0) and d["worst_all_to"] == "2008-11-20"
    assert d["of_worst"] == 120 and dip.warn_level(d["of_worst"], d["worst10_years"]) == 100   # today is not compared with itself
    assert dip.warn_level(74, 10) == 0 and dip.warn_level(75, 10) == 75 and dip.warn_level(99, 10) == 75
    assert dip.warn_level(150, 1.3) is None                                 # a 1.3-year backtest is too short to compare


def test_warns_once_at_75_and_once_past_the_worst_then_rearms_at_a_new_high(clean, monkeypatch):
    notify.set_transport(lambda *a, **k: (True, ""))
    st = {"of": 60, "peak": "2026-06-02"}

    def fake(s, now=None):
        if s.id != "rom_tbd":
            return None
        return {"depth": -st["of"] * 0.3, "pct": 50.0, "zone": None, "p70": -14.0, "p80": -18.0, "p90": -25.0,
                "day": "2026-11-05", "from": "2006-11-06", "years": 20.0, "peak_day": st["peak"], "worst10": -30.0,
                "worst10_from": "2018-08-29", "worst10_to": "2018-12-24", "worst10_years": 10.0, "worst_all": -70.0,
                "worst_all_from": "2007-10-31", "worst_all_to": "2008-11-20", "of_worst": st["of"]}
    monkeypatch.setattr(dip, "compute", fake)
    q = lambda: db.rows("SELECT * FROM line_queue WHERE event='drawdown' ORDER BY id")
    dip.refresh_all()
    assert q() == []                                                        # 60%: nothing yet
    st["of"] = 80
    dip.refresh_all()
    assert len(q()) == 1 and "Near its worst fall · ROM Trend + RSI(2)" in q()[0]["text"] and "-30.0%" in q()[0]["text"]
    dip.refresh_all()
    st["of"] = 90
    dip.refresh_all()
    assert len(q()) == 1                                                    # still the same level: no second message
    st["of"] = 110
    dip.refresh_all()
    assert len(q()) == 2 and "Deeper than its worst fall" in q()[1]["text"]
    st["of"] = 20
    dip.refresh_all()
    st["of"] = 80
    dip.refresh_all()
    assert len(q()) == 2                                                    # same fall (same high): not again
    st.update(of=80, peak="2027-02-01")
    dip.refresh_all()
    assert len(q()) == 3                                                    # a new high, then a new fall: armed again
    assert dip.get("rom_tbd")["warn"] == 75
    assert "drawdown" in notify.EVENTS


def test_your_money_fall_leaves_out_money_added(clean, clock):
    from datetime import datetime, timezone
    from app import execution
    sid = "rom_tbd"
    db.run("UPDATE ledger SET cash=1000, cap_in=1000, cap_out=0 WHERE mode='paper' AND strategy=?", (sid,))
    for day, cash, cap in ((21, 1000, 1000), (22, 1200, 1000), (23, 1900, 2000)):    # +20%, then $1,000 added and −25%
        db.run("UPDATE ledger SET cash=?, cap_in=? WHERE mode='paper' AND strategy=?", (cash, cap, sid))
        clock.set(datetime(2026, 10, day, 15, 0, tzinfo=timezone.utc))              # 11:00 New York, regular session
        execution.record_equity("paper", force=True)
    m = dip.money_fall("paper", sid)
    assert m["fall"] == pytest.approx((900 / 1200 - 1) * 100, abs=0.1) and m["high_day"] == "2026-10-22"
    assert views.strategy_detail("paper", sid)["money_fall"]["fall"] == m["fall"]


def test_exposure_groups_and_adds_up():
    cards = [
        {"id": "a", "name": "ROM one", "color": "#111", "cash": 100.0, "positions": {"ROM": {"qty": 10, "value": 1000.0}}},
        {"id": "b", "name": "QLD one", "color": "#222", "cash": 0.0, "positions": {"QLD": {"qty": 5, "value": 500.0}, "GLD": {"qty": 2, "value": 400.0}}},
        {"id": "c", "name": "Semis", "color": "#333", "cash": 0.0, "positions": {"SMH": {"qty": 1, "value": 300.0}, "BIL": {"qty": 1, "value": 200.0}}},
    ]
    x = exposure.of_cards(cards)
    assert x["total"] == 2500.0
    r = {g["key"]: g for g in x["rows"]}
    assert set(r) == {"tech", "nasdaq", "semis", "gold", "tbills", "cash"}
    assert r["tech"]["acts_like"] == pytest.approx(2000 / 2500) and r["semis"]["acts_like"] == pytest.approx(300 / 2500)
    assert sum(g["pct"] for g in x["rows"]) == pytest.approx(1.0)
    t = x["us_tech"]
    assert t["value"] == 1800.0 and t["acts_like"] == pytest.approx((2000 + 1000 + 300) / 2500)
    assert t["leveraged_pct"] == pytest.approx(1500 / 1800) and t["fall10"] == pytest.approx(-330.0) and t["strategies"] == 3
    assert exposure.classify("SOXL") == ("semis", 3) and exposure.classify("ZZZZ", {}, set())[0] == "other"


def test_dashboard_has_exposure(clean):
    d = views.dashboard("paper")
    assert "exposure" in d and d["exposure"] is not None and "us_tech" in d["exposure"]
