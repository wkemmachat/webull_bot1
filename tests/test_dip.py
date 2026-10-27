"""Dip zones: a strategy's underwater percentile, the LINE alert on entering the 80th percentile, and the cards."""
import numpy as np
import pandas as pd

from app import db, dip, notify, views
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
    assert d["p70"] > d["p80"] > d["p90"]                 # deeper percentiles are more negative
    assert dip.zone_of(75) == "dip" and dip.zone_of(80) == "deep" and dip.zone_of(69.9) is None


def test_line_once_per_dip_and_rearm(clean, monkeypatch):
    sent = []
    notify.set_transport(lambda *a, **k: sent.append(a) or (True, ""))
    vals = {"pct": 85.0}

    def fake(s, now=None):
        if s.id != "qld_regime":
            return None
        p = vals["pct"]
        return {"depth": -20.0, "pct": p, "zone": dip.zone_of(p), "p70": -14.0, "p80": -18.0, "p90": -25.0,
                "day": "2026-10-23", "from": "2016-10-24", "years": 10.0}
    monkeypatch.setattr(dip, "compute", fake)
    q = lambda: db.rows("SELECT * FROM line_queue WHERE event='dip'")
    dip.refresh_all()
    assert len(q()) == 1 and "Strong buy zone · QLD regime" in q()[0]["text"]
    dip.refresh_all()                                    # still deep: no second message
    assert len(q()) == 1
    vals["pct"] = 75.0
    dip.refresh_all()                                    # 70–80: not re-armed yet
    vals["pct"] = 90.0
    dip.refresh_all()
    assert len(q()) == 1
    vals["pct"] = 50.0
    dip.refresh_all()                                    # out of the zones: armed again
    vals["pct"] = 82.0
    dip.refresh_all()
    assert len(q()) == 2
    card = views.strategy_card("paper", S.get("qld_regime"))
    assert card["dip"]["zone"] == "deep" and card["dip"]["pct"] == 82.0


def test_dip_event_is_a_line_choice():
    assert "dip" in notify.EVENTS
