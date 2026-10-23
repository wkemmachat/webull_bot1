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
    assert len(names) == len(DOC_ORDER) == 26
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
