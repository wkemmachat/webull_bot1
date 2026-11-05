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


def test_late_orders_metals_and_basket(clean):
    """4H metals: each signal one 4H bar later; C2-7 (weekly list, daily signal): every order one trading day later."""
    a = BT.run("gold_sta", now=NOW)
    b = BT.run("gold_sta", now=NOW, delay=1)
    assert a["ok"] and b["ok"]
    ta = {x["why"]: x["t"] for x in a["trades"] if x["kind"] != "START"}
    tb = {x["why"]: x["t"] for x in b["trades"] if x["kind"] != "START"}
    both = [w for w in ta if w in tb]
    assert both and all(tb[w] >= ta[w] for w in both)               # the same signal is never traded earlier,
    assert any(tb[w] >= ta[w] + 4 * 3600 - 60 for w in both)        # often 4 hours later (or more, past the session)
    # …but often at the same time: an entry waits for the 22:00 start and an exit for the US open anyway
    assert a["series"]["strategy"] != b["series"]["strategy"]
    c = BT.run("c27_mom", now=NOW)
    d = BT.run("c27_mom", now=NOW, delay=1)
    if c["ok"]:
        tc = [x["t"] for x in c["trades"] if x["kind"] != "START"]
        td = [x["t"] for x in d["trades"] if x["kind"] != "START"]
        assert tc and td and td[0] > tc[0]                         # the delay is not ignored any more
        assert c["series"]["strategy"] != d["series"]["strategy"]


def test_late_rebalance_still_fills(clean):
    """A rebalance waiting one extra day keeps its day: it is not pushed back every day the drift lasts."""
    a = BT.run("qld_ibs", now=NOW)
    b = BT.run("qld_ibs", now=NOW, delay=1)
    ra = [x for x in a["trades"] if x["kind"] == "REBALANCE"]
    rb = [x for x in b["trades"] if x["kind"] == "REBALANCE"]
    assert not ra or rb                                            # rebalances still happen when orders are late


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
    saved = db.get_state(btview.SAVED + "usd_ibs")
    assert saved and saved["extra"]["boot"] == x["boot"]          # saved: the tab opens at once, also after a restart
    BT._cache.clear()
    assert btview.extra("usd_ibs")["boot"] == x["boot"]
    g = btview.extra("gold_sta")                               # ~2 years of Yahoo hourly gold: the research's 10 years
    assert g["ok"] and g["src"] == "research" and g["boot"]["years"] >= 9.5
    st = btview.stress("usd_ibs")
    assert st["ok"] and [r["t"].split(" ·")[0] for r in st["rows"]][0] == "as tested"
    assert len(st["rows"]) == 4 and all(r.get("cagr") is not None for r in st["rows"])
    base, f25, f50, late = st["rows"]
    assert f50["cagr"] <= f25["cagr"] <= base["cagr"]          # higher fees never help
    assert late["t"] == "every order 1 day late"
    m = btview.stress("gold_sta")
    assert m["rows"][-1]["t"] == "every signal one 4H bar late" and m["rows"][-1]["cagr"] is not None
    assert m["short"] and m["years"] < 9.5 and m["from"]            # gold: only the hourly prices Yahoo keeps


def test_saved_results_follow_settings(clean):
    st = btview.stress("qld_tbdv")
    fp = db.get_state(btview.SAVED + "qld_tbdv")["fp"]
    db.set_state(btview.SAVED + "qld_tbdv", {**db.get_state(btview.SAVED + "qld_tbdv"), "stress": {**st, "rows": [], "marker": 1}})
    assert btview.stress("qld_tbdv").get("marker") == 1           # the saved copy is used while nothing changed
    s = S.get("qld_tbdv")
    p = dict(s.params); k = next(k for k, v in p.items() if isinstance(v, int) and not isinstance(v, bool) and v > 2)
    p[k] = p[k] + 1
    S.update("qld_tbdv", params=p)
    try:
        again = btview.stress("qld_tbdv")
        assert "marker" not in again and again["rows"]             # other settings: worked out again
        assert db.get_state(btview.SAVED + "qld_tbdv")["fp"] != fp
    finally:
        S.update("qld_tbdv", params=s.params)


def test_warm_all_saves_every_strategy(clean):
    for s in S.all_instances():
        db.run("DELETE FROM state WHERE k=?", (btview.SAVED + s.id,))
    assert btview.missing()
    out = btview.warm_all()
    assert out["done"] == len(S.all_instances()) and not out["failed"]
    assert not btview.missing()
    again = btview.warm_all()                                       # fresh copies are kept, not worked out again
    assert again["done"] == out["done"] and again["s"] <= out["s"]


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
