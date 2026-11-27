"""BIB · Rates + trend blend with IBS dips (Blend v) (27 Nov 2026): the deep dip, the legs, the VIX refetch, the live evaluation
and the backtest."""
from datetime import datetime, timezone

import numpy as np

from app import backtest as BT
from app import engine
from app import strategies as S
from app.strategies import rates_trend_blend as R
from conftest import NOW


def test_deep_dip_ends_on_a_close_above_the_high_a_failed_gate_or_the_days():
    start = np.array([0, 1, 0, 0, 0, 0, 0, 0], dtype=bool)
    gate = np.ones(8, dtype=bool)
    up = np.zeros(8, dtype=bool)
    assert list(R.deep_dip(start, gate, up, 5).astype(int)) == [0, 1, 1, 1, 1, 1, 0, 0]
    up2 = up.copy()
    up2[3] = True                                                     # IBB closes above its previous high on day 3
    assert list(R.deep_dip(start, gate, up2, 5).astype(int))[:5] == [0, 1, 1, 0, 0]
    gate2 = gate.copy()
    gate2[2] = False                                                  # XBI falls under its average on day 2
    assert list(R.deep_dip(start, gate2, up, 5).astype(int))[:4] == [0, 1, 0, 0]


def test_legs_blend_and_dips_need_vix(clean):
    s = S.get("bib_blend_v")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    assert np.allclose(fr["w"], np.minimum(1.0, 0.5 * fr["w3"] + 0.5 * fr["w2"]))
    assert set(fr["w"].round(6)) <= {0.0, 0.5, 1.0}
    assert not (fr["ibb_day"] & ~fr["vix_hi"]).any() and not (fr["bib_day"] & ~fr["vix_hi"]).any()
    only_bib = fr[fr["bib_day"] & ~fr["ibb_day"] & ~fr["deep"] & ~fr["hold3"] & ~fr["hold2"]]
    assert (only_bib["w"] == 0.5).all()                               # the BIB one-day dip is the S2+v leg's only


def test_vix_is_fetched_again_once_settled(monkeypatch):
    monkeypatch.setattr(engine.md, "source", lambda: "yahoo")
    t = datetime(2026, 11, 24, 21, 25, tzinfo=timezone.utc)          # 16:25 New York, a trading day
    closing = datetime(2026, 11, 24, 21, 8, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr("time.time", lambda: t.timestamp())
    assert engine._daily_due("^VIX", t, closing)                       # had the 16:08 bar: fetch the settled close
    assert not engine._daily_due("^VIX", t, t.timestamp() - 60)
    assert not engine._daily_due("SPY", t, closing)


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("bib_blend_v")
    assert s is not None and "bib_blend_v" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in R.STATE_COLOR and set(ev["target"]) <= {"BIB"}
    r = BT.run("bib_blend_v")
    assert r["ok"], r.get("error")
    assert r["main"] == "BIB" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
