"""Dashboard → Traded: last 3 US sessions, one line per strategy."""
from datetime import date, datetime, timezone

from app import db, traded

MON_BEFORE_OPEN = datetime(2026, 11, 23, 14, 0, tzinfo=timezone.utc)     # 21:00 Bangkok, Monday, before the US open
MON_AFTER_OPEN = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
FRI = int(datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc).timestamp())
WED = int(datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc).timestamp())


def _order(plan, sid, sym, side, q, px, t, cross=None, retry=0, plan_qty=None):
    db.run("INSERT INTO orders(plan_id,mode,strategy,lot,lots,symbol,side,qty,plan_qty,limit_price,scheduled_at,status,applied_qty,"
           "applied_value,fee,cross_with,updated_at,submitted_at,retry) VALUES(?,'live',?,1,5,?,?,?,?,?,?,'filled',?,?,?,?,?,?,?)",
           (plan, sid, sym, side, plan_qty or q, plan_qty or q, px, t, q, q * px, q * px * 0.00107, cross, t + 60, t, retry))


def _plan(sid, reason, to_state=None):
    sig = None
    if to_state:
        sig = db.run("INSERT INTO signals(strategy,t,kind,from_state,to_state,created_at) VALUES(?,?,?,?,?,?)",
                     (sid, FRI, "signal", "out", to_state, FRI)).lastrowid
    return db.run("INSERT INTO plans(mode,strategy,reason,status,created_at,signal_id) VALUES('live',?,?,'done',?,?)",
                  (sid, reason, FRI, sig)).lastrowid


def test_sessions():
    assert traded.sessions(MON_BEFORE_OPEN) == [date(2026, 11, 20), date(2026, 11, 19), date(2026, 11, 18)]
    assert traded.sessions(MON_AFTER_OPEN)[0] == date(2026, 11, 23)
    assert date(2026, 11, 26) not in traded.sessions(datetime(2026, 11, 27, 20, 0, tzinfo=timezone.utc))   # Thanksgiving


def test_build(clean):
    db.run("DELETE FROM orders WHERE mode='live'")
    p1 = _plan("usd_trend_split", "signal", "dip")
    for _ in range(2):
        _order(p1, "usd_trend_split", "USD", "BUY", 71, 43.31, FRI, plan_qty=71)
    _order(p1, "usd_trend_split", "USD", "BUY", 0, 43.31, FRI, plan_qty=71)          # 3 lots more never filled
    db.run("UPDATE orders SET applied_qty=0, applied_value=0, status='failed' WHERE applied_qty=0")
    for _ in range(2):
        db.run("INSERT INTO orders(plan_id,mode,strategy,lot,lots,symbol,side,qty,plan_qty,scheduled_at,status,retry) "
               "VALUES(?,'live','usd_trend_split',4,5,'USD','BUY',71,71,?,'skipped',0)", (p1, FRI))
    p2 = _plan("usd_ibs", "signal", "out")
    _order(p2, "usd_ibs", "GLD", "SELL", 4.91, 327.06, FRI, cross="qld_split_2c")
    p3 = _plan("usd_ibs", "rebalance")
    _order(p3, "usd_ibs", "USD", "BUY", 7, 43.35, FRI)
    p4 = _plan("usd_smh_ibs", "signal", "out")
    _order(p4, "usd_smh_ibs", "USD", "SELL", 161, 50.44, WED)
    r = traded.build("live", MON_BEFORE_OPEN)
    fri, thu, wed = r["days"]
    assert [fri["label"], thu["label"], wed["label"]] == ["Fri 20 Nov", "Thu 19 Nov", "Wed 18 Nov"]
    assert fri["last"] and not wed["last"] and thu["fills"] == 0 and thu["strategies"] == []
    assert fri["fills"] == 4 and fri["bought"] == round(142 * 43.31 + 7 * 43.35, 2) and fri["sold"] == round(4.91 * 327.06, 2)
    top = fri["strategies"][0]
    assert top["id"] == "usd_trend_split" and top["legs"][0]["qty"] == 142 and top["why"] == ["signal · dip"]
    ibs = next(s for s in fri["strategies"] if s["id"] == "usd_ibs")
    assert set(ibs["why"]) == {"signal · exit", "top-up"} and any(g["inside"] for g in ibs["legs"])
    assert fri["short"] and fri["short"][0]["id"] == "usd_trend_split" and fri["short"][0]["pct"] == 40   # 2 of 5 lots
    assert wed["strategies"][0]["legs"][0]["side"] == "SELL" and wed["strategies"][0]["why"] == ["signal · exit"]


from test_api import client  # noqa: E402,F401


def test_dashboard_has_traded(client):
    from test_api import sign_in
    sign_in(client)
    d = client.get("/api/dashboard?mode=paper").json()
    assert "traded" in d and len(d["traded"]["days"]) == 3
