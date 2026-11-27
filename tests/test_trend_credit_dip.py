"""TSXU · Trend + calm + credit + dips (2+) (27 Nov 2026): the hold, dip and storm sizes, the live evaluation and the backtest."""
import numpy as np
import pandas as pd
import pytest

from app import backtest as BT
from app import strategies as S
from app.strategies import trend_credit_dip as T
from conftest import NOW

P = T.TrendCreditDipStrategy.default_params()


def _bars(c, h=None, l=None):
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    c = np.asarray(c, float)
    h = c * 1.01 if h is None else np.asarray(h, float)
    l = c * 0.99 if l is None else np.asarray(l, float)
    return pd.DataFrame({"o": c, "h": h, "l": l, "c": c}, index=idx)


def test_hold_dip_and_storm_sizes():
    n = 400
    p = dict(P, vol_lookback=60, ema_days=50, credit_ma=20)
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(0.003 + rng.normal(0, 0.01, n)))      # steady rise: trend on
    lq = 100 + np.arange(n) * 0.01                                    # LQD rising vs IEF flat: credit healthy
    data = {"SMH": _bars(c), "LQD": _bars(lq), "IEF": _bars(np.full(n, 100.0))}
    fr = T.signals(data["SMH"], data, p)
    ok = fr[fr["ok"]]
    assert (ok["w"][ok["trend"] & ok["calm"] & ok["credit"]] == 1.0).all()
    assert set(ok["state"]) <= set(T.STATE_COLOR)
    # credit weak everywhere: no holds; a close at the low is a one-day dip
    data["LQD"] = _bars(100 - np.arange(n) * 0.01)
    h, l = c * 1.01, c * 0.99
    l[-1] = c[-1]                                                     # close at the low → IBS 0
    smh = _bars(c, h, l)
    fr2 = T.signals(smh, {**data, "SMH": smh}, p)
    assert fr2["state"].iloc[-1] in ("dip", "storm_dip") and not (fr2["state"] == "hold").any()
    assert fr2["w"].iloc[-1] == (0.75 if fr2["storm"].iloc[-1] else 1.0)
    assert (fr2.loc[fr2["ok"] & (fr2["ibs"] >= 0.25), "w"] == 0).all()


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("tsxu_2plus")
    assert s is not None and "tsxu_2plus" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in T.STATE_COLOR and set(ev["target"]) <= {"TSXU"}
    r = BT.run("tsxu_2plus")
    assert r["ok"], r.get("error")
    assert r["main"] == "TSXU" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "trade"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
