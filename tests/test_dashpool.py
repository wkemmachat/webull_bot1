"""Dashboard v2 (strategy pool on) and the 2x ETF watch (28 Nov 2026)."""
import time

import numpy as np
import pandas as pd

from app import db, etfwatch, execution, ledger, pool
from app import strategies as S
from conftest import NOW

MODE = "paper"


def _on(members):
    pool.set_members(MODE, members)
    pool.set_settings(MODE, on_=True, slot=15.0, cap=25.0, minp=2.0)


def test_bot_value_counts_the_pool_cash(clean, clock):
    """27 Nov (Live): with all the money in the pool the Dashboard showed $0.05 and −100%."""
    with db.tx() as c:
        c.execute("DELETE FROM ledger WHERE mode=?", (MODE,))
        c.execute("DELETE FROM holdings WHERE mode=?", (MODE,))
    ledger.pool(MODE)
    db.run("UPDATE pool SET cash=? WHERE mode=?", (40_000.0, MODE))
    _on(["qld_split_2c"])
    execution.record_equity(MODE, NOW, force=True)
    r = db.one("SELECT value, capital FROM equity WHERE mode=? AND strategy='*' ORDER BY t DESC LIMIT 1", (MODE,))
    assert r["value"] == 40_000.0 and r["capital"] == 40_000.0


def test_repair_adds_the_pool_cash_to_records_since_the_pool_started(clean):
    with db.tx() as c:
        c.execute("DELETE FROM ledger WHERE mode=?", (MODE,))
        c.execute("DELETE FROM equity WHERE mode=?", (MODE,))
    ledger.pool(MODE)
    db.run("UPDATE pool SET cash=? WHERE mode=?", (39_000.0, MODE))
    _on(["qld_split_2c"])
    t0 = pool.since(MODE)
    ledger.credit(MODE, "qld_split_2c", 1_000)
    db.run("UPDATE ledger SET cap_in=1000 WHERE mode=? AND strategy='qld_split_2c'", (MODE,))
    for t, v, c in ((t0 - 3600, 39_500, 40_000), (t0 + 600, 1_010, 1_000), (t0 + 1200, 1_020, 1_000)):
        db.run("INSERT INTO equity(mode,t,strategy,value,capital,bench) VALUES(?,?,?,?,?,?)", (MODE, t, "*", v, c, c))
    assert pool.repair_equity(MODE) == 2
    rows = db.rows("SELECT t, value, capital FROM equity WHERE mode=? AND strategy='*' ORDER BY t", (MODE,))
    assert rows[0]["value"] == 39_500                                   # before the pool: unchanged
    assert rows[1]["capital"] == 40_000 and rows[1]["value"] == 40_010   # K = pool cash 39,000 + strategy net 1,000
    assert pool.repair_equity(MODE) == 0                                 # once per pool start


def test_backtest_ranges():
    idx = pd.date_range("2010-01-31", periods=60, freq="ME")
    v = pd.Series(100 * np.cumprod(np.r_[1, np.full(59, 1.01)]), index=idx)
    r = pool.ranges(v)
    assert r["bands"][0][0] == 1 and abs(r["bands"][0][2] - 1.0) < 0.01 and r["m_up"] == 100 and r["y_down"] == 0


def test_dashboard_api_pool_layout(clean, clock):
    from fastapi.testclient import TestClient
    from app import main
    _on(["qld_split_2c", "usd_trend_split"])
    main.app.dependency_overrides[main.user] = lambda: {"id": 1}
    try:
        d = TestClient(main.app).get("/api/dashboard?mode=paper").json()
    finally:
        main.app.dependency_overrides.clear()
    assert "dash" in d, d.get("dash_error")
    ds = d["dash"]
    assert {"pool", "check", "attention", "plans"} <= set(ds) and ds["check"]["too_early"] is True
    assert isinstance(ds["attention"]["items"], list) and isinstance(ds["attention"]["ok"], list)


def test_month_rows_mark_the_months_before_the_pool():
    from datetime import date
    from app import dashpool
    days = [date(2026, 10, 27), date(2026, 10, 27), date(2026, 10, 31), date(2026, 11, 20), date(2026, 11, 27)]
    idx = [1.0, 1.0, 0.95, 0.90, 0.92]
    m = dashpool._month_rows(days, idx, date(2026, 11, 27))
    assert [(r["m"], round(r["ret"], 4)) for r in m] == [(10, -0.05), (11, round(0.92 / 0.95 - 1, 4))]
    assert m[0]["before_pool"] and m[1]["mixed"] and m[1]["partial"]


# ---------------------------------------------------------------- 2x ETF watch
def _fake(monkeypatch, search, volumes, first=None):
    monkeypatch.setattr(etfwatch, "_search", lambda q: search.get(q, []))
    monkeypatch.setattr(etfwatch, "_download", lambda ts: {t: volumes[t] for t in ts if t in volumes})
    monkeypatch.setattr(etfwatch, "_first_trade", lambda t: (first or {}).get(t, int(time.time()) - 5 * 31_557_600))
    monkeypatch.setattr(etfwatch, "_quote_type", lambda s: "EQUITY" if s in ("NVDA", "TSLA") else "ETF")
    monkeypatch.setattr(etfwatch.time, "sleep", lambda s: None)


def _vol(m):
    return {"adv90": m * 1e6, "adv10": m * 1e6, "price": 20.0, "first": 0, "days": 180}


def test_etf_watch_first_run_then_new_and_left(clean, monkeypatch):
    for k in ("etfwatch:known", "etfwatch:last", "etfwatch:log", "etfwatch:marks"):
        db.set_state(k, None)
    seed = [t for t, (a, g, r) in etfwatch.SEED.items() if g != "Crypto"]
    vols = {t: _vol(100 - i) for i, t in enumerate(seed)}                 # seed order = rank order
    _fake(monkeypatch, {}, vols)
    sent = []
    monkeypatch.setattr(etfwatch.notify, "send", lambda ev, text, **k: sent.append(text))
    r = etfwatch.check()
    assert r["first_run"] and len(r["top"]) == 50 and not r["new"] and not sent
    # week 2: a new 2x index fund is listed, a single-stock, an inverse and a crypto fund are ignored, #51 overtakes #50
    young = int(time.time()) - 20 * 86400
    search = {"2X Long ETF": [
        {"symbol": "ABCX", "name": "ProShares Ultra Example Global Semis", "type": "ETF"},
        {"symbol": "NVDZ", "name": "Tradr 2X Long NVDA Daily ETF", "type": "ETF"},
        {"symbol": "SQQX", "name": "ProShares UltraShort QQQ", "type": "ETF"},
        {"symbol": "BTCZ", "name": "2X Bitcoin Strategy ETF", "type": "ETF"}]}
    vols["ABCX"] = _vol(1.9)
    vols[seed[50]] = _vol(200)                                             # #51 jumps to the top
    _fake(monkeypatch, search, vols, {"ABCX": young})
    r = etfwatch.check()
    new = {n["t"]: n for n in r["new"]}
    assert set(new) == {"ABCX", seed[50]} and new["ABCX"]["kind"] == "listing" and new[seed[50]]["kind"] == "entered"
    assert [x["t"] for x in r["left"]] == [seed[49]]                       # pushed from #50 to #51
    k = etfwatch.known()
    assert k["NVDZ"]["group"] == "Single stock" and k["BTCZ"]["group"] == "Crypto" and "SQQX" not in k
    assert sent and "ABCX" in sent[0]
    v = etfwatch.mark("ABCX", "research")
    assert next(n for n in v["new"] if n["t"] == "ABCX")["status"] == "to_research"
    etfwatch.mark("ABCX", "dismissed")
    assert all(n["t"] != "ABCX" for n in etfwatch.brief()["new"])


def test_etf_watch_status_follows_the_bot(clean, monkeypatch):
    k = etfwatch.known()
    assert etfwatch._status("QLD", k, {}) in ("pool", "bot")
    assert etfwatch._status("DGP", k, {}) == "not_researched"
    assert etfwatch._status("BOIL", k, {}) == "researched"


def test_etf_watch_runs_on_saturday_morning_bangkok(clean):
    from datetime import datetime, timezone
    db.set_state("etfwatch:done", None)
    sat_early = datetime(2026, 11, 28, 2, 0, tzinfo=timezone.utc)          # 09:00 Bangkok
    sat = datetime(2026, 11, 28, 2, 45, tzinfo=timezone.utc)               # 09:45 Bangkok
    assert not etfwatch.due(sat_early) and etfwatch.due(sat) and not etfwatch.due(sat)


def test_dashboard_on_a_saturday_with_the_weekend_pause(clean, monkeypatch):
    """28 Nov (Saturday 08:00+): the next LINE digest was "Mon 08:00" and parsing it as "HH:MM" failed the whole Dashboard."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app import notify, views
    sat = datetime(2026, 11, 28, 8, 37, tzinfo=ZoneInfo("Asia/Bangkok"))
    t = notify.next_digest_at(sat)
    assert t is not None and t.weekday() == 0                       # Monday
    assert notify.next_digest(sat).startswith("Mon ")
    monkeypatch.setattr(notify, "next_digest_at", lambda now=None: t)
    items = views.next_up("paper", [], [])
    assert any(i["title"] == "LINE digest" and i["t"] == int(t.timestamp()) for i in items)


def test_non_finite_numbers_never_reach_the_response():
    from app import views
    assert views._finite({"a": float("nan"), "b": [1.0, float("inf")], "c": "x"}) == {"a": None, "b": [1.0, None], "c": "x"}


def test_pnl_card_percent_counts_the_pool_cash(clean, clock):
    """28 Nov (Live): the Profit & loss card still said −100% with all the money in the pool."""
    from app import views
    with db.tx() as c:
        c.execute("DELETE FROM ledger WHERE mode=?", (MODE,))
        c.execute("DELETE FROM holdings WHERE mode=?", (MODE,))
    ledger.pool(MODE)
    db.run("UPDATE pool SET cash=? WHERE mode=?", (39_000.0, MODE))
    ledger.credit(MODE, "qld_split_2c", 0)
    db.run("UPDATE ledger SET cap_in=1000, cap_out=0, cash=900 WHERE mode=? AND strategy='qld_split_2c'", (MODE,))
    _on(["qld_split_2c"])
    d = views.pnl_breakdown(MODE, "all")
    assert d["pool_cash"] == 39_000.0 and abs(d["total"] - -100) < 0.01
    assert abs(d["pct"] - (-100 / 40_000)) < 1e-9                        # not −100 / 1,000
