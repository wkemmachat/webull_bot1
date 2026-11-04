"""Backtest page (every strategy) and the extra analyses of a strategy's Backtest tab (5 Nov 2026)."""
import numpy as np
import pandas as pd
import pytest

from app import backtest as BT, btview, db, expected as E
from app import strategies as S
from conftest import NOW


@pytest.fixture(scope="module")
def checked():
    BT._cache.clear()
    import app.notify as N
    orig = N.send
    N.send = lambda *a, **k: None
    try:
        return E.refresh("manual", send_line=False, now=NOW)
    finally:
        N.send = orig


def test_late_orders_shift_every_fill_by_one_day(clean):
    a = BT.run("usd_ibs", now=NOW)
    b = BT.run("usd_ibs", now=NOW, delay=1)
    assert a["ok"] and b["ok"] and a["series"]["t"] == b["series"]["t"]
    days = a["series"]["t"]
    ta = [x["t"] for x in a["trades"] if x["kind"] != "START"]
    tb = [x["t"] for x in b["trades"] if x["kind"] != "START"]
    assert ta and tb and tb[0] > ta[0]
    da = pd.Timestamp(ta[0], unit="s").date()
    db_ = pd.Timestamp(tb[0], unit="s").date()
    i = [pd.Timestamp(t, unit="s").date() for t in days]
    assert i.index(db_) == i.index(da) + 1                    # the first order fills one trading day later
    assert BT.run("usd_ibs", now=NOW, delay=0) is a          # the normal run is untouched (same cached result)
    with pytest.raises(BT.BacktestError):
        BT.run("gold_sta", now=NOW, delay=1)


def test_overview_every_strategy(clean, checked):
    db.set_state(E.STATE, checked)
    ov = btview.overview("paper")
    ids = {r["id"] for r in ov["rows"]}
    assert ids == {r["id"] for r in db.rows("SELECT id FROM strategies WHERE archived=0")}
    assert len(ov["dates"]) == 523 and all(len(v) == 523 for v in ov["series"].values())
    assert set(ov["corr"]["ids"]) == set(ov["series"]) and len(ov["corr"]["m"]) == len(ov["corr"]["ids"])
    # gold and silver on default settings: the research's 10 years (Yahoo has only ~2 years of hourly metals prices)
    g = next(r for r in ov["rows"] if r["id"] == "gold_trend_calm")
    assert g["src"] == "research" and g["r10"] == E.basis(S.get("gold_trend_calm"), checked)["cagr"] and g["years"] >= 9.5
    assert g["group"] == "gold" and next(r for r in ov["rows"] if r["id"] == "silver_gold_ok")["group"] == "silver"
    u = next(r for r in ov["rows"] if r["id"] == "usd_ibs")
    assert u["src"] == "bot" and u["group"] == "usd"
    if u["r10"] is not None:
        assert u["r10"] == checked["strategies"]["usd_ibs"]["cagr10"]
        assert u["ret_dd"] == round(u["r10"] / abs(u["dd10"]), 2)
    tot = sum(r["value"] for r in ov["rows"] if r["value"] > 0.5)
    assert ov["summary"]["total"] == pytest.approx(tot, abs=0.05)
    assert sum(ov["summary"]["by_symbol"].values()) == pytest.approx(tot, abs=1)
    for r in ov["rows"]:
        assert r["below"] is None or 0 <= r["below"] <= 100
        assert r["up"] <= r["of"]


def test_research_curves_only_on_default_settings(clean, checked):
    db.set_state(E.STATE, checked)
    s = S.get("gold_sta")
    p = dict(s.params); p["atr"] = int(p["atr"]) + 1
    S.update("gold_sta", params=p)
    try:
        g = next(r for r in btview.overview("paper")["rows"] if r["id"] == "gold_sta")
        assert g["src"] == "bot"                              # own settings: the research curve no longer applies
    finally:
        S.update("gold_sta", params=s.params)


def test_bootstrap_is_reproducible_and_ordered():
    idx = pd.date_range("2016-11-04", periods=523 * 5, freq="B")
    rng = np.random.default_rng(1)
    ser = pd.Series(10000 * np.cumprod(1 + rng.normal(0.0008, 0.02, len(idx))), index=idx)
    a = btview.bootstrap(ser, 7, paths=400)
    b = btview.bootstrap(ser, 7, paths=400)
    assert a == b
    assert all(x <= y <= z for x, y, z in zip(a["p10"], a["p50"], a["p90"]))
    assert a["cagr"]["p10"] <= a["cagr"]["p50"] <= a["cagr"]["p90"]
    assert a["fall"]["p10"] <= a["fall"]["p50"] <= 0
    assert 0 <= a["chance"]["fall50"] <= a["chance"]["fall40"] <= a["chance"]["fall30"] <= 100
    assert len(a["x"]) == len(a["p50"]) and a["x"][-1] == 1.0


def test_extra_and_stress(clean):
    x = btview.extra("usd_ibs")
    assert x["ok"] and x["boot"] and x["boot"]["paths"] == btview.BOOT_PATHS
    rg = x["regime"]
    assert rg is None or (rg["etf"] == "USD" and 0 < rg["bad_share"] < 100)
    assert btview.extra("usd_ibs") is x                        # cached for the same backtest
    g = btview.extra("gold_sta")                               # ~2 years of Yahoo hourly gold: the research's 10 years
    assert g["ok"] and g["src"] == "research" and g["boot"]["years"] >= 9.5
    st = btview.stress("usd_ibs")
    assert st["ok"] and [r["t"].split(" ·")[0] for r in st["rows"]][0] == "as tested"
    assert len(st["rows"]) == 4 and all(r.get("cagr") is not None for r in st["rows"])
    base, f25, f50, late = st["rows"]
    assert f50["cagr"] <= f25["cagr"] <= base["cagr"]          # higher fees never help
    m = btview.stress("gold_sta")
    assert m["rows"][-1].get("na") and m["rows"][-1]["cagr"] is None


def test_api(clean, checked):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        sign_in(c)
        db.set_state(E.STATE, checked)
        assert c.get("/api/backtest-overview?mode=paper").json()["rows"]
        assert c.get("/api/backtest/qld_tbdv/extra").json()["ok"]
        assert c.get("/api/backtest/qld_tbdv/stress").json()["ok"]
        assert c.get("/api/backtest/nope/extra").status_code == 404
