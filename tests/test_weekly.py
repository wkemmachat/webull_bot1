"""Weekly report: real vs backtest per strategy, fees and fills vs the day's open."""
from datetime import date, datetime, timezone

import pytest

from app import brokers, db, execution as X, ledger, weekly
from app import strategies as S
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)
from test_execution import run_until_done


def test_week_window():
    wed = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
    assert weekly.week_window(wed) == (date(2026, 10, 19), date(2026, 10, 21))
    sat = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)                  # Saturday morning Bangkok
    assert weekly.week_window(sat) == (date(2026, 10, 19), date(2026, 10, 23))


def test_span_uses_the_value_before_the_week():
    days = [date(2026, 10, 16), date(2026, 10, 19), date(2026, 10, 20)]
    assert weekly._span(days, [100, 102, 105], date(2026, 10, 19), date(2026, 10, 23)) == (100, 105)
    assert weekly._span(days[1:], [102, 105], date(2026, 10, 19), date(2026, 10, 23)) == (102, 105)


def test_cost_vs_open_sign():
    fl = [{"value": 1000.0, "fee": 1.07, "cost": 5.0, "open": 100.0, "qty": 10},
          {"value": 990.0, "fee": 1.06, "cost": -1.0, "open": 100.0, "qty": 10}]
    c = weekly.cost_summary(fl)
    assert c["fills"] == 2 and c["cost"] == 4.0 and c["cost_pct"] == pytest.approx(4.0 / 2000) and c["fees"] == 2.13


def test_build_and_send(clean, clock):
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    db.run("UPDATE orders SET submitted_at=?", (int(NOW.timestamp()) - 86400,))   # wall-clock times → a test day with a daily bar
    X.record_equity("paper", clock.dt, force=True)
    r = weekly.send("paper", clock.dt, line=True)
    names = {x["id"] for x in r["strategies"]}
    assert "qld_regime" in names
    q = next(x for x in r["strategies"] if x["id"] == "qld_regime")
    assert q["backtest"] is not None
    assert r["fills"] and all(f["open"] for f in r["fills"])
    assert r["week_costs"]["fills"] == len(r["fills"]) and r["week_costs"]["fees"] > 0
    assert "Weekly report · Paper" in r["text"] and "QLD regime" in r["text"]
    assert weekly.stored("paper")[0]["week"] == r["week"]
    assert db.one("SELECT COUNT(*) n FROM line_queue WHERE event='weekly'")["n"] == 1
    weekly.send("paper", clock.dt, line=False)
    assert len(weekly.stored("paper")) == 1                               # same week replaces


def test_api(client):
    sign_in(client)
    w = client.get("/api/weekly?mode=paper").json()
    assert "reports" in w and "costs" in w
    r = client.post("/api/weekly/send", json={"mode": "paper", "line": False})
    assert r.status_code == 200 and "Weekly report" in r.json()["text"]
