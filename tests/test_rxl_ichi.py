"""RXL · Ichimoku cloud + calm + S&P check + dips (trend_gate with ma_type ICHI, a market check and dip trades sold above the
previous high): the rule rebuilt with pandas, the settings checks, the health recompute and the new default ("Strategy
research and stress tests", round 1 RXL-A, 15 Nov 2026)."""
import numpy as np
import pandas as pd
import pytest

from app import health, marketdata as md
from app import strategies as S
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


A = default("rxl_ichi_calm")


def make(params=None):
    return S.TYPES["trend_gate"]({"id": "t_rxl", "name": "rxl test", "params": {**A, **(params or {})}})


def test_matches_the_research_rule():
    s = make()
    fr = s.frame(NOW)
    fr = fr[fr["state"] != ""]
    xl = md.daily_closed("XLV", NOW)
    h, l, c = (xl[k].astype(float) for k in ("h", "l", "c"))
    mid = lambda n: (h.rolling(n).max() + l.rolling(n).min()) / 2
    a, b = ((mid(18) + mid(48)) / 2).shift(48), mid(96).shift(48)
    top, bot = np.maximum(a, b), np.minimum(a, b)
    assert np.allclose(fr["ma"].values, top.reindex(fr.index).values)
    on, cloud = False, pd.Series(False, index=c.index)
    for d in c.index:                                   # on above the top, off below the bottom, kept inside
        if np.isnan(top[d]):
            on = False
        elif c[d] > top[d]:
            on = True
        elif c[d] < bot[d]:
            on = False
        cloud[d] = on
    up = cloud.reindex(fr.index)
    assert (fr["up"].astype(bool) == up).all()
    spy = md.daily_closed("SPY", NOW)["c"].astype(float)
    mkt = (spy > spy.rolling(200).mean()).reindex(fr.index)
    calm = fr["vol"] < fr["vol_thr"]
    st = fr["state"]
    assert ((st == "trend") == (up & calm & mkt & (st != "dip"))).all()
    assert ((st == "volatile") == (up & ~(calm & mkt) & (st != "dip"))).all()
    # dip trades: open below the cloud trend on XLV IBS < 0.25; close on a close above the previous high or after 5 days
    pos = {d: i for i, d in enumerate(xl.index)}
    want, on, held = [], False, 0
    for j, d in enumerate(fr.index):                    # the trade replayed from the rule's words
        i = pos[d]
        if on:
            held += 1
            if c.iloc[i] > h.iloc[i - 1] or held >= 5:
                on = False
        if not on and not bool(up.iloc[j]) and fr["sig_ibs"].iloc[j] < 0.25:
            on, held = True, 0
        want.append(on)
    got = fr["rsi_on"].astype(bool).values
    first = next(j for j in range(len(fr)) if got[j] == want[j] and not got[j])   # in step from the first day both are out
    assert (got[first:] == np.array(want[first:])).all()
    assert (fr["rsi1_hit"].astype(bool) == (~up & (fr["rsi"] < 5))).all()
    assert set(fr.loc[st == "dip", "size"]) <= {1.0}


def test_settings_checks_and_texts():
    with pytest.raises(ValueError):
        make({"ichi_kijun": 120})
    with pytest.raises(ValueError):
        make({"dip_exit": "ATR"})
    s = make()
    d = s.describe()
    assert "Ichimoku cloud 18/48/96" in d["rule"] and "SPY > SMA200" in d["rule"] and "prev. high" in d["rule"]
    assert '"Ichimoku Cloud" Conversion Line 18' in d["tv"] and "Lagging Span 49" in d["tv"]
    assert set(s.read_symbols()) == {"XLV", "RXL", "SPY"}
    ev = s.evaluate(NOW)
    keys = [c["k"] for c in ev["checks"]]
    assert keys[0] == "XLV vs Ichimoku cloud" and "Market · SPY vs SMA200" in keys
    ch = s.chart(NOW, "1Y")
    assert [l["name"] for l in ch["charts"][0]["lines"]] == ["Cloud span A", "Cloud span B"]


def test_health_recompute_matches():
    t = health.indicator_table(make(), NOW)
    assert t["max_diff"] == 0 and len(t["rows"]) == 12


def test_default_added_quietly(clean):
    r = S.row("rxl_ichi_calm")
    assert r and r["type"] == "trend_gate" and "rxl_ichi_calm" in S.QUIET_DEFAULTS
    st = S.get("rxl_ichi_calm")
    assert set(st.trade_symbols()) == {"RXL", "GLD"}
    from app import backtest
    out = backtest.run("rxl_ichi_calm")
    assert out.get("ok") is not False and "MAX" in out["stats"]
