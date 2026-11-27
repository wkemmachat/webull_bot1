"""URAA · Uranium dip legs with a Cameco check (S1++) (27 Nov 2026): the legs, the up-close exit, the live evaluation and the
backtest."""
import numpy as np

from app import backtest as BT
from app import strategies as S
from app.strategies import three_leg_dips as T
from conftest import NOW


def test_legs_size_and_exit(clean):
    s = S.get("uraa_s1pp")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    assert set(fr["w"].round(6)) <= {0.0, 0.5, 1.0}
    assert (fr.loc[fr["leg_a"] | fr["leg_b"], "w"] == 1.0).all()
    assert (fr.loc[fr["leg_c"] & ~fr["leg_a"] & ~fr["leg_b"], "w"] == 0.5).all()
    assert not (fr["start_a"] & ~(fr["c_rsi2"] < 30)).any() and not (fr["start_b"] & ~(fr["c_rsi2"] < 30)).any()
    w, up, st = fr["w"].values, fr["up"].values.astype(bool), (fr["start_a"] | fr["start_b"] | fr["start_c"]).values
    for i in range(1, len(fr)):
        if w[i - 1] > 0 and up[i] and not st[i]:
            assert w[i] == 0                                          # an up close ends every open leg


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("uraa_s1pp")
    assert s is not None and "uraa_s1pp" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in T.STATE_COLOR and set(ev["target"]) <= {"URAA"}
    r = BT.run("uraa_s1pp")
    assert r["ok"], r.get("error")
    assert r["main"] == "URAA" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
