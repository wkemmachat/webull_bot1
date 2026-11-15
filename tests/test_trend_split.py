"""USD · Trend split (type trend_split): the bot's rule against an independent copy of round 3 USD split C ("Strategy research
and stress tests", 15 Nov 2026), the yearly sub-account sizing, the health recompute, and the new default."""
import numpy as np
import pandas as pd
import pytest

from app import db, health, marketdata as md
from app import strategies as S
from app.strategies.trend_split import split_sizes
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


C = default("usd_trend_split")


def make(params=None):
    return S.TYPES["trend_split"]({"id": "t_split", "name": "test split", "params": {**C, **(params or {})}})


# ---------------------------------------------------------------- the research rule, written independently (pandas)
def research_legs(sm, lqd, ief, legs, q_days=20, lb=252, cma=100, th=0.3):
    """Number of legs in after each close, on SMH's days where LQD and IEF also traded."""
    idx = sm.index.intersection(lqd.index).intersection(ief.index)
    c = sm.c
    v = c.pct_change().rolling(q_days).std()
    ratio = (lqd.c / ief.c).dropna()
    credit = (ratio > ratio.rolling(cma).mean()).reindex(idx).fillna(False)
    ibs = ((sm.c - sm.l) / (sm.h - sm.l)).round(4).fillna(0.5).reindex(idx)
    n_in = pd.Series(0, index=idx)
    ready = pd.Series(True, index=idx)
    for kind, n, q in legs:
        if kind == "SMA":
            ref = c.rolling(n).mean()
        elif kind == "EMA":
            ref = c.ewm(span=n, adjust=False).mean()
            ref.iloc[:n - 1] = np.nan                       # seeded like TradingView: first value = SMA(n)
            e = c.iloc[:n].mean()
            vals = [np.nan] * (n - 1) + [e]
            a = 2 / (n + 1)
            for x in c.iloc[n:]:
                e = a * x + (1 - a) * e
                vals.append(e)
            ref = pd.Series(vals, index=c.index)
        else:
            ref = c.shift(n)
        up = (c > ref).reindex(idx)
        thr = v.rolling(lb).quantile(q / 100)
        calm = (v < thr).reindex(idx)
        ready &= ref.reindex(idx).notna() & thr.reindex(idx).notna()
        inn = (up & calm & credit) | (~up & (ibs < th))
        n_in += inn.astype(int)
    ready &= (ratio.rolling(cma).mean().reindex(idx).notna())
    return n_in[ready]


def test_matches_the_research_rule():
    s = make()
    fr = s.frame(NOW)
    fr = fr[fr["state"] != ""]
    sm, lqd, ief = (md.daily_closed(x, NOW) for x in ("SMH", "LQD", "IEF"))
    want = research_legs(sm, lqd, ief, [("SMA", 150, 90), ("ROC", 126, 90), ("EMA", 150, 80)])
    common = fr.index.intersection(want.index)
    assert len(common) > 150
    got = fr.loc[common, "legs_in"].astype(int)
    assert (got.values == want.loc[common].values).all()
    assert set(np.unique(got.values)) - {0, 1, 2, 3} == set()
    assert fr["legs_in"].max() >= 1 and fr["size"].between(0, 1).all()


def test_yearly_sizes_drift_and_reset():
    ins = np.array([[1, 0, 0], [1, 0, 0], [1, 1, 0], [1, 1, 0]], dtype=bool)
    rets = np.array([np.nan, 0.10, 0.0, 0.0])
    years = np.array([2025, 2025, 2025, 2026])
    y = split_sizes(ins, rets, years, yearly=True)
    assert y[0] == pytest.approx(1 / 3)
    # leg 1 grew 10% on day 2: 0.3667 of 1.0333
    assert y[1] == pytest.approx((1 / 3 * 1.1) / (1 / 3 * 1.1 + 2 / 3))
    assert y[2] == pytest.approx((1 / 3 * 1.1 + 1 / 3) / (1 / 3 * 1.1 + 2 / 3))
    assert y[3] == pytest.approx(2 / 3)                                     # a new year: back to a third each
    d = split_sizes(ins, rets, years, yearly=False)
    assert list(d) == pytest.approx([1 / 3, 1 / 3, 2 / 3, 2 / 3])


def test_evaluate_target_and_checks():
    s = make()
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("trend", "dip", "volatile", "out")
    size = ev["detail"]["size"]
    if size > 0:
        assert ev["target"] == {"USD": pytest.approx(size * 0.99, abs=1e-4)} and ev["label"].startswith("IN")
    else:
        assert ev["target"] == {} and ev["label"].startswith("OUT")
    keys = [c["k"] for c in ev["checks"]]
    assert keys[0].startswith("Leg 1 · SMA150") and keys[1].startswith("Leg 2 · ROC126") and keys[2].startswith("Leg 3 · EMA150")
    assert any(k.startswith("Credit · LQD ÷ IEF") for k in keys)
    assert all(h["kind"] in ("BUY", "SELL") for h in ev["history"])
    assert "credit" in s.describe()["rule"] and len(s.describe()["rules"]) >= 6
    ch = s.chart(NOW, "1Y")
    assert ch["charts"][0]["candles"] and any(p["id"] == "credit" for p in ch["charts"][0]["panes"])


def test_no_credit_and_daily_options():
    a = make({"credit_ma": 0}).frame(NOW)
    assert a["credit"].all()
    b = make({"rebalance_legs": "daily"}).frame(NOW)
    b = b[b["state"] != ""]
    assert np.allclose(b["size"].values, np.round(b["legs_in"].values / 3, 4))
    with pytest.raises(ValueError):
        make({"leg1_kind": "WMA"})


def test_health_recompute_matches():
    s = make()
    cols, rows, worst = s.check_table(NOW, 12)
    assert cols[0] == "Close" and len(rows) == 12 and worst == 0 and all(r["ok"] for r in rows)


def test_default_added_quietly(clean):
    r = S.row("usd_trend_split")
    assert r and r["type"] == "trend_split"
    assert "usd_trend_split" in S.QUIET_DEFAULTS
    st = S.get("usd_trend_split")
    assert st.trade_symbols() == ["USD"] and set(st.read_symbols()) == {"SMH", "USD", "LQD", "IEF"}
    from app import backtest
    out = backtest.run("usd_trend_split")
    assert out.get("ok") is not False and "MAX" in out["stats"]
