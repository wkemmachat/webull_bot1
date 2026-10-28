"""20 years: a 2x ETF's prices before it existed are built from its index, chained back from its first real close."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import backtest as B, marketdata as md


def _bars(start, n, ret, first=100.0):
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    c = first * np.cumprod(1 + np.asarray(ret))
    return pd.DataFrame({"o": c, "h": c * 1.01, "l": c * 0.99, "c": c, "v": 0.0}, index=idx)


def test_lever_back_doubles_the_index_minus_costs():
    u = _bars("2006-01-03", 300, [0.01] * 300)
    real = u.iloc[250:].copy() * 3                                  # the ETF starts at day 250, at another price level
    out = B.lever_back(real, u)
    assert out.index[0] == u.index[0] and out["c"].iloc[250] == pytest.approx(real["c"].iloc[0])
    r = out["c"].iloc[100] / out["c"].iloc[99] - 1
    assert r == pytest.approx(2 * 0.01 - (B.SYNTH_FEE_Y + B._tbill(2006)) / 252, rel=1e-9)
    assert (out["h"] >= out[["o", "c"]].max(axis=1) - 1e-9).all() and (out["l"] <= out[["o", "c"]].min(axis=1) + 1e-9).all()
    assert out.index.is_monotonic_increasing and not out.index.duplicated().any()


def test_lever_back_needs_the_index_on_the_first_real_day():
    u = _bars("2006-01-03", 100, [0.0] * 100)
    real = _bars("2010-01-04", 10, [0.0] * 10)
    assert B.lever_back(real, u) is real


def test_tbill_back_grows_at_the_rate():
    cal = _bars("2006-01-03", 300, [0.0] * 300)
    real = cal.iloc[260:].copy()
    out = B.tbill_back(real, cal)
    assert out.index[0] == cal.index[0]
    assert out["c"].iloc[1] / out["c"].iloc[0] - 1 == pytest.approx(B._tbill(2006) / 252)


def test_early_bars_are_per_thread_and_only_before_the_first_stored_bar(clean):
    import threading
    early = _bars("2000-01-03", 5, [0.0] * 5)
    md.set_early({"QLD": early})
    try:
        df = md.daily_closed("QLD")
        assert df.index[0] == early.index[0]
        seen = {}
        t = threading.Thread(target=lambda: seen.setdefault("first", md.daily_closed("QLD").index[0]))
        t.start(); t.join()
        assert seen["first"] > early.index[-1]                     # another thread (the bot) does not see them
    finally:
        md.set_early(None)
