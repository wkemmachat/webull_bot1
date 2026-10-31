"""QLD regime / 2x Semis: the four states and their targets."""
import math

import numpy as np
import pandas as pd
import pytest

from app import marketdata as md
from app import strategies as S


@pytest.fixture
def qld():
    return S.get("qld_regime")


def test_targets_for_each_state(qld):
    assert qld.target_for("2x") == {"QLD": 0.99}
    assert qld.target_for("0.5x") == {"QLD": 0.25}                 # the rest stays cash (default since 31 Oct 2026)
    assert qld.target_for("1x") == {"QLD": 0.5}
    qld.params = dict(qld.params, cash_symbol="BIL")                 # the old T-bill parking still works
    assert qld.target_for("0.5x") == {"QLD": 0.25, "BIL": 0.74}
    assert qld.target_for("1x") == {"QLD": 0.5, "BIL": 0.49}
    assert qld.target_for("off") == {"GLD": 0.99}


def test_semis_defaults():
    s = S.get("semis_regime")
    assert s.params["signal"] == "SMH" and s.params["trade"] == "USD" and s.params["vol_gate_pct"] == 40


def _series(closes):
    idx = pd.bdate_range(end="2026-10-20", periods=len(closes), tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"o": c, "h": c * 1.001, "l": c * 0.999, "c": c, "v": 1.0})


def test_state_rules(qld, monkeypatch):
    n = 320
    calm = 100 * np.exp(np.linspace(0, 0.5, n))                         # steady rise: above both averages, low vol
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: _series(calm))
    fr = qld.frame(None)
    assert fr["state"].iloc[-1] == "2x"
    # volatility = stdev of 20 daily log returns × √252
    lr = np.diff(np.log(calm))[-20:]
    assert fr["vol"].iloc[-1] == pytest.approx(np.std(lr, ddof=1) * math.sqrt(252))

    crash = np.r_[calm, calm[-1] * np.exp(np.linspace(0, -0.6, 40))]   # falls below the 200-day average
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: _series(crash))
    assert qld.frame(None)["state"].iloc[-1] == "off"

    swings = np.cumsum(np.tile([0.04, -0.035], 12))                   # ±4% days: same trend, high volatility
    jumpy = np.r_[calm, calm[-1] * np.exp(swings)]
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: _series(jumpy))
    last = qld.frame(None).iloc[-1]
    assert last["c"] > last["sma_long"] and last["sma_short"] > last["sma_long"]
    assert last["vol"] >= 0.30 and last["state"] == "0.5x" and last["weight"] == 0.25


def test_unconfirmed_state(qld, monkeypatch):
    # long fall then a sharp recovery: price back above SMA200 while SMA50 is still below it
    down = 200 * np.exp(np.linspace(0, -0.5, 260))
    up = down[-1] * np.exp(np.linspace(0, 0.55, 25))
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: _series(np.r_[down, up]))
    fr = qld.frame(None)
    last = fr.iloc[-1]
    assert last["c"] > last["sma_long"] and last["sma_short"] <= last["sma_long"]
    assert last["state"] == "1x" and last["weight"] == 0.5
