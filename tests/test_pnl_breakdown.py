"""Dashboard: profit & loss by strategy. The rows must add up to the Dashboard's Today and Since start numbers."""
import pytest

from app import db, execution, views
from app import strategies as S


def _ids():
    return [s.id for s in S.all_instances()]


def test_rows_add_up_to_the_dashboard(clean, clock):
    ids = _ids()
    a, b, c = ids[0], ids[1], ids[2]
    execution.record_equity("paper", force=True)                     # yesterday's snapshot
    clock.advance(hours=20)
    # a gains $120, b loses $45.50, c gets $1,000 more money (a flow, not a profit)
    db.run("UPDATE ledger SET cash=cash+120 WHERE mode='paper' AND strategy=?", (a,))
    db.run("UPDATE ledger SET cash=cash-45.5 WHERE mode='paper' AND strategy=?", (b,))
    db.run("UPDATE ledger SET cash=cash+1000, cap_in=cap_in+1000 WHERE mode='paper' AND strategy=?", (c,))
    d = views.dashboard("paper")["bot"]

    t = views.pnl_breakdown("paper", "today")
    rows = {r["id"]: r for r in t["rows"]}
    assert rows[a]["pnl"] == pytest.approx(120) and rows[b]["pnl"] == pytest.approx(-45.5)
    assert rows[c]["pnl"] == pytest.approx(0)                         # money added today is not a profit
    assert t["total"] == pytest.approx(d["today"], abs=0.01) and t["pct"] == pytest.approx(d["today_pct"])
    assert sum(r["pts"] for r in t["rows"]) == pytest.approx(t["pct"])  # the points add up to the total %

    s = views.pnl_breakdown("paper", "all")
    assert s["total"] == pytest.approx(d["pnl"], abs=0.01) and s["pct"] == pytest.approx(d["ret"])
    assert sum(r["pnl"] for r in s["rows"]) == pytest.approx(d["pnl"], abs=0.01)
    r = {x["id"]: x for x in s["rows"]}[a]
    assert r["realised"] + r["open"] == pytest.approx(r["pnl"]) and r["pct"] == pytest.approx(r["pnl"] / r["cap_in"])
    # the running P&L ends at today's numbers, one point per snapshot plus now
    assert len(s["series"]["t"]) == len(s["series"]["lines"][a]) and s["series"]["lines"][a][-1] == pytest.approx(r["pnl"])
    w = views.pnl_breakdown("paper", "1w")
    assert w["series"]["lines"][a][0] == 0 and w["series"]["lines"][a][-1] == pytest.approx(120)


def test_strategy_with_no_money_keeps_its_loss(clean, clock):
    a = _ids()[0]
    db.run("UPDATE ledger SET cash=0, cap_out=cap_in-250 WHERE mode='paper' AND strategy=?", (a,))   # lost $250, rest taken out
    s = views.pnl_breakdown("paper", "all")
    r = {x["id"]: x for x in s["rows"]}[a]
    assert r["no_money"] and r["pnl"] == pytest.approx(-250)
    assert s["total"] == pytest.approx(views.dashboard("paper")["bot"]["pnl"], abs=0.01)


def test_api_and_bad_period(clean, clock):
    from fastapi.testclient import TestClient
    from app.main import app
    for t in ("users", "sessions", "login_attempts"):
        db.run(f"DELETE FROM {t}")
    with TestClient(app) as cl:
        assert cl.get("/api/pnl?mode=paper").status_code == 401
        assert cl.post("/api/setup", json={"username": "kemmachat", "password": "testpassword123"}).status_code == 200
        j = cl.get("/api/pnl?mode=paper&period=nonsense").json()
        assert j["period"] == "all" and "rows" in j and "series" in j
        assert cl.get("/api/pnl?mode=paper&period=today").status_code == 200


def test_over_time_keeps_regular_session_only(clean, clock):
    from datetime import datetime, timezone
    a = _ids()[0]
    for hhmm in ((13, 0), (15, 0), (21, 0), (23, 30)):            # 09:00, 11:00, 17:00 and 19:30 New York on Wed 21 Oct
        clock.set(datetime(2026, 10, 21, *hhmm, tzinfo=timezone.utc))
        execution.record_equity("paper", force=True)
    clock.set(datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc))
    s = views.pnl_breakdown("paper", "all")
    hours = [datetime.fromtimestamp(t, timezone.utc).hour for t in s["series"]["t"][:-1]]
    assert hours == [13, 15]                                      # the first snapshot, then only the regular session
    assert len(s["series"]["lines"][a]) == len(s["series"]["t"])


def test_cards_today_add_up_to_the_dashboard_today(clean, clock):
    """12 Nov 2026: the cards' Today summed to -$198.76 while the Dashboard said -$187.58, because the Dashboard counted from
    a snapshot 1.2 days back (Wednesday 17:00 New York) and the cards from Wednesday's last record. Both now use the latter."""
    from datetime import datetime, timezone
    ids = _ids()
    a, b = ids[0], ids[1]
    clock.set(datetime(2026, 11, 11, 21, 0, tzinfo=timezone.utc))         # Wed 16:00 New York
    execution.record_equity("paper", force=True)
    db.run("UPDATE ledger SET cash=cash+11.18 WHERE mode='paper' AND strategy=?", (a,))   # an after-hours move
    clock.set(datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc))          # Wed 22:00 New York: Wednesday's last record
    execution.record_equity("paper", force=True)
    db.run("UPDATE ledger SET cash=cash-119.05 WHERE mode='paper' AND strategy=?", (a,))
    db.run("UPDATE ledger SET cash=cash-79.71 WHERE mode='paper' AND strategy=?", (b,))
    clock.set(datetime(2026, 11, 13, 2, 47, tzinfo=timezone.utc))         # Thu 21:47 New York
    d = views.dashboard("paper")
    cards = sum((c["today"] or {}).get("pnl") or 0 for c in d["strategies"])
    assert d["bot"]["today"] == pytest.approx(-198.76, abs=0.01) and cards == pytest.approx(d["bot"]["today"], abs=0.01)
    assert views.pnl_breakdown("paper", "today")["total"] == pytest.approx(d["bot"]["today"], abs=0.01)
