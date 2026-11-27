"""AIBU · Breakout + calm + fast stop + dips (S2++) (27 Nov 2026): the fast stop, the model, the live evaluation and the backtest."""
import numpy as np
import pandas as pd

from app import backtest as BT
from app import strategies as S
from app.strategies import breakout_calm_dip as B
from conftest import NOW


def test_fast_stop_keeps_the_trend_out_for_the_days(clean):
    s = S.get("aibu_s2pp")
    fr = s.frame(NOW)
    fr = fr[fr["ok"]]
    hits = np.where(fr["chg"].values < -13.0)[0]
    for i in hits:
        assert fr["stop"].iloc[i : i + 7].all()                       # the trigger day and the next 6 decisions
        assert (fr["w_trend"].iloc[i : i + 7] == 0).all()
    assert (fr.loc[fr["dip"], "w"] == 1.0).all()                      # dips still buy, stop or not
    off = dict(s.params, stop_pct=0.0)
    fr0 = B.signals(fr[["t_o", "t_h", "t_l", "t_c"]].rename(columns=lambda c: c[2:]), *_data(s), off)
    assert not fr0["stop"].any()                                      # 0 = no stop


def _data(s):
    from app import marketdata as md
    from app.strategies.hk_crash import HkCrashStrategy
    data = {}
    for sym in s.read_symbols():
        df = md.daily_closed(sym, NOW)
        data[sym] = HkCrashStrategy.dividend_adjusted(sym, df[~df.index.duplicated(keep="last")])
    return (data,)


def test_model_scales_the_mix_and_joins_the_real_first_close():
    idx = pd.bdate_range("2024-01-01", periods=6, tz="UTC")
    a = pd.DataFrame({"o": [100, 101, 102, 103, 104, 105.0], "h": 106.0, "l": 99.0, "c": [100, 101, 102, 103, 104, 105.0]}, index=idx)
    real = pd.DataFrame({"o": [50.0, 51], "h": 52.0, "l": 49.0, "c": [50.0, 51], "v": 1.0}, index=idx[4:])
    m = B.model_beta(real, {"A": a}, {"A": 1.0}, idx, 2.0, 0.0)
    assert m["c"].loc[idx[4]] == 50.0 and m["c"].loc[idx[5]] == 51.0  # real prices from the listing day
    r = m["c"].loc[idx[2]] / m["c"].loc[idx[1]] - 1
    assert abs(r - 2 * (102 / 101 - 1)) < 1e-12                      # 2 × the mix's daily move before it


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("aibu_s2pp")
    assert s is not None and "aibu_s2pp" in S.QUIET_DEFAULTS
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in B.STATE_COLOR and set(ev["target"]) <= {"AIBU"}
    r = BT.run("aibu_s2pp")
    assert r["ok"], r.get("error")
    assert r["main"] == "AIBU" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["signal", "dip"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6
