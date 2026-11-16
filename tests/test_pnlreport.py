"""Profit & loss page (app/pnlreport.py): month by month and since start. Every view must add up: start + put in + P&L = end,
the months add up to the Dashboard's Since start, and the strategy rows add up to each month."""
from datetime import datetime, timezone

import pytest

from app import db, execution, pnlreport, views
from app import strategies as S


def _close(clock, y, m, d):
    clock.set(datetime(y, m, d, 21, 30, tzinfo=timezone.utc))         # 16:30 / 17:30 New York: after the close
    execution.record_equity("paper", force=True)


def _cash(sid, amount, flow=False):
    if flow:
        db.run("UPDATE ledger SET cash=cash+?, cap_in=cap_in+? WHERE mode='paper' AND strategy=?", (amount, amount, sid))
    else:
        db.run("UPDATE ledger SET cash=cash+? WHERE mode='paper' AND strategy=?", (amount, sid))


@pytest.fixture
def story(clean, clock):
    """Two months: a gains, b loses, c gets $1,000 more money (not a profit) on 29 Oct."""
    a, b, c = [s.id for s in S.all_instances()][:3]
    _close(clock, 2026, 10, 27)
    _cash(a, 100); _close(clock, 2026, 10, 28)
    _cash(b, -50); _cash(c, 1000, flow=True); _close(clock, 2026, 10, 29)
    _cash(a, 30); _close(clock, 2026, 10, 30)
    _cash(b, -20); _close(clock, 2026, 11, 2)
    _cash(a, 10); _close(clock, 2026, 11, 3)
    clock.set(datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc))      # 10:00 New York, Wednesday: month to date
    _cash(a, 5)
    return a, b, c


def test_months_add_up_like_a_statement(story):
    r = pnlreport.build("paper")
    ms = {m["m"]: m for m in r["months"]}
    assert list(ms) == ["2026-10", "2026-11"]
    oct_, nov = ms["2026-10"], ms["2026-11"]
    assert oct_["pnl"] == pytest.approx(80) and nov["pnl"] == pytest.approx(-5)
    for m in r["months"]:
        assert m["start"] + m["flow"] + m["pnl"] == pytest.approx(m["end"], abs=0.02)
    assert nov["start"] == pytest.approx(oct_["end"])
    assert oct_["flow"] == pytest.approx(oct_["end"] - 80)                  # all the money put in, incl. the $1,000
    assert nov["flow"] == pytest.approx(0) and nov["to_date"] and not oct_["to_date"]
    assert oct_["up"] == 2 and oct_["down"] == 1 and nov["up"] == 1 and nov["down"] == 1
    assert oct_["best"]["pnl"] == pytest.approx(100) and oct_["worst"]["pnl"] == pytest.approx(-50)
    assert 0 < oct_["ret"] < 0.01 and -0.001 < nov["ret"] < 0


def test_since_start_is_the_dashboard_number(story):
    r = pnlreport.build("paper")
    s = r["since"]
    assert s["pnl"] == pytest.approx(views.pnl_breakdown("paper", "all")["total"], abs=0.01)
    assert s["pnl"] == pytest.approx(views.dashboard("paper")["bot"]["pnl"], abs=0.01)
    assert s["pnl"] == pytest.approx(sum(m["pnl"] for m in r["months"]), abs=0.02)
    assert s["worth"] - s["put_in"] == pytest.approx(s["pnl"], abs=0.02)
    assert s["first"] == "2026-10-27" and s["last"] == "2026-11-04" and s["days"] == 6
    assert (1 + r["months"][0]["ret"]) * (1 + r["months"][1]["ret"]) - 1 == pytest.approx(s["ret"])


def test_strategy_rows_add_up_to_each_month(story):
    a, b, c = story
    r = pnlreport.build("paper")
    by = {x["id"]: x for x in r["strategies"]}
    assert by[a]["months"] == {"2026-10": pytest.approx(130), "2026-11": pytest.approx(15)}
    assert by[b]["months"] == {"2026-10": pytest.approx(-50), "2026-11": pytest.approx(-20)}
    assert by[c]["months"] == {}                                             # money put in is not a profit
    for m in r["months"]:
        assert sum(x["months"].get(m["m"], 0) for x in r["strategies"]) == pytest.approx(m["pnl"], abs=0.02)
    assert r["timing"] == {}
    assert [x["pnl"] for x in r["strategies"]] == sorted(x["pnl"] for x in r["strategies"])


def test_csv_and_api(story):
    text = pnlreport.csv_text("paper")
    lines = text.strip().splitlines()
    assert lines[0].startswith("month,start_usd,put_in_usd,pnl_usd,return_pct")
    assert lines[1].startswith("2026-10,") and lines[2].startswith("2026-11,") and lines[3].startswith("since_start,")
    from fastapi.testclient import TestClient
    from app.main import app
    for t in ("users", "sessions", "login_attempts"):
        db.run(f"DELETE FROM {t}")
    with TestClient(app) as cl:
        assert cl.get("/api/pnl/report?mode=paper").status_code == 401
        assert cl.post("/api/setup", json={"username": "kemmachat", "password": "testpassword123"}).status_code == 200
        j = cl.get("/api/pnl/report?mode=paper").json()
        assert [m["m"] for m in j["months"]] == ["2026-10", "2026-11"] and j["since"]["pnl"] == pytest.approx(75, abs=0.02)
        res = cl.get("/api/pnl/report.csv?mode=paper")
        assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
        assert "profit-loss-by-month-paper.csv" in res.headers["content-disposition"]


def test_no_records_yet(clean, clock):
    db.run("DELETE FROM equity")
    r = pnlreport.build("test")
    assert r["months"] == [] and r["since"] is None and r["timing"] == {}
