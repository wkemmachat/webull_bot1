"""Web API smoke test: first-run setup, sign-in, every page's data, money and the manual."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app import strategies as S
from app.main import app


@pytest.fixture
def client(clean, clock):
    db.run("DELETE FROM users")
    db.run("DELETE FROM sessions")
    db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        yield c


def sign_in(c):
    assert c.get("/api/auth").json()["needs_setup"] is True
    r = c.post("/api/setup", json={"username": "kemmachat", "password": "testpassword123"})
    assert r.status_code == 200, r.text


def test_public_and_locked(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/dashboard").status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/login"
    assert client.get("/login").status_code == 200


def test_setup_only_from_the_same_computer(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "_same_computer", lambda request: False)
    assert client.get("/api/auth").json()["setup_allowed"] is False
    r = client.post("/api/setup", json={"username": "stranger", "password": "testpassword123"})
    assert r.status_code == 403 and db.one("SELECT COUNT(*) n FROM users")["n"] == 0


def test_wrong_password(client):
    sign_in(client)
    client.post("/api/logout")
    assert client.post("/api/login", json={"username": "kemmachat", "password": "nope-nope-nope"}).status_code == 401
    assert client.post("/api/setup", json={"username": "x", "password": "y"}).status_code == 403


GETS = ["/api/topbar", "/api/dashboard?mode=paper", "/api/strategies?mode=paper", "/api/strategy-types",
        "/api/strategies/gold_sta?mode=paper", "/api/strategies/qld_regime?mode=paper",
        "/api/strategies/gold_sta/chart?range=1M", "/api/strategies/qld_regime/chart?range=1Y",
        "/api/money?mode=paper", "/api/plans?mode=paper", "/api/settings/execution", "/api/fills?mode=paper",
        "/api/fills.csv?mode=paper", "/api/positions?mode=paper", "/api/health/report",
        "/api/health/indicators?strategy=gold_sta", "/api/events", "/api/events.log", "/api/line", "/api/webull",
        "/api/settings", "/api/docs"]


@pytest.mark.parametrize("path", GETS)
def test_pages(client, path):
    sign_in(client)
    r = client.get(path)
    assert r.status_code == 200, (path, r.text[:300])


def test_money_and_health_run(client):
    sign_in(client)
    assert client.post("/api/money/add", json={"mode": "paper", "strategy": "gold_sta", "amount": 1000}).status_code == 400
    assert client.post("/api/money/to-bot", json={"mode": "paper", "amount": 3000}).status_code == 200
    r = client.post("/api/money/add", json={"mode": "paper", "strategy": "gold_sta", "amount": 1000, "invest": "now"})
    assert r.status_code == 200, r.text
    r = client.post("/api/money/split", json={"mode": "paper", "equal": True, "strategies": ["silver_dc", "silver_st"]})
    assert r.status_code == 200 and r.json()["pool"] == 0
    f = client.get("/api/money?mode=paper").json()["fund"]
    assert f["pool"] == 0 and f["allocated"] == pytest.approx(len(S.rows()) * 10000 + 3000, rel=0.01)
    r = client.post("/api/health/run")
    assert r.status_code == 200
    items = r.json().get("items") or r.json().get("report", {}).get("items") or []
    assert items


def test_manual_pages(client):
    sign_in(client)
    docs = client.get("/api/docs").json()
    names = [d["name"] for d in (docs.get("docs") if isinstance(docs, dict) else docs)]
    from app.main import DOC_ORDER
    assert len(names) == len(DOC_ORDER) == 37
    for n in names:
        r = client.get(f"/api/docs/{n}")
        assert r.status_code == 200 and len(r.json()["markdown"]) > 100, n
    assert client.get("/api/docs/../config").status_code in (400, 404)


def test_live_needs_confirm(client):
    sign_in(client)
    r = client.post("/api/settings", json={"modes": {"live": True}})
    assert r.status_code == 400
    assert db.get_setting("mode_live") != "1"
    r = client.post("/api/settings", json={"modes": {"live": True}, "confirm": "LIVE"})
    assert r.status_code == 200 and db.get_setting("mode_live") == "1"


def test_favicon(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.headers["content-type"] == "image/x-icon"
    assert client.get("/static/icons/favicon.svg").status_code == 200
    assert any(i["sizes"] == "512x512" for i in client.get("/manifest.webmanifest").json()["icons"])


def test_today_ignores_deposits(client, clock):
    from app import execution, moneyops
    sign_in(client)
    execution.record_equity("paper", clock.dt, force=True)
    clock.advance(hours=2)
    moneyops.to_bot("paper", 5000)
    moneyops.add("paper", "gold_sta", 5000)
    execution.record_equity("paper", clock.dt, force=True)
    b = client.get("/api/dashboard?mode=paper").json()["bot"]
    assert abs(b["today"]) < 50                       # adding $5,000 is not a $5,000 gain


def test_head_requests(client):
    assert client.head("/api/health").status_code == 200          # uptime monitors and `curl -I`
    assert client.head("/", follow_redirects=False).status_code in (302, 307)
    assert client.head("/login").status_code == 200


def test_webull_shared_test_account_and_token_date(client, tmp_path):
    from app import brokers
    sign_in(client)
    r = client.post("/api/webull/test/keys", json={"shared": 2})
    assert r.status_code == 200 and r.json()["test"]["account_id"] == brokers.SHARED_TEST_ACCOUNTS[1]["account_id"]
    assert r.json()["test"]["endpoint"] == "th-api.uat.webullbroker.com"
    assert client.post("/api/webull/test/keys", json={"shared": 9}).status_code == 400
    b = brokers.WebullBroker(env="test")
    b.tok_dir.mkdir(parents=True, exist_ok=True)
    (b.tok_dir / "token.txt").write_text("abc\n1793000000000\nNORMAL\n")
    assert b.token_info() == (1793000000, "NORMAL")
    (b.tok_dir / "token.txt").unlink()


def test_webull_account_total_falls_back_to_cash_plus_positions(monkeypatch):
    from app import brokers
    b = brokers.WebullBroker(env="test")
    monkeypatch.setattr(b, "raw_account", lambda: ("A1", {"total_cash_balance": "1000.50", "account_currency_assets": []},
                                                    [{"symbol": "QLD", "quantity": "10", "last_price": "100"}]))
    monkeypatch.setattr(b, "_touch", lambda: None)
    a = b.account()
    assert a["cash"] == 1000.5 and a["market_value"] == 1000 and a["total"] == 2000.5
    monkeypatch.setattr(b, "raw_account", lambda: ("A1", {"total_asset": "5000", "total_cash_balance": "1000"}, []))
    assert b.account()["total"] == 5000


def test_webull_multi_currency_uses_usd_only(monkeypatch):
    from app import brokers
    b = brokers.WebullBroker(env="test")
    monkeypatch.setattr(b, "_touch", lambda: None)
    bal = {"total_cash_balance": "152000", "total_asset": "160000", "account_currency_assets": [
        {"currency": "USD", "cash_balance": "2000", "buying_power": "2000", "market_value": "1000", "net_liquidation_value": "3000"},
        {"currency": "THB", "cash_balance": "150000", "buying_power": "150000"},
        {"currency": "CNY", "cash_balance": "0"}]}
    monkeypatch.setattr(b, "raw_account", lambda: ("A1", bal, [{"symbol": "QLD", "quantity": "10", "last_price": "100"}]))
    a = b.account()
    assert a["cash"] == 2000 and a["buying_power"] == 2000 and a["total"] == 3000          # THB is never counted
    assert a["other_cash"] == [{"currency": "THB", "cash": 150000.0}]
    bal2 = {"total_cash_balance": "152000", "account_currency_assets": [{"currency": "USD"}, {"currency": "THB", "cash_balance": "150000"}]}
    monkeypatch.setattr(b, "raw_account", lambda: ("A1", bal2, []))
    assert b.account()["cash"] is None                                                       # unclear → no buys, not THB


def test_golive_checklist(client, clock):
    sign_in(client)
    r = client.get("/api/golive?mode=paper")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 15 and 0 <= d["pct"] <= 1 and not d["ready"]
    keys = {i["key"] for s in d["sections"] for i in s["items"]}
    assert {"sessions", "plans", "lots", "health", "t_withdraw", "t_restart", "t_guard", "m_fills"} <= keys
    d = client.post("/api/golive/tick", json={"key": "m_fills", "done": True, "mode": "paper"}).json()
    item = next(i for s in d["sections"] for i in s["items"] if i["key"] == "m_fills")
    assert item["status"] == "ok"
    assert client.post("/api/golive/tick", json={"key": "nope", "done": True}).status_code == 400
    assert client.post("/api/golive/restart", json={"mode": "paper"}).status_code == 200


def test_golive_detects_planned_tests(clean, clock):
    from app import golive, moneyops, execution as X
    from test_execution import run_until_done
    db.set_state("golive_start:paper", int(clock.dt.timestamp()) - 10)
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, dict(s.evaluate(clock.dt), target=s.target_for("2x")), clock.dt, brokers_get("paper"), db.get_settings())
    run_until_done(clock, pid)
    r = moneyops.withdraw("paper", s.id, 3000)
    run_until_done(clock, r["plan_id"])
    moneyops.move("paper", "gold_sta", "silver_dc", 100)
    rep = golive.report("paper")
    st = {i["key"]: i["status"] for sec in rep["sections"] for i in sec["items"]}
    assert st["t_withdraw"] == "ok" and st["t_move"] == "ok" and st["t_stop"] == "todo"


def brokers_get(m):
    from app import brokers
    return brokers.get(m)


def test_testtrade_api(client):
    sign_in(client)
    from app import brokers, ledger
    ledger.fund_in("paper", 300, brokers.get("paper").account()["cash"])
    d = client.get("/api/testtrade?mode=paper").json()
    assert {s["symbol"] for s in d["symbols"]} >= {"QLD", "SGOV"} and d["pool"] == 300
    r = client.post("/api/testtrade/start", json={"mode": "paper", "symbols": ["TSLA"]})
    assert r.status_code == 400
    r = client.post("/api/testtrade/start", json={"mode": "paper", "symbols": ["SGOV"], "qty": 1})
    assert r.status_code == 200
    s = next(x for x in r.json()["symbols"] if x["symbol"] == "SGOV")
    assert s["last"]["status"] in ("buying", "selling", "ok")
    g = client.get("/api/golive?mode=paper").json()
    assert any(i["key"] == "t_symbols" for sec in g["sections"] for i in sec["items"])


def test_indicator_crosscheck_returns_json_for_every_strategy(client):
    sign_in(client)
    from app import strategies as S
    for s in S.all_instances():
        r = client.get(f"/api/health/indicators?strategy={s.id}")
        assert r.status_code == 200, (s.id, r.text[:200])
        d = r.json()
        assert d.get("error") or (d["rows"] and all(isinstance(x["ok"], bool) for x in d["rows"])), s.id


def test_backtest_api(client):
    sign_in(client)
    r = client.get("/api/backtest/gold_sta")
    assert r.status_code == 200 and r.json()["ok"]
    r = client.post("/api/backtest/gold_sta", json={"params": {"atr": 12}})
    assert r.status_code == 200 and r.json()["custom"]
    r = client.post("/api/backtest/gold_sta", json={"params": {"atr": 1}})
    assert r.status_code == 400
    assert client.get("/api/backtest/nope").status_code == 404


def test_symbol_chart_api(client):
    sign_in(client)
    r = client.get("/api/backtest/c27_mom/chart?sym=QQQ").json()
    assert r["ok"] and r["sym"] == "QQQ" and r["symbols"]
    assert client.get("/api/backtest/c27_mom/chart?sym=ZZZZ").json()["ok"] is False
    assert client.get("/api/backtest/qld_regime/chart").json()["ok"] is False


def test_plans_carry_estimates_and_badge_per_mode(client):
    from app import engine
    sign_in(client)
    engine.tick()
    d = client.get("/api/plans?mode=paper").json()
    assert "next" in d and d["rule_code"] and isinstance(d["single_stock"], list)
    if d["plans"]:
        p = d["plans"][0]
        assert "est" in p
    top = client.get("/api/topbar").json()
    assert "plans_by_mode" in top["issues"]
