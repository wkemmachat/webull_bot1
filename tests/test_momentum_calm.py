"""RAM · Momentum + calm + one-day dips (26 Nov 2026): the hold rule (momentum of every symbol, the fast check, the calm gate), the
one-day dips, the model of RAM before it listed, the live evaluation and the backtest."""
import numpy as np
import pandas as pd
import pytest

from app import backtest as BT
from app import strategies as S
from app.strategies import momentum_calm as M
from conftest import NOW

P = M.MomentumCalmStrategy.default_params()


def _bars(c, idx, ibs=0.5):
    c = np.asarray(c, dtype=float)
    return pd.DataFrame({"o": c, "h": c * 1.01, "l": c * 1.01 - c * 0.02, "c": c * (0.99 + 0.02 * ibs)}, index=idx)


def test_hold_needs_every_part_and_dips_fill_the_rest():
    n = 700
    idx = pd.bdate_range("2023-01-02", periods=n, tz="UTC")
    rng = np.random.default_rng(3)
    up = 100 * np.cumprod(1 + 0.002 + rng.normal(0, 0.01, n))
    data = {"MU": _bars(up, idx), "SMH": _bars(up, idx)}
    ram = _bars(up, idx)
    fr = M.signals(ram, data, P)
    r = fr.iloc[-1]
    assert r["mom"] and r["fast_ok"]
    assert r["state"] == ("hold" if r["calm"] else "jumpy")
    down = up[::-1].copy()
    data2 = {"MU": _bars(down, idx), "SMH": _bars(up, idx)}
    weak = _bars(up, idx, ibs=0.02)                                   # closes near the low every day: IBS ≈ 0.04
    fr2 = M.signals(weak, data2, P)
    assert not fr2["mom"].iloc[-1] and fr2["state"].iloc[-1] == "dip" and fr2["w"].iloc[-1] == 1.0
    fr3 = M.signals(weak, data2, dict(P, dip_ibs_max=0.0))
    assert fr3["state"].iloc[-1] == "out" and fr3["w"].iloc[-1] == 0.0


def test_model_joins_the_first_real_close():
    idx = pd.bdate_range("2026-05-01", periods=40, tz="UTC")
    stocks = {s: _bars(np.linspace(100, 120, 40), idx) for s in ("MU", "STX", "WDC")}
    real = _bars([3.7, 3.8, 3.6], idx[-3:])
    m = M.model_2x(real, stocks, M.parse_weights("MU:70,STX:15,WDC:15"), idx, 0.185)
    assert m.loc[idx[-3], "c"] == pytest.approx(real["c"].iloc[0]) and m.index[0] == idx[1]
    assert M.parse_weights("MU:70,STX:15,WDC:15") == pytest.approx({"MU": 0.7, "STX": 0.15, "WDC": 0.15})


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("ram_mom_calm")
    assert s is not None and "ram_mom_calm" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in M.STATE_COLOR and set(ev["target"]) <= {"RAM"}
    r = BT.run("ram_mom_calm")
    assert r["ok"], r.get("error")
    assert r["main"] == "RAM" and r["stats"]
    assert [c["id"] for c in s.chart(NOW, "8M")["charts"]] == ["trade", "sig_MU", "sig_SMH"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst == 0
