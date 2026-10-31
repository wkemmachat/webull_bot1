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
    assert s.params["cash_symbol"] == "" and s.params["gold_share_pct"] == 50
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("trend", "dip", "volatile", "out")
    assert ev["target"] in ({"QLD": 0.99}, {"GLD": 0.495})
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


def test_gold_share_when_out():
    s = S.get("qld_tbdv")
    assert s.target_for("out") == {"GLD": 0.495} and s.trade_symbols() == ["QLD", "GLD"]      # default: half gold, half cash
    assert s.park_text() == "50% GLD + 50% cash"
    s.params = dict(s.params, gold_share_pct=0, cash_symbol="BIL")
    assert s.target_for("out") == {"BIL": 0.99} and s.trade_symbols() == ["QLD", "BIL"]       # the old T-bill parking
    s.params = dict(s.params, gold_share_pct=50, gold_symbol="GLD")
    assert s.target_for("out") == {"GLD": 0.495, "BIL": 0.495}
    assert s.target_for("volatile") == {"GLD": 0.495, "BIL": 0.495}
    assert s.target_for("trend") == {"QLD": 0.99} and s.target_for("dip") == {"QLD": 0.99}
    assert set(s.trade_symbols()) == {"QLD", "BIL", "GLD"} and s.park_text() == "50% GLD + 50% BIL"
    s.params = dict(s.params, gold_share_pct=100)
    assert s.target_for("out") == {"GLD": 0.99} and s.park_text() == "GLD"
    s.params = dict(s.params, gold_share_pct=50, cash_symbol="")                               # no T-bill ETF: the rest stays cash
    assert s.target_for("out") == {"GLD": 0.495} and s.park_text() == "50% GLD + 50% cash"
    ev = s.evaluate(NOW)
    assert ev["ok"] and any("50% GLD" in t["hold"] for t in ev["detail"]["tiles"])


def test_old_bil_defaults_move_to_cash_once():
    import json
    olds = {sid: p for key, sid, p in S.UPGRADES if key == "cash_parking_2026_10"}
    assert set(olds) == {"qld_regime", "semis_regime", "qld_tbd", "qld_tbdv"}
    for sid, p in olds.items():
        db.run("UPDATE strategies SET params=? WHERE id=?", (json.dumps(p), sid))
    db.run("UPDATE strategies SET params=? WHERE id='semis_regime'", (json.dumps({**olds["semis_regime"], "vol_gate_pct": 35}),))  # changed by you
    db.set_state("upgrades_done", [])
    try:
        assert sorted(S.upgrade_defaults()) == ["qld_regime", "qld_tbd", "qld_tbdv"]
        assert S.get("qld_regime").params["cash_symbol"] == "" and S.get("qld_tbd").params["cash_symbol"] == ""
        assert S.get("qld_tbdv").params["gold_share_pct"] == 50 and S.get("qld_tbdv").target_for("out") == {"GLD": 0.495}
        assert S.get("semis_regime").params["cash_symbol"] == "BIL"                 # your own settings are left alone
        assert S.upgrade_defaults() == []                                            # once only
    finally:
        for sid, typ, name, color, params, ex in S.DEFAULTS:
            if sid in olds:
                db.run("UPDATE strategies SET params=? WHERE id=?", (json.dumps(params), sid))
