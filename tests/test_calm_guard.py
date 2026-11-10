"""Calm guard + dips (type calm_guard): the bot's rule against an independent copy of the research rule ("DDM · RXL · SSO: 1x
signals and a better rule", 10 Nov 2026: lab2.py Lab.calm / above / hold_dips + final_rule.py make), the three new defaults
(DDM, SSO, RXL), and that nothing already running changed."""
import numpy as np
import pandas as pd
import pytest

from app import db, exposure, health, ledger, marketdata as md
from app import strategies as S
from app.strategies.calm_guard import CalmGuardStrategy
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


DDM, SSO, RXL = default("ddm_calm_guard"), default("sso_calm_guard"), default("rxl_calm_guard")


# ---------------------------------------------------------------- the research rule, written independently
def research_weights(u, X, q=80, n=None, cap=25, th=0.15, dcap=40, win=20, lb=252, mx=5):
    """u = traded 2x ETF bars, X = the 1x ETF's full bars. Weight of the 2x ETF (0/1) after each close, on u's days."""
    v = np.log(X.c).diff().rolling(win).std()
    calm = (v <= v.rolling(lb).quantile(q / 100)).reindex(u.index).fillna(False).values
    hold = calm | ((X.c > X.c.rolling(n).mean()).reindex(u.index).fillna(False).values if n else False)
    ann = v * np.sqrt(252) * 100
    hold = hold & (ann < cap).reindex(u.index).fillna(False).values
    gate = (ann < dcap).reindex(u.index).fillna(False).values
    ibs = np.round(((u.c - u.l) / (u.h - u.l).replace(0, np.nan)).values, 4)
    c, h = u.c.values, u.h.values
    w = np.zeros(len(c)); d = None; held = 0
    for i in range(len(c)):
        if hold[i]:
            d = None; w[i] = 1; continue
        if d is not None:
            held += 1
            if c[i] > h[i - 1] or held >= mx:
                d = None
        if d is None and gate[i] and ibs[i] < th:
            d, held = 0, 0
        w[i] = 1 if d is not None else 0
    return w


def bars(seed, n=2600, base=None, lev=1.0, start="2012-01-02"):
    rng = np.random.default_rng(seed)
    if base is None:                                     # calm stretches, jumpy ones and a few crashes (>40% a year)
        sig = np.full(n, 0.008)
        for k in range(200, n, 520):
            sig[k:k + 120] = 0.016
            sig[k + 120:k + 160] = 0.032
        r = rng.normal(0.0004, 1, n) * sig
        for k in range(320, n, 520):
            r[k:k + 40] -= 0.006
    else:
        r = lev * base + rng.normal(0, 0.002, n)
    c = 100 * np.exp(np.cumsum(r))
    o = c * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.006, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.006, n)))
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": 1e6}, index=idx), r


def fake_market(monkeypatch, seed, market="SPY", trade="SSO", late_start=0):
    x, r = bars(seed)
    u, _ = bars(seed + 100, base=r, lev=2.0)
    u = u.iloc[late_start:]                              # the 2x ETF may start later than its 1x (RXL: 2007, XLV: 1998)
    dfs = {market: x, trade: u}
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: dfs[sym])
    return dfs


def strat(params, sid="t"):
    return CalmGuardStrategy({"id": sid, "name": sid, "type": "calm_guard", "params": params, "exec": {}, "color": "#fff"})


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
@pytest.mark.parametrize("which", ["DDM", "SSO", "RXL"])
def test_same_positions_as_the_research(monkeypatch, seed, which):
    p = {"DDM": DDM, "SSO": SSO, "RXL": RXL}[which]
    dfs = fake_market(monkeypatch, seed, p["market"], p["trade"], late_start=400)
    fr = strat(p).frame(NOW)
    ref = research_weights(dfs[p["trade"]], dfs[p["market"]], n=p["uptrend_ma_days"] or None)
    ok = fr["state"].values != ""
    assert ok.sum() > 2000 and ok[0]                                         # the market's earlier history warms it up
    assert np.array_equal(fr["weight"].values, ref)                          # identical on every day
    assert {"hold", "dip", "ready", "blocked"} <= set(fr["state"].values)   # every state really happens
    assert 0.3 < fr["weight"].mean() < 0.97


def test_cold_start_waits_for_a_year_of_volatility(monkeypatch):
    dfs = fake_market(monkeypatch, 5)
    fr = strat(SSO).frame(NOW)
    first = np.argmax(fr["state"].values != "")
    assert first == 20 + 252 - 1 and (fr["weight"].values[:first] == 0).all()
    dfs["SPY"] = dfs["SPY"].iloc[:200]
    with pytest.raises(md.DataError):
        strat(SSO).frame(NOW)


def test_switches(monkeypatch):
    dfs = fake_market(monkeypatch, 3)
    base = strat(SSO).frame(NOW)
    no_up = strat({**SSO, "uptrend_ma_days": 0}).frame(NOW)
    assert (no_up["guard"] <= base["guard"]).all() and no_up["guard"].sum() < base["guard"].sum()
    no_cap = strat({**SSO, "vol_cap_pct": 0}).frame(NOW)
    assert (base["guard"] <= no_cap["guard"]).all() and no_cap["guard"].sum() > base["guard"].sum()
    no_dips = strat({**SSO, "dip_ibs_max": 0}).frame(NOW)
    assert "dip" not in set(no_dips["state"]) and np.array_equal(no_dips["guard"].values, base["guard"].values)
    ann = np.log(dfs["SPY"]["c"]).diff().rolling(20).std() * np.sqrt(252) * 100
    assert np.allclose(base["ann"].values[300:], ann.reindex(base.index).values[300:])


def test_frame_waits_for_every_symbol(monkeypatch):
    dfs = fake_market(monkeypatch, 9)
    full = strat(SSO).frame(NOW)
    dfs["SSO"] = dfs["SSO"].iloc[:-1]
    part = strat(SSO).frame(NOW)
    assert part.index[-1] == full.index[-2] and part["state"].iloc[-1] == full["state"].iloc[-2]


def test_a_missing_2x_day_does_not_move_the_volatility(monkeypatch):
    """Volatility and the average run on the 1x ETF's own full series: a day the 2x ETF lacks must not change them."""
    dfs = fake_market(monkeypatch, 4)
    full = strat(SSO).frame(NOW)
    gap = dfs["SSO"].index[-80]
    dfs["SSO"] = dfs["SSO"].drop(gap)
    part = strat(SSO).frame(NOW)
    same = full.drop(gap)
    for k in ("ann", "vol_q", "ma", "guard"):
        assert np.array_equal(part[k].values.astype(float), same[k].values.astype(float), equal_nan=True), k


def test_targets_and_parking():
    s = strat(SSO)
    assert s.target_for("hold") == {"SSO": 0.99} and s.target_for("dip") == {"SSO": 0.99}
    assert s.target_for("ready") == {} and s.target_for("blocked") == {}
    g = strat({**SSO, "gold_share_pct": 50, "cash_symbol": "BIL"})
    assert g.target_for("blocked") == {"GLD": 0.495, "BIL": 0.495}
    assert s.trade_symbols() == ["SSO"] and sorted(x[0] for x in s.data_needs()) == ["SPY", "SSO"]
    assert s.bench_extra() == ["SPY"] and s.benchmark_symbol() == "SSO"


def test_new_defaults_seeded_with_research_settings_and_no_live_money():
    for sid, trade, market, up in (("ddm_calm_guard", "DDM", "DIA", 100), ("sso_calm_guard", "SSO", "SPY", 100),
                                   ("rxl_calm_guard", "RXL", "XLV", 0)):
        s = S.get(sid)
        assert s.type == "calm_guard" and s.row["control"] == "active"
        p = s.params
        assert (p["trade"], p["market"], p["calm_pct"], p["vol_days"], p["vol_lookback"], p["uptrend_ma_days"], p["vol_cap_pct"],
                p["dip_ibs_max"], p["dip_max_days"], p["dip_vol_cap_pct"], p["cash_symbol"]) == \
            (trade, market, 80, 20, 252, up, 25.0, 0.15, 5, 40.0, "")
        assert ledger.get("live", sid)["cap_in"] == 0 and not ledger.get("live", sid)["holdings"]
        assert ledger.get("test", sid)["cap_in"] == 0


def test_strategies_already_running_are_unchanged():
    want = {"usd_ibs": ("ibs_dip", {"trade": "USD", "ibs_max": 0.15}), "rom_tbd": ("trend_dip", {"trade": "ROM", "ma_days": 150}),
            "qld_tbdv": ("trend_dip", {"trade": "QLD", "ma_days": 200}), "usd_smh_ibs": ("trend_gate", {"trade": "USD", "ma_days": 125})}
    for sid, (typ, sub) in want.items():
        s = S.get(sid)
        assert s.type == typ and {k: s.params[k] for k in sub} == sub


def test_dow_and_health_care_are_their_own_groups():
    assert exposure.KNOWN["RXL"] == ("health", 2) and exposure.KNOWN["XLV"] == ("health", 1)
    assert exposure.KNOWN["DDM"] == ("dow", 2) and exposure.KNOWN["DIA"] == ("dow", 1)
    assert exposure.GROUPS["health"][1] == "XLV" and exposure.GROUPS["dow"][1] == "DIA"
    assert "health" not in exposure.US_TECH and "dow" not in exposure.US_TECH


def test_old_ddm_rule_is_gone():
    assert "ddm_ibs_gated" not in [d[0] for d in S.DEFAULTS] and "ibs_gated" not in S.TYPES


@pytest.mark.parametrize("sid", ["ddm_calm_guard", "sso_calm_guard", "rxl_calm_guard"])
def test_evaluates_on_the_demo_prices(sid):
    s = S.get(sid)
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("hold", "dip", "ready", "blocked")
    assert ev["bar_time"] < NOW.timestamp()
    assert set(ev["target"]) <= {s.params["trade"]}
    assert [t["k"] for t in ev["detail"]["tiles"]] == ["hold", "dip", "ready", "blocked"]
    assert all(h["kind"] in ("BUY", "SELL") for h in ev["history"])
    assert s.describe()["rule"]
    ch = s.chart(NOW)
    assert [c["id"] for c in ch["charts"]] == ["signal", "market"] and ch["charts"][0]["candles"]


@pytest.mark.parametrize("sid", ["ddm_calm_guard", "sso_calm_guard", "rxl_calm_guard"])
def test_health_recompute_agrees(sid):
    tbl = health.indicator_table(S.get(sid), NOW, rows=60)
    assert all(r["ok"] for r in tbl["rows"])


def test_new_defaults_added_once_to_an_existing_install():
    new = ("ddm_calm_guard", "sso_calm_guard", "rxl_calm_guard")
    for sid in new:
        db.run("DELETE FROM strategies WHERE id=?", (sid,))
    db.set_state("seeded_defaults", [d[0] for d in S.DEFAULTS if d[0] not in new])
    assert sorted(S.seed()) == sorted(new)
    assert S.seed() == []
    assert S.get("rxl_calm_guard").params["uptrend_ma_days"] == 0 and S.get("sso_calm_guard").row["line_on"] == 0


def test_pages_and_api(clean, clock):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        sign_in(c)
        for sid, doc in (("ddm_calm_guard", "strategy-ddm-calm-guard"), ("sso_calm_guard", "strategy-sso-calm-guard"),
                         ("rxl_calm_guard", "strategy-rxl-calm-guard")):
            d = c.get(f"/api/strategies/{sid}")
            assert d.status_code == 200 and d.json()["row"]["type"] == "calm_guard"
            assert c.get(f"/api/strategies/{sid}/chart").json()["charts"]
            bt = c.get(f"/api/backtest/{sid}")
            assert bt.status_code == 200 and bt.json()["ok"], bt.text[:300]
            page = c.get(f"/api/docs/{doc}").json()
            assert "<!--expected:" not in page["markdown"] and "Calm guard + dips" in page["markdown"]
            assert doc in [x["name"] for x in c.get("/api/docs").json()["docs"]]
        assert c.get("/api/expected?mode=paper").status_code == 200
        assert c.post("/api/health/run").status_code == 200
