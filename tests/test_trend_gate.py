"""Trend + volatility gate + dips (type trend_gate): the bot's rule against an independent copy of the research rule
(2x ETF Strategy Challengers, 2 Nov 2026, stage2.py `weights`), the two new default strategies, and that nothing about the
strategies already running changed."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app import db, health, ledger, marketdata as md
from app import strategies as S
from app.strategies.trend_gate import TrendGateDipStrategy
from conftest import NOW

R1 = dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index("rom_vol_ibs")][4])
U1 = dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index("usd_smh_ibs")][4])


# ---------------------------------------------------------------- the research rule, written independently
def research_weights(sig, etf, dip_src, jumpy_src, p):
    """Research engine (stage2.weights) restated with pandas: weight of the ETF (0-1, before the 1% buffer)."""
    c = sig["c"]
    ma = c.ewm(span=p["ma_days"], adjust=False).mean() if p["ma_type"] == "EMA" else c.rolling(p["ma_days"]).mean()
    if p["ma_type"] == "EMA":                       # TradingView seeds the EMA with the simple mean of the first n closes
        n = p["ma_days"]
        e = np.full(len(c), np.nan)
        e[n - 1] = c.iloc[:n].mean()
        a = 2 / (n + 1)
        for i in range(n, len(c)):
            e[i] = a * c.iloc[i] + (1 - a) * e[i - 1]
        ma = pd.Series(e, index=c.index)
    v = c.pct_change().rolling(p["vol_days"]).std()
    calm = (v < v.rolling(p["vol_lookback"]).quantile(p["vol_gate_q"] / 100)).values if p["vol_gate_q"] > 0 else np.ones(len(c), bool)
    T = (c > ma).values
    tc, tv, out = T & calm, T & ~calm, ~T
    d = np.zeros(len(c), bool)
    if p.get("rsi_buy", 0) > 0:
        dd = c.diff()
        au = dd.clip(lower=0).ewm(alpha=1 / p["rsi_len"], adjust=False).mean()
        ad = (-dd.clip(upper=0)).ewm(alpha=1 / p["rsi_len"], adjust=False).mean()
        rsi = (100 - 100 / (1 + au / ad)).values
        sx = c.rolling(p["exit_ma"]).mean().values
        on = False
        for i in range(len(c)):
            if on and sx[i] == sx[i] and c.iloc[i] > sx[i]:
                on = False
            elif not on and out[i] and rsi[i] < p["rsi_buy"]:
                on = True
            d[i] |= on
    ibs = lambda df: np.round(((df["c"] - df["l"]) / (df["h"] - df["l"])).values, 4)
    if p.get("dip_ibs_max", 0) > 0:
        d |= out & (ibs(dip_src) < p["dip_ibs_max"])
    if p.get("jumpy_ibs_max", 0) > 0:
        d |= tv & (ibs(jumpy_src) < p["jumpy_ibs_max"])
    if p.get("target_vol_pct", 0) > 0:
        raw = np.minimum(1.0, p["target_vol_pct"] / 100 / (etf["c"].pct_change().rolling(p["size_vol_days"]).std() * np.sqrt(252)).values)
        held, sc = 0.0, np.zeros(len(c))
        for i in range(len(c)):
            if tc[i] and raw[i] == raw[i]:
                if held == 0 or abs(raw[i] - held) > p["size_band_pct"] / 100:
                    held = round(float(raw[i]), 2)
            else:
                held = 0.0
            sc[i] = held
    else:
        sc = tc.astype(float)
    return np.where(d, 1.0, np.where(tc, sc, 0.0))


def bars(seed, n=2600, drift=0.0004, vol=0.014, lev=1.0, base=None):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, n) if base is None else lev * base + rng.normal(0, 0.002, n)
    r[rng.random(n) < 0.03] *= 3
    c = 100 * np.exp(np.cumsum(r))
    o = c * np.exp(rng.normal(0, 0.004, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.008, n)))
    idx = pd.bdate_range("2014-01-01", periods=n, tz="UTC")
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": 1e6}, index=idx), r


def fake_market(monkeypatch, seed, sig_sym, etf_sym):
    sig, r = bars(seed)
    etf, _ = bars(seed + 100, base=r, lev=2.0)
    dfs = {sig_sym: sig, etf_sym: etf}
    monkeypatch.setattr(md, "daily_closed", lambda sym, now=None: dfs[sym])
    return dfs


def strat(params, sid="t"):
    return TrendGateDipStrategy({"id": sid, "name": sid, "type": "trend_gate", "params": params, "exec": {}, "color": "#fff"})


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("which", ["R1", "U1"])
def test_same_positions_as_the_research(monkeypatch, seed, which):
    p = R1 if which == "R1" else U1
    dfs = fake_market(monkeypatch, seed, p["signal"], p["trade"])
    s = strat(p)
    fr = s.frame(NOW)
    m = S.TYPES["trend_gate"].merge_params(p)
    ref = research_weights(dfs[p["signal"]], dfs[p["trade"]], dfs[s.dip_sym()], dfs[s.jumpy_sym()], m)
    ok = fr["state"].values != ""
    assert ok.sum() > 1500
    assert np.array_equal(np.round(fr["size"].values[ok], 2), np.round(ref[ok], 2))      # identical on every decided day
    st = fr["state"].values[ok]
    assert {"trend", "dip", "out"} <= set(st) and (st == "volatile").sum() > 20             # every state really happens
    if which == "U1":
        sz = fr["size"].values[ok & (fr["state"].values == "trend")]
        assert (sz < 1).any() and (sz > 0).all()                                            # the volatility cap bites


def test_frame_waits_for_every_symbol(monkeypatch):
    dfs = fake_market(monkeypatch, 9, "SMH", "USD")
    full = strat(U1).frame(NOW)
    dfs["USD"] = dfs["USD"].iloc[:-1]                       # USD's last bar not stored yet (data refresh in progress)
    part = strat(U1).frame(NOW)
    assert part.index[-1] == full.index[-2]                 # decided on the last day both have, not on half the data
    assert part["state"].iloc[-1] == full["state"].iloc[-2]


def test_targets_size_and_parking():
    s = strat(U1)
    assert s.target_for("trend", 0.5) == {"USD": 0.495}
    assert s.target_for("dip", 1.0) == {"USD": 0.99}
    assert s.target_for("out") == {} and s.target_for("volatile") == {}
    g = strat({**R1, "gold_share_pct": 50, "cash_symbol": ""})
    assert g.target_for("out") == {"GLD": 0.495}
    assert g.target_for("trend", 1.0) == {"ROM": 0.99}
    assert strat(U1).trade_symbols() == ["USD"] and strat(R1).trade_symbols() == ["ROM"]
    assert sorted(x[0] for x in strat(U1).data_needs()) == ["SMH", "USD"]
    assert sorted(x[0] for x in strat(R1).data_needs()) == ["IYW", "ROM"]


def test_new_defaults_seeded_with_research_settings_and_no_live_money():
    u, r = S.get("usd_smh_ibs"), S.get("rom_vol_ibs")
    assert u.type == r.type == "trend_gate" and u.row["control"] == "active"
    assert (u.params["signal"], u.params["trade"], u.params["ma_type"], u.params["ma_days"], u.params["vol_gate_q"],
            u.params["vol_lookback"], u.params["dip_ibs_max"], u.params["dip_ibs_symbol"], u.params["jumpy_ibs_max"],
            u.params["target_vol_pct"], u.params["rsi_buy"]) == ("SMH", "USD", "SMA", 125, 80, 504, 0.25, "SMH", 0.15, 40, 0)
    assert (r.params["signal"], r.params["trade"], r.params["ma_type"], r.params["ma_days"], r.params["vol_gate_q"],
            r.params["vol_lookback"], r.params["rsi_buy"], r.params["exit_ma"], r.params["dip_ibs_max"], r.params["target_vol_pct"]) \
        == ("IYW", "ROM", "EMA", 150, 90, 252, 5, 5, 0.15, 0)
    for sid in ("usd_smh_ibs", "rom_vol_ibs"):
        assert ledger.get("live", sid)["cap_in"] == 0 and not ledger.get("live", sid)["holdings"]
        assert ledger.get("test", sid)["cap_in"] == 0


def test_strategies_already_running_are_unchanged():
    """The strategies with real money keep exactly their settings and type (this update only adds)."""
    want = {"usd_ibs": ("ibs_dip", {"trade": "USD", "vol_symbol": "USD", "st_atr": 20, "st_mult": 4.5, "ibs_max": 0.15, "target_vol_pct": 40}),
            "rom_tbd": ("trend_dip", {"signal": "IYW", "trade": "ROM", "ma_days": 150, "exit_ma": 10, "vol_gate_q": 0}),
            "qld_tbdv": ("trend_dip", {"signal": "QQQ", "trade": "QLD", "ma_days": 200, "vol_gate_q": 80, "gold_share_pct": 50}),
            "qld_ibs": ("ibs_dip", {"trade": "QLD", "ibs_max": 0.15, "adx_min": 20})}
    for sid, (typ, sub) in want.items():
        s = S.get(sid)
        assert s.type == typ
        assert {k: s.params[k] for k in sub} == sub


def test_evaluates_on_the_demo_prices():
    for sid in ("usd_smh_ibs", "rom_vol_ibs"):
        s = S.get(sid)
        ev = s.evaluate(NOW)
        assert ev["ok"] and ev["state"] in ("trend", "dip", "volatile", "out")
        assert ev["bar_time"] < NOW.timestamp()
        tr = s.params["trade"]
        assert set(ev["target"]) <= {tr} and all(0 < w <= 0.99 for w in ev["target"].values())
        assert [t["k"] for t in ev["detail"]["tiles"]] == ["trend", "dip", "volatile", "out"]
        assert all(h["kind"] in ("BUY", "SELL", "SIZE") for h in ev["history"])
        assert s.describe()["rule"] and s.chart(NOW)["charts"][0]["candles"]


def test_health_recompute_agrees():
    for sid in ("usd_smh_ibs", "rom_vol_ibs"):
        tbl = health.indicator_table(S.get(sid), NOW, rows=40)
        assert tbl["max_diff"] < 1e-6 and all(r["ok"] for r in tbl["rows"]), sid


def test_new_defaults_added_once_to_an_existing_install():
    for sid in ("usd_smh_ibs", "rom_vol_ibs"):
        db.run("DELETE FROM strategies WHERE id=?", (sid,))
    db.set_state("seeded_defaults", [d[0] for d in S.DEFAULTS if d[0] not in ("usd_smh_ibs", "rom_vol_ibs")])
    assert sorted(S.seed()) == ["rom_vol_ibs", "usd_smh_ibs"]
    assert S.seed() == []
    assert S.get("usd_smh_ibs").params["ma_days"] == 125


def test_paper_plan_reaches_a_capped_target(clean, clock):
    """A sized target (USD at half) goes through the normal split plan and the books end at that weight."""
    from app import brokers, execution as X
    from test_execution import run_until_done
    s = S.get("usd_smh_ibs")
    ev = {**s.evaluate(NOW), "target": s.target_for("trend", 0.5)}
    pid = X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings())
    assert pid
    plan = run_until_done(clock, pid)
    assert plan["status"] == "done"
    w, _ = ledger.weights("paper", s.id, md.prices({"USD"}))
    assert w.get("USD", 0) == pytest.approx(0.495, abs=0.03)


def test_no_money_means_no_orders(clean, clock):
    """Like a strategy just added in Live: no money in it → following its signal sends nothing."""
    from app import brokers, execution as X
    s = S.get("rom_vol_ibs")
    with db.tx() as c:
        c.execute("DELETE FROM ledger WHERE mode='paper' AND strategy=?", (s.id,))
        c.execute("DELETE FROM money WHERE mode='paper' AND strategy=?", (s.id,))
    assert ledger.get("paper", s.id)["cap_in"] == 0
    ev = {**s.evaluate(NOW), "target": s.target_for("trend", 1.0)}
    assert X.reconcile("paper", s, ev, NOW, brokers.get("paper"), db.get_settings()) is None


def test_pages_and_api_for_the_new_strategies(clean, clock):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        sign_in(c)
        lst = {s["id"]: s for s in c.get("/api/strategies").json()["strategies"]} if isinstance(c.get("/api/strategies").json(), dict) \
            else {s["id"]: s for s in c.get("/api/strategies").json()}
        for sid, doc in (("usd_smh_ibs", "strategy-usd-smh-ibs"), ("rom_vol_ibs", "strategy-rom-vol-ibs")):
            assert sid in lst
            d = c.get(f"/api/strategies/{sid}")
            assert d.status_code == 200 and d.json()["row"]["type"] == "trend_gate"
            ch = c.get(f"/api/strategies/{sid}/chart")
            assert ch.status_code == 200 and ch.json()["charts"]
            bt = c.get(f"/api/backtest/{sid}")
            assert bt.status_code == 200 and bt.json()["ok"], bt.text[:300]
            page = c.get(f"/api/docs/{doc}").json()
            assert "<!--expected:" not in page["markdown"] and ("49.6" in page["markdown"] or "42.0" in page["markdown"])
            assert doc in [x["name"] for x in c.get("/api/docs").json()["docs"]]
        assert c.get("/api/expected?mode=paper").status_code == 200
        assert c.post("/api/health/run").status_code == 200
