"""QPUX · Dip + trend + RSI, Bitcoin check (Safe) (26 Nov 2026): the basket, the three legs and their weights, the Bitcoin check
(the previous UTC close), the model of QPUX before it listed, the live evaluation and the backtest."""
import numpy as np
import pandas as pd
import pytest

from app import backtest as BT, db
from app import strategies as S
from app.strategies import quantum_mix as Q
from conftest import NOW

P = Q.QuantumMixStrategy.default_params()


def _bars(c, idx):
    c = np.asarray(c, dtype=float)
    return pd.DataFrame({"o": c, "h": c * 1.01, "l": c * 0.99, "c": c}, index=idx)


def test_basket_averages_the_members_from_their_start():
    idx = pd.bdate_range("2022-01-03", periods=4, tz="UTC")
    a = _bars([10, 11, 12.1, 12.1], idx)                     # +10%, +10%, 0%
    b = _bars([20, 20, 18, 18], idx)                         # 0%, −10%, 0%
    bk = Q.basket_bars({"A": a, "B": b}, {"A": None, "B": idx[1]}, idx)
    assert bk["rc"].iloc[1] == pytest.approx(0.10)           # B counts from the day after its start
    assert bk["rc"].iloc[2] == pytest.approx(0.0)            # (+10% − 10%) / 2
    assert list(bk["n"]) == [0, 1, 2, 2]


def test_weights_add_up_and_bitcoin_blocks_every_leg_in_safe():
    n = 260
    idx = pd.bdate_range("2025-01-01", periods=n, tz="UTC")
    up = np.linspace(10, 20, n)
    q = _bars(up, idx)
    bk = pd.DataFrame({"o": up, "h": up * 1.02, "l": up * 0.98, "c": up * 0.981}, index=idx)   # weak closes: IBS ≈ 0.03
    mkt = _bars(np.linspace(300, 400, n), idx)
    bidx = pd.date_range("2024-08-01", periods=520, freq="D", tz="UTC")
    btc_up = _bars(np.linspace(50000, 90000, len(bidx)), bidx)
    fr = Q.signals(q, bk, mkt, btc_up, P)
    r = fr.iloc[-1]
    assert r["btc_ok"] and r["dip"] == 1 and r["trend"] > 0
    assert r["w"] == pytest.approx(min(1.0, 0.4 + 0.5 * r["trend"] + 0.25 * r["rsi_in"]))
    btc_down = _bars(np.linspace(90000, 50000, len(bidx)), bidx)
    fr2 = Q.signals(q, bk, mkt, btc_down, P)
    assert fr2["w"].iloc[-1] == 0 and fr2["state"].iloc[-1] == "btc_off"          # Safe: every leg needs Bitcoin
    fr3 = Q.signals(q, bk, mkt, btc_down, dict(P, btc_all=False))
    assert fr3["dip"].iloc[-1] == 1 and fr3["trend"].iloc[-1] == 0                 # the round-3 pick: only the trend leg needs it


def test_bitcoin_check_uses_the_previous_days_close():
    bidx = pd.date_range("2026-01-01", periods=130, freq="D", tz="UTC")
    c = np.full(130, 100.0)
    c[-1] = 1000.0                                           # today's (unfinished) Bitcoin day jumps: not seen yet
    btc = _bars(c, bidx)
    idx = pd.DatetimeIndex([bidx[-1]])
    q = _bars([10], idx)
    fr = Q.signals(q, _bars([10], idx), _bars([10], idx), btc, P)
    assert fr["btc"].iloc[-1] == pytest.approx(100.0) and not fr["btc_ok"].iloc[-1]


def test_model_joins_the_first_real_close():
    idx = pd.bdate_range("2025-07-01", periods=30, tz="UTC")
    bk = pd.DataFrame({"o": 100.0, "h": 101.0, "l": 99.0, "c": np.linspace(100, 110, 30), "n": 4}, index=idx)
    real = _bars([5.0, 5.2, 5.1], idx[-3:])
    m = Q.model_qpux(real, bk, 0.213)
    assert m.index[0] == idx[0] and m.loc[idx[-3], "c"] == pytest.approx(5.0)
    assert (m.loc[idx[-3]:, "c"].values == real["c"].values).all()


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("qpux_safe")
    assert s is not None and "qpux_safe" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in Q.STATE_COLOR and set(ev["target"]) <= {"QPUX"}
    r = BT.run("qpux_safe")
    assert r["ok"], r.get("error")
    assert r["main"] == "QPUX" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["trade", "market", "btc"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
