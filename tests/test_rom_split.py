"""ROM · Split 2C (split_mix 67% / 33%): the new trend_gate options of its second leg (ROC trend, credit check, dip trades
after 3 lower closes), weighted legs that park differently, the day's target in the backtest, the health recompute and the
default ("Strategy research and stress tests", round 2 ROM split C, 15 Nov 2026)."""
import json

import numpy as np
import pytest

from app import health, marketdata as md
from app import strategies as S
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


P = default("rom_split_2c")
LEGS = json.loads(P["legs"])
NEW = LEGS[1]["params"]


def leg(params=None):
    return S.TYPES["trend_gate"]({"id": "t_new", "name": "new leg", "params": {**NEW, **(params or {})}})


def mix(params=None):
    return S.TYPES["split_mix"]({"id": "t_rom", "name": "rom mix", "params": {**P, **(params or {})}})


# ---------------------------------------------------------------- the second leg's rules, rebuilt with pandas
def test_roc_credit_and_three_down_dips():
    s = leg()
    fr = s.frame(NOW)
    fr = fr[fr["state"] != ""]
    sg = md.daily_closed("IYW", NOW)
    c = sg["c"].astype(float)
    ref = c.shift(252).reindex(fr.index)
    assert np.allclose(fr["ma"].values, ref.values)
    up = fr["c"] > fr["ma"]
    trend = up & fr["credit"].astype(bool)
    assert ((fr["state"] == "trend") == (trend & (fr["state"] != "dip"))).all()
    assert ((fr["state"] == "volatile") == (up & ~fr["credit"].astype(bool) & (fr["state"] != "dip"))).all()
    # dip trades open only on the third lower close in a row below the trend, and close on a close above SMA5
    cl = c.values
    pos = {d: i for i, d in enumerate(sg.index)}
    on = fr["rsi_on"].astype(bool).values
    for j in range(1, len(fr)):
        if on[j] and not on[j - 1]:
            i = pos[fr.index[j]]
            assert cl[i] < cl[i - 1] < cl[i - 2] < cl[i - 3] and not bool(up.iloc[j])
        if on[j - 1] and not on[j]:
            assert fr["c"].iloc[j] > fr["sma_exit"].iloc[j]
    ibs = fr["ibs_dip"]
    assert (fr["ibs_hit"].astype(bool) == (~up & (ibs < 0.2))).all()
    cols, rows, worst = s.check_table(NOW, 12)
    assert worst == 0 and all(r["ok"] for r in rows)


def test_new_options_are_checked():
    with pytest.raises(ValueError):
        leg({"ma_type": "WMA"})
    with pytest.raises(ValueError):
        leg({"dip_entry": "4DOWN"})
    off = leg({"credit_ma": 0}).frame(NOW)
    assert off["credit"].all() and "LQD" not in leg({"credit_ma": 0}).read_symbols()
    d = leg().describe()
    assert "ROC252 > 0" in d["rule"] and "credit OK" in d["rule"] and "3-lower-closes" in d["rule"]


# ---------------------------------------------------------------- the weighted mix
def test_weights_and_parking_per_leg():
    s = mix()
    assert list(np.round(s.weights(), 2)) == [0.67, 0.33] and not s.equal() and s.share_word() == "67% / 33%"
    fr = s.frame(NOW)
    years = [d.year for d in fr.index.tz_convert("America/New_York")]
    starts = [i for i in range(1, len(fr)) if years[i] != years[i - 1]]
    assert starts
    for i in starts:                                      # on a year's first day the legs are back to 67% / 33%
        w1, w2 = fr["l1_w"].iloc[i], fr["l2_w"].iloc[i]
        assert fr["size"].iloc[i] == pytest.approx(0.67 * w1 + 0.33 * w2, abs=1e-4)
        g2 = 0.0 if w2 > 0 else 0.5 * 0.99                   # leg 2 parks half in GLD; leg 1 parks in cash
        assert fr["gold_w"].iloc[i] == pytest.approx(0.33 * g2, abs=1e-4)
    # the backtest takes the day's target from the frame (the gold share depends on which leg is out)
    for i in starts:
        t = s.target_at(fr.index[i].date())
        assert t.get("ROM", 0) == pytest.approx(fr["size"].iloc[i], abs=1e-4)
        assert t.get("GLD", 0) == pytest.approx(fr["gold_w"].iloc[i], abs=1e-4)


def test_evaluate_and_health():
    s = mix()
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["target"] == s.target_at(s.frame(NOW).index[-1].date())
    tiles = ev["detail"]["tiles"]
    assert tiles[0]["hold"].startswith("67% of the money") and tiles[1]["hold"].startswith("33% of the money")
    keys = [c["k"] for c in ev["checks"]]
    assert any(k.startswith("Leg 2 · ROC252") for k in keys) and any("Credit · LQD ÷ IEF" in k for k in keys)
    assert "67% / 33%" in s.describe()["rule"]
    t = health.indicator_table(s, NOW)
    assert t["max_diff"] == 0 and len(t["rows"]) == 12


def test_default_added_quietly(clean):
    r = S.row("rom_split_2c")
    assert r and r["type"] == "split_mix" and "rom_split_2c" in S.QUIET_DEFAULTS
    st = S.get("rom_split_2c")
    assert set(st.trade_symbols()) == {"ROM", "GLD"} and set(st.read_symbols()) == {"IYW", "ROM", "LQD", "IEF"}
    assert st.legs()[0].params == S.get("rom_vol_ibs").params | {"cash_buffer_pct": st.legs()[0].params["cash_buffer_pct"]}
    from app import backtest
    out = backtest.run("rom_split_2c")
    assert out.get("ok") is not False and "MAX" in out["stats"]
