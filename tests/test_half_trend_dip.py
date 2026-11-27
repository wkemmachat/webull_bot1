"""CHAU · Half trend + half dip, yuan filter (S4) (27 Nov 2026): the dip trade, the yuan timing, the halves, the live evaluation
and the backtest."""
import numpy as np
import pandas as pd

from app import backtest as BT
from app import strategies as S
from app.strategies import half_trend_dip as H
from conftest import NOW


def test_dip_trade_ends_above_exit_ibs_or_after_the_closes():
    ibs = np.array([0.5, 0.1, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    start = ibs < 0.2
    assert list(H.dip_weights(start, ibs, 0.8, 5).astype(int)) == [0, 1, 1, 1, 1, 1, 0, 0]   # opened at close 1, ended at close 6 (5 closes later)
    ibs2 = ibs.copy()
    ibs2[3] = 0.9
    assert list(H.dip_weights(ibs2 < 0.2, ibs2, 0.8, 5).astype(int))[:5] == [0, 1, 1, 0, 0]  # IBS > 0.8 ends it
    ibs3 = np.array([0.5, 0.1, 0.5, 0.5, 0.5, 0.5, 0.1, 0.5])
    w3 = H.dip_weights(ibs3 < 0.2, ibs3, 0.8, 5)
    assert w3[6] and w3[7]                                            # a new dip may open at the close that ends one


def test_yuan_uses_that_days_close_or_the_day_before():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"]))
    idx = pd.to_datetime(["2026-01-06", "2026-01-08"])
    assert list(H.as_of(s, idx, 0)) == [2.0, 3.0]
    assert list(H.as_of(s, idx, 1)) == [1.0, 3.0]


def test_halves_add_up_and_need_the_yuan(clean):
    s = S.get("chau_s4")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    assert np.allclose(fr["w"], np.minimum(1.0, fr["w_trend"] + fr["w_dip"]))
    assert (fr.loc[~fr["yuan"], "w"] == 0).all()
    assert set(fr["w"].round(6)) <= {0.0, 0.5, 1.0}
    assert set(fr["state"]) <= set(H.STATE_COLOR)


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("chau_s4")
    assert s is not None and "chau_s4" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in H.STATE_COLOR and set(ev["target"]) <= {"CHAU"}
    r = BT.run("chau_s4")
    assert r["ok"], r.get("error")
    assert r["main"] == "CHAU" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst == 0
