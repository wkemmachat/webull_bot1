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
    # money added counts from the start of its day (as on the Falls page): 1.2 × (1 + (1900 − 1200 − 1000) / 2200)
    assert m["fall"] == pytest.approx((1.2 * (1 - 300 / 2200) / 1.2 - 1) * 100, abs=0.1) and m["high_day"] == "2026-10-22"
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


def test_real_return_is_not_changed_by_moving_money_out_after_a_loss(clean, clock):
    """This week's ROM case: $5,500 in, −27%, then $2,500 moved out. On the $3,000 left the simple % looks like −50%;
    the real result is still −27.3%."""
    from datetime import datetime, timezone
    from app import execution, perf
    sid = "rom_tbd"
    for day, cash, cap in ((26, 5500, 5500), (27, 4000, 5500), (28, 1500, 3000)):
        db.run("UPDATE ledger SET cash=?, cap_in=?, cap_out=0 WHERE mode='paper' AND strategy=?", (cash, cap, sid))
        clock.set(datetime(2026, 10, day, 15, 0, tzinfo=timezone.utc))
        execution.record_equity("paper", force=True)
    v = ledger.value("paper", sid)
    assert v["ret"] == pytest.approx(-0.5)
    r = perf.real_return("paper", sid, v["value"], v["net_in"])
    assert r["ret"] == pytest.approx(4000 / 5500 - 1) and r["since"] == "2026-10-26"
    c = views.strategy_card("paper", S.get(sid)) if hasattr(views, "strategy_card") else None
    if c is not None:
        assert c["real"]["ret"] == pytest.approx(r["ret"])
    b = views.dashboard("paper")["bot"]
    assert "real" in b


def test_same_bet_preview_add_and_move(clean):
    from app import exposure
    db.run("INSERT OR REPLACE INTO strategy_state(strategy, target, ok) VALUES('rom_tbd', '{\"ROM\": 0.99}', 1)")
    db.run("INSERT OR REPLACE INTO strategy_state(strategy, target, ok) VALUES('gold_sta', '{\"UGL\": 0.99}', 1)")
    x = exposure.preview("paper", "add", "rom_tbd", 1000)
    assert x["target"] == {"ROM": 0.99}
    assert x["after"]["total"] == pytest.approx(x["before"]["total"] + 1000)
    assert x["after"]["value"] == pytest.approx(x["before"]["value"] + 990)                 # 99% into ROM
    assert x["after"]["acts_like"] * x["after"]["total"] == pytest.approx(x["before"]["acts_like"] * x["before"]["total"] + 1980)
    w = exposure.preview("paper", "add", "rom_tbd", 1000, invest="wait")
    assert w["after"]["value"] == pytest.approx(w["before"]["value"]) and w["target"] == {}   # waits as cash
    m = exposure.preview("paper", "move", "rom_tbd", 500, to="gold_sta")
    assert m["after"]["total"] == pytest.approx(m["before"]["total"])                         # moving is not adding
    assert m["dest"]["id"] == "gold_sta"


def test_falls_now_counts_past_falls_deeper_than_today():
    from datetime import date, timedelta
    from app import perf
    vals = [100, 80, 100, 101, 70, 90, 101, 102, 95, 102.5, 103, 85]       # falls of −20%, −30.7%, −6.9%; now −17.5%
    days = [date(2020, 1, 1) + timedelta(days=30 * i) for i in range(len(vals))]
    x = perf.falls_now(days * 1, vals) if len(vals) >= 30 else None
    long_v = vals * 3                                                        # three rounds so there are 30+ days
    long_v = [v * (1.05 ** (i // len(vals))) for i, v in enumerate(long_v)]
    long_d = [date(2020, 1, 1) + timedelta(days=30 * i) for i in range(len(long_v))]
    x = perf.falls_now(long_d, long_v)
    assert x["episodes"] >= 6 and x["deeper"] >= 4                          # each round has a −20% and a −30.7% fall
    assert x["back_months"] is not None and 0 < x["of_worst"] <= 100
    u = perf.daily_underwater(long_d, long_v)
    assert len(u["t"]) == len(long_v) and u["v"][0] == 10000 and max(u["dd"]) == 0 and min(u["dd"]) < -30
