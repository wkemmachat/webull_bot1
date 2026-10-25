"""Daily P&L per strategy (money moves left out) and the falls: depth, length, time underwater."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import db, perf
from app import strategies as S
from conftest import NOW


def test_drawdowns_depth_length_recovery():
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(9)]
    vals = [100, 110, 99, 88, 105, 111, 100, 105, 108]
    d = perf.drawdowns(days, vals)
    w = d["worst"]
    assert w["depth"] == pytest.approx(-20.0) and w["peak"] == "2026-01-02" and w["trough"] == "2026-01-04"
    assert w["recovered"] == "2026-01-06" and w["days_down"] == 2 and w["days_under"] == 4 and w["days_to_recover"] == 2
    assert d["current"]["depth"] == pytest.approx((108 / 111 - 1) * 100, abs=0.01) and d["current"]["since"] == "2026-01-06"
    assert d["top"][0]["depth"] <= d["top"][1]["depth"] and d["count_10"] == 1 and d["count_20"] == 1
    assert d["longest"]["days_under"] == 4 or d["longest"]["ongoing"]
    assert 0 < d["pct_under"] < 100
    assert perf.drawdowns(days[:1], vals[:1]) is None


def _equity(mode, sid, rows):
    with db.tx() as c:
        c.execute("DELETE FROM equity WHERE mode=? AND strategy=?", (mode, sid))
        c.executemany("INSERT INTO equity(mode,t,strategy,value,capital,bench) VALUES(?,?,?,?,?,?)",
                      [(mode, int(t.timestamp()), sid, v, c_, c_) for t, v, c_ in rows])


def test_daily_pnl_leaves_out_money_moves():
    mode, sid = "paper", "gold_sta"
    ny = lambda d, h: datetime(2026, 10, d, h, 0, tzinfo=timezone.utc)     # 20:00 UTC = 16:00 New York
    _equity(mode, sid, [
        (ny(16, 15), 9990, 10000), (ny(16, 20), 10000, 10000),          # Fri: first day, value = money in
        (ny(17, 20), 10000, 10000),                                     # Sat: not a trading day
        (ny(19, 20), 10200, 10000),                                     # Mon +200
        (ny(20, 20), 15300, 15000),                                     # Tue: +5,000 added, real gain +100
        (ny(21, 14), 15150, 15000)])                                    # Wed (today, so far) −150
    d = perf.daily(mode, sid)
    rows = {r["date"]: r for r in d["rows"]}
    assert "2026-10-17" not in rows
    assert rows["2026-10-19"]["pnl"] == pytest.approx(200) and rows["2026-10-19"]["pct"] == pytest.approx(0.02)
    t = rows["2026-10-20"]
    assert t["pnl"] == pytest.approx(100) and t["flow"] == pytest.approx(5000) and t["pct"] == pytest.approx(100 / 15200)
    assert t["total"] == pytest.approx(300)
    assert rows["2026-10-21"]["today"] and rows["2026-10-21"]["pnl"] == pytest.approx(-150)
    assert d["rows"][0]["date"] == "2026-10-21"                          # newest first
    assert d["stats"]["days"] == 3 and d["stats"]["up"] == 2
    tp = perf.today_pnl(mode, sid, 15150, 15000)
    assert tp["pnl"] == pytest.approx(-150) and tp["since"] == "2026-10-20"
    assert perf.today_pnl(mode, sid, 16150, 16000)["pnl"] == pytest.approx(-150)   # $1,000 added today is not profit
    assert tp["live"] is True
    # before the open the card shows the last completed session (Tue), not a fake "today"
    from app import marketdata as md
    md.set_clock(datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc))            # 08:00 New York
    try:
        pre = perf.today_pnl(mode, sid, 15150, 15000)
        assert pre["live"] is False and pre["day"] == "2026-10-20" and pre["pnl"] == pytest.approx(100)
    finally:
        md.set_clock(NOW)
    csv = perf.daily_csv(mode, sid)
    assert csv.splitlines()[0].startswith("date (US)") and "2026-10-21 (so far)" in csv and "5000.00" in csv
    # the time-weighted index ignores the deposit: +2% then +100/15200
    days, idx = perf.live_index(mode, sid)
    assert idx[days.index(date(2026, 10, 20))] == pytest.approx(1.02 * (1 + 100 / 15200))
    db.run("DELETE FROM equity WHERE mode=? AND strategy=?", (mode, sid))


def test_strategy_risk_from_backtest(monkeypatch):
    from app import backtest as BT
    BT._cache.clear()
    r = perf.strategy_risk("qld_regime", "paper")
    b = r["backtest"]
    assert b and b["worst"]["depth"] < 0 and b["underwater"] and b["top"]
    assert b["pct_under"] > 0 and r["research"]["source"]
    cs = perf.card_summary("qld_regime")
    assert cs["worst"] == b["worst"]["depth"]
    assert r["live"] is None or "worst" in r["live"]


def test_api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_api import sign_in
    db.run("DELETE FROM users"); db.run("DELETE FROM sessions"); db.run("DELETE FROM login_attempts")
    with TestClient(app) as c:
        sign_in(c)
        j = c.get("/api/strategies/usd_ibs/daily?mode=paper").json()
        assert "rows" in j and j["mode"] == "paper"
        r = c.get("/api/strategies/usd_ibs/daily.csv?mode=paper")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
        k = c.get("/api/strategies/qld_tbd/risk?mode=paper").json()
        assert k["backtest"]["worst"]["depth"] < 0
        s = c.get("/api/strategies?mode=paper").json()["strategies"]
        assert all("today" in x and "dd" in x for x in s)
        assert c.get("/api/strategies/nope/risk").status_code == 404
