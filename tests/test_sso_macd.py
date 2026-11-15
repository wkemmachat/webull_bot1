"""SSO · Slow MACD + calm + dips (trend_gate with ma_type XEMA, dip_entry IBS and one-day RSI dips): the rule rebuilt with
pandas, the settings checks, the health recompute and the new default ("Strategy research and stress tests", round 1
SSO-A, 15 Nov 2026)."""
import numpy as np
import pandas as pd
import pytest

from app import health, marketdata as md
from app import strategies as S
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


A = default("sso_macd_calm")


def make(params=None):
    return S.TYPES["trend_gate"]({"id": "t_sso", "name": "sso test", "params": {**A, **(params or {})}})


def ema_tv(c, n):
    """EMA seeded with the SMA of the first n closes, like TradingView."""
    v = [np.nan] * (n - 1) + [c.iloc[:n].mean()]
    a = 2 / (n + 1)
    for x in c.iloc[n:]:
        v.append(a * x + (1 - a) * v[-1])
    return pd.Series(v, index=c.index)


def test_matches_the_research_rule():
    s = make()
    fr = s.frame(NOW)
    fr = fr[fr["state"] != ""]
    sp = md.daily_closed("SPY", NOW)
    c = sp["c"].astype(float)
    fast, slow = ema_tv(c, 60).reindex(fr.index), ema_tv(c, 130).reindex(fr.index)
    assert np.allclose(fr["fast"].values, fast.values) and np.allclose(fr["ma"].values, slow.values)
    up = fast > slow
    calm = fr["vol"] < fr["vol_thr"]
    st = fr["state"]
    assert ((st == "trend") == (up & calm & (st != "dip"))).all()
    assert ((st == "volatile") == (up & ~calm & (st != "dip"))).all()
    # dip trades: open below the trend on SPY IBS < 0.20, close on a close above SMA5; one-day dips on RSI(2) < 10
    on = fr["rsi_on"].astype(bool).values
    for j in range(1, len(fr)):
        if on[j] and not on[j - 1]:
            assert not bool(up.iloc[j]) and fr["sig_ibs"].iloc[j] < 0.2
        if on[j - 1] and not on[j]:
            assert fr["c"].iloc[j] > fr["sma_exit"].iloc[j]
    assert (fr["rsi1_hit"].astype(bool) == (~up & (fr["rsi"] < 10))).all()
    assert ((st == "dip") == (fr["rsi_on"].astype(bool) | fr["rsi1_hit"].astype(bool))).all()
    assert set(fr.loc[st == "dip", "size"]) <= {1.0}


def test_settings_checks_and_texts():
    with pytest.raises(ValueError):
        make({"fast_days": 130})
    with pytest.raises(ValueError):
        make({"dip_entry": "MACD"})
    s = make()
    d = s.describe()
    assert "SPY EMA60 > EMA130" in d["rule"] and "IBS < 0.2" in d["rule"] and "RSI(2) < 10" in d["rule"]
    assert '"MACD" fast 60 slow 130' in d["tv"]
    ev = s.evaluate(NOW)
    keys = [c["k"] for c in ev["checks"]]
    assert keys[0] == "SPY EMA60 vs EMA130" and any(k.startswith("IBS · SPY") for k in keys)
    assert any(k.startswith("RSI(2) · one-day dip") for k in keys)
    ch = s.chart(NOW, "1Y")
    assert [l["name"] for l in ch["charts"][0]["lines"]][:2] == ["EMA 130", "EMA 60"]


def test_health_recompute_matches():
    t = health.indicator_table(make(), NOW)
    assert t["cols"][1] == "EMA130 · bot" and t["max_diff"] == 0 and len(t["rows"]) == 12


def test_default_added_quietly(clean):
    r = S.row("sso_macd_calm")
    assert r and r["type"] == "trend_gate" and "sso_macd_calm" in S.QUIET_DEFAULTS
    st = S.get("sso_macd_calm")
    assert st.trade_symbols() == ["SSO"] and st.read_symbols() == ["SPY", "SSO"]
    from app import backtest
    out = backtest.run("sso_macd_calm")
    assert out.get("ok") is not False and "MAX" in out["stats"]
