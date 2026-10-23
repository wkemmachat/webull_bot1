"""Indicators: the Pine-exact versions in app.indicators against the separately written references in app.health."""
import math

import numpy as np
import pandas as pd
import pytest

from app import bars, health, indicators as I


def ohlc(n=600, seed=1):
    rng = np.random.default_rng(seed)
    c = 2000 * np.exp(np.cumsum(rng.normal(0, 0.006, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    return h, l, c


def test_rma_is_wilder_average():
    x = np.arange(1, 21, dtype=float)
    r = I.rma(x, 5)
    assert np.isnan(r[3]) and r[4] == pytest.approx(3.0)          # seeded with the simple average of the first 5
    assert r[5] == pytest.approx((3.0 * 4 + 6) / 5)


@pytest.mark.parametrize("period,mult", [(30, 2.5), (10, 3.0)])
def test_supertrend_matches_reference(period, mult):
    h, l, c = ohlc()
    a = I.supertrend(h, l, c, period, mult)
    ref_line, ref_up = health.ref_supertrend(list(h), list(l), list(c), period, mult)
    for i in range(period + 5, len(c)):
        assert a["line"][i] == pytest.approx(ref_line[i], rel=1e-9)
        assert bool(a["up"][i]) == ref_up[i]


def test_adx_matches_reference():
    h, l, c = ohlc(seed=2)
    a = I.dmi(h, l, c, 14, 14)["adx"]
    ref = health.ref_adx(list(h), list(l), list(c), 14)
    checked = 0
    for i in range(60, len(c)):
        if not math.isnan(ref[i]):
            assert a[i] == pytest.approx(ref[i], rel=1e-6)
            checked += 1
    assert checked > 400
    assert np.nanmax(a) <= 100 and np.nanmin(a) >= 0


def test_donchian_excludes_current_bar():
    h = np.array([1, 5, 3, 2, 4, 9, 1], dtype=float)
    hp = I.highest_prev(h, 3)
    assert np.isnan(hp[2]) and hp[3] == 5 and hp[5] == 4 and hp[6] == 9
    lp = I.lowest_prev(h, 2)
    assert lp[2] == 1 and lp[3] == 3


def test_4h_buckets_follow_the_18_00_new_york_session():
    idx = pd.date_range("2026-10-18 22:00", "2026-10-21 20:00", freq="1h", tz="UTC")      # Sun 18:00 NY → Wed
    df = pd.DataFrame({"o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 1.0}, index=idx)
    out = bars.to_4h(df)
    hours = set(out.index.tz_convert("America/New_York").hour)
    assert hours <= {18, 22, 2, 6, 10, 14}
    assert (out["n"] <= 4).all()
    # the 14:00 bucket ends at the 17:00 close, not 18:00
    b = out[out.index.tz_convert("America/New_York").hour == 14].iloc[0]
    assert b["end"].tz_convert("America/New_York").hour == 17
