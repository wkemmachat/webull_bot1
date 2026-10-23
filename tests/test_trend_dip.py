"""QLD + Trend + bear-dip: the bot's rule against the research code (ETF Strategy Lab 2026-10-23, choose.py tbd_pos)."""
import numpy as np
import pandas as pd
import pytest

from app import db, health
from app import strategies as S
from app.strategies.trend_dip import positions
from conftest import NOW


def research_tbd_pos(c, ma=200, th=5, exit_ma=5):
    """Copied logic of the research (bt.py sma / rsi / state_machine, choose.py tbd_pos), pandas version."""
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
    up = c > sma(c, ma)
    dip = state_machine((rsi(c, 2) < th) & ~up, c > sma(c, exit_ma))
    return (up | (dip > 0)).astype(float)


def walk(seed, n=3000):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.014, n)
    r[rng.random(n) < 0.03] *= 3                     # some sharp days so RSI(2) < 5 happens
    return pd.Series(300 * np.exp(np.cumsum(r)))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_same_positions_as_the_research(seed):
    c = walk(seed)
    ref = research_tbd_pos(c).values
    st, *_ = positions(c.values)
    bot = np.array([1.0 if s in ("trend", "dip") else 0.0 for s in st])
    ok = ~np.isnan(c.rolling(200).mean().values)
    assert (bot[ok] == ref[ok]).mean() == 1.0       # identical on every day once SMA200 exists
    assert (st == "dip").sum() > 5                   # dip trades really happen in the test data


def test_rsi_matches_tradingview_definition():
    from app import indicators as I
    c = np.array([10, 11, 10.5, 10.2, 10.8, 11.5, 11.0, 10.4, 10.9, 11.2])
    r = I.rsi(c, 2)
    # hand-computed Wilder RSI(2): seed with the mean of the first two changes
    g, l = (1 + 0) / 2, (0 + 0.5) / 2
    assert r[2] == pytest.approx(100 - 100 / (1 + g / l))
    g, l = (g + 0) / 2, (l + 0.3) / 2
    assert r[3] == pytest.approx(100 - 100 / (1 + g / l))


def test_seeded_and_evaluates():
    s = S.get("qld_tbd")
    assert s and s.type == "trend_dip" and s.params["signal"] == "QQQ" and s.params["trade"] == "QLD"
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("trend", "dip", "out")
    assert ev["target"] in ({"QLD": 0.99}, {"BIL": 0.99})
    assert all(h["kind"] in ("BUY", "SELL") for h in ev["history"])
    spec = s.chart(NOW)
    assert [c["title"].split()[0] for c in spec["charts"]] == ["QQQ", "QLD"]
    assert spec["charts"][0]["panes"][0]["id"] == "rsi"


def test_health_recompute_agrees():
    tbl = health.indicator_table(S.get("qld_tbd"), NOW, rows=60)
    assert tbl["max_diff"] < 1e-6 and all(r["ok"] for r in tbl["rows"])


def test_new_default_added_to_an_existing_install():
    db.run("DELETE FROM strategies WHERE id='qld_tbd'")
    db.set_state("seeded_defaults", ["gold_sta", "gold_st30", "silver_dc", "silver_st", "qld_regime", "semis_regime"])
    assert S.seed() == ["qld_tbd"]
    assert S.seed() == []                             # only once
    db.run("UPDATE strategies SET archived=1 WHERE id='qld_tbd'")
    assert S.seed() == []                             # archived stays archived
    db.run("UPDATE strategies SET archived=0 WHERE id='qld_tbd'")
