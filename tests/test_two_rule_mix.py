"""UWM · Trend + credit + calm dips (A3 + R3) (27 Nov 2026): each rule's hold and dip trades, the half-and-half weight, the live
evaluation and the backtest."""
import numpy as np
import pandas as pd
import pytest

from app import backtest as BT
from app import strategies as S
from app.strategies import two_rule_mix as T
from conftest import NOW

P = T.TwoRuleMixStrategy.default_params()


def test_dip_trade_exits_above_the_previous_high_or_after_the_days():
    hold = np.zeros(8, dtype=bool)
    ibs = np.array([0.5, 0.1, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    calm = np.ones(8, dtype=bool)
    close = np.array([10, 9, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6])
    high = np.array([10.2, 9.5, 9.6, 9.7, 9.8, 9.9, 10.0, 10.1])
    w, dip = T.rule_weights(hold, 0.99, ibs, calm, close, high, 0.15, 5)
    assert list(w) == [0, 1, 1, 1, 1, 1, 0, 0]                      # bought day 1, sold after 5 days (no close above a high)
    close2 = close.copy()
    close2[3] = 9.7                                                   # day 3 closes above day 2's high (9.6)
    w2, _ = T.rule_weights(hold, 0.99, ibs, calm, close2, high, 0.15, 5)
    assert list(w2[:5]) == [0, 1, 1, 0, 0]
    hold2 = hold.copy()
    hold2[2:] = True                                                  # the hold starts: the dip ends, the hold size takes over
    w3, d3 = T.rule_weights(hold2, 0.75, ibs, calm, close, high, 0.15, 5)
    assert list(w3[:4]) == [0, 1, 0.75, 0.75] and not d3[2:].any()
    w4, _ = T.rule_weights(hold, 0.99, ibs, ~calm, close, high, 0.15, 5)
    assert not w4.any()                                               # no dips when not calm


def test_half_and_half_weight(clean):
    s = S.get("uwm_a3_r3")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    assert np.allclose(fr["w"], np.minimum(1.0, 0.5 * fr["wa"] + 0.5 * fr["wr"]))
    both = fr[fr["hold_a"] & fr["hold_r"]]
    if len(both):
        assert both["w"].iloc[0] == pytest.approx(0.5 * 0.99 + 0.5 * 0.75)


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("uwm_a3_r3")
    assert s is not None and "uwm_a3_r3" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in T.STATE_COLOR and set(ev["target"]) <= {"UWM"}
    r = BT.run("uwm_a3_r3")
    assert r["ok"], r.get("error")
    assert r["main"] == "UWM" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"] and all(c["open"] is not None for c in ch["charts"][0]["candles"])
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
