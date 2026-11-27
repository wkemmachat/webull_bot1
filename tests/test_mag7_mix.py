"""MAGX · Mag 7 trend + RSI2 dips (half S1+, half S2++) (27 Nov 2026): the quarterly basket, the sticky trend size, the halves,
the live evaluation and the backtest."""
import numpy as np
import pandas as pd

from app import backtest as BT
from app import strategies as S
from app.strategies import mag7_mix as M
from conftest import NOW


def _bars(c, start="2024-01-02"):
    idx = pd.bdate_range(start, periods=len(c), tz="UTC")
    c = np.asarray(c, float)
    return pd.DataFrame({"o": c, "h": c, "l": c, "c": c}, index=idx)


def test_quarterly_basket_drifts_inside_a_quarter_and_resets_at_its_start():
    n = 150                                                           # Dec 2023 – Jun 2024: members join at Q1 2024
    a = _bars(100 * 1.01 ** np.arange(n), "2023-12-01")              # A rises 1% a day
    b = _bars(np.full(n, 100.0), "2023-12-01")                       # B flat
    bk = M.quarterly_basket({"A": a, "B": b}, a.index)
    r = bk["rc"].values
    q1 = np.where(a.index.year == 2024)[0][0]
    q2 = np.where(a.index.month == 4)[0][0]
    assert np.isnan(r[:q1]).all() and (bk["n"].iloc[:q1] == 0).all()   # nothing held before the first quarter start
    assert abs(r[q1] - 0.005) < 1e-9 and r[q1] < r[q2 - 1] < 0.01        # equal at Q1's start, A's share grows inside it
    assert abs(r[q2] - 0.005) < 1e-9                                  # back to half A / half B on the first day of Q2
    assert (bk["n"].iloc[q1:] == 2).all()


def test_sticky_size_changes_only_on_big_moves():
    t = np.array([0, 0.6, 0.7, 0.75, 0.85, 0.9, 0.0, 0.5])
    assert list(M.sticky(t, 0.2)) == [0, 0.6, 0.6, 0.6, 0.85, 0.85, 0.0, 0.5]


def test_halves_and_states(clean):
    s = S.get("magx_s1p_s2pp")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    assert np.allclose(fr["w"], np.minimum(1.0, 0.5 * fr["w1"] + 0.5 * fr["w2"]))
    assert (fr.loc[fr["state"] == "out", "w"] == 0).all()
    assert (fr.loc[fr["state"] == "day", "w"] == 0.5).all()
    assert set(fr["state"]) <= set(M.STATE_COLOR)


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("magx_s1p_s2pp")
    assert s is not None and "magx_s1p_s2pp" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in M.STATE_COLOR and set(ev["target"]) <= {"MAGX"}
    r = BT.run("magx_s1p_s2pp")
    assert r["ok"], r.get("error")
    assert r["main"] == "MAGX" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
