"""QLD Trend + bear-dip + Vol: the bot's rule against the research code (ETF Strategy Lab v3, code/v3_tbdvol.py run())."""
import numpy as np
import pandas as pd
import pytest

from app import db, health
from app import strategies as S
from app.strategies.trend_dip import positions, vol_gate
from conftest import NOW
from test_trend_dip import walk


def research_tbdvol_pos(c, ma=200, vq=0.8, vw=20):
    """Copied logic of v3_tbdvol.py run() (with bt.py sma / rsi / state_machine), pandas version."""
    def sma(x, n): return x.rolling(n).mean()

    def rsi(c, n):
        d = c.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
        au = up.ewm(alpha=1 / n, adjust=False).mean(); ad = dn.ewm(alpha=1 / n, adjust=False).mean()
        return 100 - 100 / (1 + au / ad.replace(0, np.nan))

    def state_machine(entry, exit_):
        e = entry.values; x = exit_.values; p = np.zeros(len(e)); on = 0
        for i in range(len(e)):
            if on and x[i]: on = 0
            elif not on and e[i]: on = 1
            p[i] = on
        return pd.Series(p, index=entry.index)
    r1 = c.pct_change(); v = r1.rolling(vw).std(); g = (v < v.rolling(252).quantile(vq)).astype(float)
    up = (c > sma(c, ma)).astype(float)
    dip = state_machine((rsi(c, 2) < 5) & (c <= sma(c, ma)), c > sma(c, 5)).astype(float)
    return np.maximum(up * g, dip)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_same_positions_as_the_research(seed):
    c = walk(seed)
    ref = research_tbdvol_pos(c).values
    st, *_ = positions(c.values, vol_q=80, vol_days=20)
    bot = np.array([1.0 if s in ("trend", "dip") else 0.0 for s in st])
    ok = ~np.isnan(c.rolling(200).mean().values)
    assert (bot[ok] == ref[ok]).mean() == 1.0       # identical on every day once SMA200 exists
    assert (st == "volatile").sum() > 20             # the filter really bites in the test data
    assert (st == "dip").sum() > 5


def test_filter_off_is_the_old_strategy():
    c = walk(7)
    a, *_ = positions(c.values)
    b, *_ = positions(c.values, vol_q=0)
    assert (a == b).all() and "volatile" not in set(a)


def test_vol_gate_definition():
    c = walk(3)
    calm, v, thr = vol_gate(c.values, 80, 20)
    k = 600
    w = c.pct_change().values[k - 19:k + 1]
    assert v[k] == pytest.approx(np.std(w, ddof=1))                        # sample standard deviation of 20 daily changes
    assert thr[k] == pytest.approx(np.percentile(v[k - 251:k + 1], 80))     # 80th percentile of the last 252, today included
    assert calm[k] == (v[k] < thr[k])
    assert not calm[:270].any()                                             # no verdict before a year of volatility exists


def test_seeded_and_evaluates():
    s = S.get("qld_tbdv")
    assert s and s.type == "trend_dip" and s.params["vol_gate_q"] == 80 and s.params["signal"] == "QQQ"
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("trend", "dip", "volatile", "out")
    assert ev["target"] in ({"QLD": 0.99}, {"BIL": 0.99})
    assert any(c["k"].startswith("Volatility") for c in ev["checks"])
    assert [t["k"] for t in ev["detail"]["tiles"]] == ["trend", "dip", "volatile", "out"]
    spec = s.chart(NOW)
    assert [p["id"] for p in spec["charts"][0]["panes"]] == ["rsi", "vol"]
    # the plain strategy shows no filter
    ev0 = S.get("qld_tbd").evaluate(NOW)
    assert not any(c["k"].startswith("Volatility") for c in ev0["checks"]) and len(ev0["detail"]["tiles"]) == 3


def test_health_recompute_agrees():
    tbl = health.indicator_table(S.get("qld_tbdv"), NOW, rows=60)
    assert tbl["max_diff"] < 1e-6 and all(r["ok"] for r in tbl["rows"])


def test_new_default_added_to_an_existing_install():
    db.run("DELETE FROM strategies WHERE id='qld_tbdv'")
    db.set_state("seeded_defaults", [d[0] for d in S.DEFAULTS if d[0] != "qld_tbdv"])
    assert S.seed() == ["qld_tbdv"]
    assert S.seed() == []                             # only once
    assert S.get("qld_tbdv").params["vol_gate_q"] == 80
