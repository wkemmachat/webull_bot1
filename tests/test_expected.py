"""Expected returns: research − haircut, weak/typical/good ranges, the mix of strategies, real vs expected, docs."""
import json
import math
import time

import pytest

from app import db, expected as E, ledger
from app import strategies as S
from app.strategies import DEFAULTS
from conftest import NOW


def test_every_default_strategy_has_research_and_a_doc():
    F = E.load_file()
    from app.main import DOCS
    for d in DEFAULTS:
        spec = F["strategies"][d[0]]
        assert spec["expect"]["cagr"] > 0 and spec["reviewed"]
        assert (DOCS / f"{spec['doc']}.md").exists(), spec["doc"]
        assert f"<!--expected:{d[0]}-->" in (DOCS / f"{spec['doc']}.md").read_text(encoding="utf-8"), d[0]
    assert E.review_info()["next"] > F["reviewed"]


def test_backtest_research_comes_from_the_same_file():
    from app import backtest as BT
    assert BT.RESEARCH["usd_ibs"]["cagr"] == E.load_file()["strategies"]["usd_ibs"]["research"]["cagr"]


def test_haircut_setting():
    assert E.haircut() == pytest.approx(0.30)
    E.set_haircut(50)
    assert E.haircut() == pytest.approx(0.50)
    with pytest.raises(ValueError):
        E.set_haircut(95)
    E.set_haircut(30)


def test_ranges_compound_and_widen():
    r = E.ranges(0.20, None)
    assert r[1]["typical"] == pytest.approx(0.20) and r[2]["typical"] == pytest.approx(0.44) and "weak" not in r[1]
    r = E.ranges(0.20, 0.30)
    assert r[1]["weak"] < r[1]["typical"] < r[1]["good"]
    assert r[1]["weak"] == pytest.approx(1.2 * math.exp(-E.Z * 0.30) - 1)
    assert (r[3]["good"] - r[3]["weak"]) > (r[1]["good"] - r[1]["weak"])


def test_portfolio_is_each_strategys_money_growing_on_its_own():
    items = [{"id": "a", "amount": 30000, "mu": 0.10, "sig": 0.2}, {"id": "b", "amount": 10000, "mu": 0.50, "sig": 0.6},
             {"id": "c", "amount": 0, "mu": 0.9, "sig": 0.9}]
    corr = {"ids": ["a", "b"], "m": [[1, 0.2], [0.2, 1]]}
    p = E.portfolio(items, corr)
    assert p["amount"] == 40000
    assert p["periods"][1]["usd"] == pytest.approx(30000 * 1.1 + 10000 * 1.5)
    assert p["periods"][2]["usd"] == pytest.approx(30000 * 1.21 + 10000 * 2.25)
    # spreading money: the mix's volatility is below the weighted average when correlation < 1
    assert p["vol"] < 0.75 * 0.2 + 0.25 * 0.6
    one = E.portfolio([{"id": "a", "amount": 1, "mu": 0.1, "sig": 0.2}], corr)
    assert one["vol"] == pytest.approx(0.2) and one["periods"][1]["typical"] == pytest.approx(0.1)
    # no volatility yet → typical only
    q = E.portfolio([{"id": "a", "amount": 5, "mu": 0.1, "sig": None}], None)
    assert "weak" not in q["periods"][1] and q["vol"] is None
    assert E.portfolio([], None) is None


def test_real_vs_expected():
    mode, sid = "paper", "gold_sta"
    db.run("DELETE FROM money WHERE mode=? AND (strategy=? OR other=?)", (mode, sid, sid))
    year = 365.25 * 86400
    t0 = int(time.time() - year)
    db.run("INSERT INTO money(mode,t,kind,strategy,amount,status,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?)",
           (mode, t0, "add", sid, 10000, "done", t0, 10000))
    tr = E.track(mode, sid, 0.10, 0.2, 11500)
    assert tr["expected"] == pytest.approx(11000, rel=1e-3) and tr["status"] == "ahead"
    assert tr["weak"] < 11000 < tr["good"]
    assert E.track(mode, sid, 0.10, 0.2, 10500)["status"] == "behind"
    assert E.track(mode, sid, 0.10, 0.2, 7000)["status"] == "below"
    # a withdrawal half way lowers what is expected
    th = int(time.time() - year / 2)
    db.run("INSERT INTO money(mode,t,kind,strategy,amount,status,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?)",
           (mode, th, "withdraw", sid, 5000, "done", th, 5000))
    tr = E.track(mode, sid, 0.10, None, 6000)
    assert tr["expected"] == pytest.approx(11000 - 5000 * 1.1 ** 0.5, rel=1e-3) and tr["net_in"] == 5000
    # under 3 months: too early
    db.run("DELETE FROM money WHERE mode=? AND strategy=?", (mode, sid))
    db.run("INSERT INTO money(mode,t,kind,strategy,amount,status,done_at,done_amount) VALUES(?,?,?,?,?,?,?,?)",
           (mode, int(time.time() - 86400 * 20), "add", sid, 10000, "done", int(time.time() - 86400 * 20), 10000))
    assert E.track(mode, sid, 0.10, 0.2, 9000)["status"] == "early"
    db.run("DELETE FROM money WHERE mode=? AND strategy=?", (mode, sid))


@pytest.fixture(scope="module")
def checked():
    from app import backtest as BT
    BT._cache.clear()
    sent = []
    import app.notify as N
    orig = N.send
    N.send = lambda *a, **k: sent.append((a, k))
    try:
        chk = E.refresh("manual", send_line=True, now=NOW)
    finally:
        N.send = orig
    return chk, sent


def test_check_stores_volatility_and_correlations(checked):
    chk, sent = checked
    st = chk["strategies"]
    assert set(st) == {s.id for s in S.all_instances()}
    ok = [k for k, v in st.items() if v["ok"]]
    assert len(ok) >= 8
    for k in ok:
        assert st[k]["vol"] > 0 and st[k]["wv"] and st[k]["w0"]
    c = chk["corr"]
    assert c["ids"] == ok and all(abs(c["m"][i][i] - 1) < 1e-6 for i in range(len(ok)))
    assert sent and sent[0][0][0] == "review" and "Planning haircut 30%" in sent[0][0][1]
    assert db.get_state(E.STATE)["at"] == chk["at"]


def test_check_goes_stale_when_the_fee_or_settings_change(checked):
    chk, _ = checked
    assert chk["cost_pct"] == 0.11 and chk["fp"] == E.fingerprint() and not E.stale()
    assert E.status()["stale"] is False and E.status()["cost_pct"] == 0.11
    db.set_settings({"backtest_cost_pct": "0.2"})
    try:
        assert E.stale() and E.status()["stale"] is True
    finally:
        db.set_settings({"backtest_cost_pct": "0.11"})
    assert not E.stale()
    s = S.get("qld_ibs")
    S.update("qld_ibs", params={**s.row["params"], "ibs_max": 0.12})
    try:
        assert E.stale()
    finally:
        S.update("qld_ibs", params=s.row["params"])
    assert not E.stale()


def test_view_for_the_dashboard(checked):
    from app import moneyops
    moneyops.seed_paper()
    v = E.view("paper")
    assert v["haircut_pct"] == 30 and v["horizons"] == [1, 2, 3]
    rows = {r["id"]: r for r in v["strategies"]}
    u = rows["usd_ibs"]
    assert u["basis"]["basis"] == "research, real fee" and u["mu"] == pytest.approx(0.629 * 0.7)
    assert u["ranges"][1]["typical"] == pytest.approx(0.629 * 0.7)
    funded = [r for r in v["strategies"] if r["value"] > 0]
    if funded:
        p = v["portfolio"]
        assert p["amount"] == pytest.approx(sum(r["value"] for r in funded), rel=1e-6)
        assert p["periods"][1]["usd"] == pytest.approx(sum(r["value"] * (1 + r["mu"]) for r in funded), rel=1e-6)
        assert p["periods"][3]["weak"] < p["periods"][3]["typical"] < p["periods"][3]["good"]
        assert v["track"] and v["track"]["status"] == "early"
    json.dumps(v)                                                   # the API can send it


def test_custom_settings_use_the_bot_backtest(checked):
    s = S.get("qld_ibs")
    row = dict(s.row)
    row["params"] = {**s.params, "ibs_max": 0.3}
    b = E.basis(S.instance(row), checked[0])
    assert b["basis"] == "bot backtest"


@pytest.fixture
def client(checked):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        sign_in(c)
        db.set_state(E.STATE, checked[0])
        yield c


def test_docs_are_filled_in(client):
    r = client.get("/api/docs/strategy-usd-ibs").json()
    assert "<!--expected" not in r["markdown"] and "planning haircut" in r["markdown"]
    r = client.get("/api/docs/expected-returns").json()
    assert "<!--expected" not in r["markdown"] and "USD Trend + IBS-dip" in r["markdown"]
    r = client.get("/api/expected?mode=paper").json()
    assert r["strategies"] and r["review"]["reviewed"]
    assert client.post("/api/expected/haircut", json={"pct": 40}).json()["haircut_pct"] == pytest.approx(40)
    assert client.post("/api/expected/haircut", json={"pct": 99}).status_code == 400
    client.post("/api/expected/haircut", json={"pct": 30})


def test_saved_ratio_plan():
    assert E.set_plan({}) is None and E.get_plan() is None
    p = E.set_plan({"usd_ibs": 30, "gold_sta": 20, "c27_mom": 50, "qld_ibs": 0}, 120000)
    assert p["pct"] == {"usd_ibs": 30, "gold_sta": 20, "c27_mom": 50} and p["total"] == 120000
    assert E.get_plan()["pct"]["c27_mom"] == 50
    with pytest.raises(ValueError):
        E.set_plan({"usd_ibs": 70, "gold_sta": 40})                  # 110%
    with pytest.raises(ValueError):
        E.set_plan({"nope": 10})
    with pytest.raises(ValueError):
        E.set_plan({"usd_ibs": 0})
    assert E.get_plan()["total"] == 120000                           # a refused save keeps the old plan
    v = E.view("paper")
    assert v["plan"]["pct"]["usd_ibs"] == 30 and v["unassigned"] >= 0
    E.set_plan(None)
    assert E.get_plan() is None


def test_plan_api(client):
    r = client.post("/api/expected/plan", json={"pct": {"usd_ibs": 60, "qld_regime": 40}, "total": 50000})
    assert r.status_code == 200 and r.json()["plan"]["pct"] == {"usd_ibs": 60, "qld_regime": 40}
    assert client.get("/api/expected?mode=paper").json()["plan"]["total"] == 50000
    assert client.post("/api/expected/plan", json={"pct": {"usd_ibs": 80, "qld_regime": 40}}).status_code == 400
    assert client.post("/api/expected/plan", json={"pct": {}}).json()["plan"] is None
