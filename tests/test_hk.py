"""Hong Kong: symbols, board lots, HKEX price steps and hours; bot HKD; the Go-live Hong Kong test trade; Webull's HK order."""
from datetime import datetime, timezone

import pytest

from app import brokers, db, golive, hk, ledger, marketdata as md, moneyops, testtrade as T
from test_api import client, sign_in  # noqa: F401  (fixture)

HK_OPEN = datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)        # Wed 10:00 Hong Kong
HK_LUNCH = datetime(2026, 10, 21, 4, 30, tzinfo=timezone.utc)       # 12:30 Hong Kong
HK_NIGHT = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)       # 23:00 Hong Kong (US open)


def prices():
    md.set_quote("7234", 5.22)
    md.set_quote("7226", 2.22)
    md.set_quote("7233", 3.694)


def test_symbols_lots_and_ticks():
    assert hk.is_hk("7234") and hk.is_hk("07234") and hk.is_hk("7234.HK") and not hk.is_hk("QLD")
    assert hk.norm("07234") == "7234" and hk.api_symbol("7234") == "07234" and md.yahoo_ticker("7234") == "7234.HK"
    assert hk.lot("7226") == 100
    assert hk.tick(0.2) == 0.001 and hk.tick(2.22) == 0.01 and hk.tick(15) == 0.02 and hk.tick(150) == 0.1
    assert hk.round_price(5.2234, "BUY") == 5.23 and hk.round_price(5.2299, "SELL") == 5.22
    assert hk.round_price(0.2213, "BUY") == 0.222
    assert hk.money(1234.5, "7234") == "HK$1,234.50" and hk.money(12, "QLD") == "$12.00"


def test_hours():
    assert hk.is_open(HK_OPEN) and not hk.is_open(HK_LUNCH) and not hk.is_open(HK_NIGHT)
    assert not hk.is_open(datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc))      # Chung Yeung holiday (Mon)
    nxt = hk.next_open(HK_NIGHT)
    assert nxt.strftime("%Y-%m-%d %H:%M") == "2026-10-22 09:30"
    assert "08:30" in hk.status(HK_NIGHT)["text"]                                   # Bangkok time shown


def test_bot_hkd_in_and_out(clean):
    acct = brokers.get("paper").account()
    assert acct["cash_hkd"] == 100000
    with pytest.raises(ValueError):
        ledger.hk_fund_in("paper", 200000, acct["cash_hkd"])
    moneyops.hkd_to_bot("paper", 1500)
    assert ledger.hk_cash("paper") == 1500 and ledger.pool_cash("paper") == 0     # USD books untouched
    assert ledger.hk_outside("paper", acct["cash_hkd"]) == 98500
    moneyops.hkd_to_webull("paper", 500)
    assert ledger.hk_cash("paper") == 1000
    m = db.rows("SELECT kind, amount, ccy FROM money WHERE mode='paper' ORDER BY id")
    assert [(r["kind"], r["ccy"]) for r in m][-2:] == [("to_bot", "HKD"), ("to_webull", "HKD")]


def test_paper_convert(clean):
    usd0 = brokers.get("paper").account()["cash"]
    out = moneyops.paper_convert(100, rate=7.8)
    a = brokers.get("paper").account()
    assert out["cash_hkd"] == 100780 and a["cash"] == pytest.approx(usd0 - 100)


def test_paper_broker_board_lots(clean):
    prices()
    b = brokers.get("paper")
    with pytest.raises(brokers.BrokerRejected):
        b.place("7234", "BUY", 50, 5.3, "CORE", "hk-odd")
    b.place("7234", "BUY", 100, 5.3, "CORE", "hk-lot")
    a = b.account()
    assert a["positions"]["7234"]["qty"] == 100 and a["positions"]["7234"]["currency"] == "HKD"
    assert a["cash_hkd"] < 100000 - 500 and a["market_value"] == 0             # HKD never added to the USD figures


def test_hk_round_trip_paid_from_bot_hkd(clean, clock):
    clock.set(HK_OPEN)
    prices()
    moneyops.hkd_to_bot("paper", 1500)
    usd_pool = ledger.pool_cash("paper")
    T.start("paper", ["7234"])
    for _ in range(4):
        clock.advance(seconds=30)
        T.tick("paper")
    t = db.one("SELECT * FROM test_trades WHERE symbol='7234'")
    assert t["status"] == "ok" and t["bought"] == 100 and t["sold"] == 100
    cost = t["buy_value"] - t["sell_value"] + t["buy_fee"] + t["sell_fee"]
    assert 0 < cost < 5
    assert ledger.hk_cash("paper") == pytest.approx(1500 - cost, abs=0.01)
    assert ledger.pool_cash("paper") == usd_pool
    assert "HK$" in t["result"]
    st = T.hk_status("paper")
    assert st["7234"]["state"] == "ok" and st["7226"]["state"] is None
    rep = golive.report("paper")
    sec = next(s for s in rep["sections"] if s["id"] == "hk")
    assert sec["counted"] is False and next(i for i in sec["items"] if i["key"] == "hk_7234")["status"] == "ok"
    assert rep["total"] == sum(len(s["items"]) for s in rep["sections"] if s.get("counted", True))


def test_hk_waits_for_hong_kong_hours_and_needs_hkd(clean, clock):
    clock.set(HK_NIGHT)
    prices()
    T.start("paper", ["7226"])
    t = db.one("SELECT * FROM test_trades WHERE symbol='7226'")
    assert t["status"] == "queued" and "Hong Kong market closed" in (t["error"] or "")
    clock.set(HK_OPEN)
    T.tick("paper")
    t = db.one("SELECT * FROM test_trades WHERE symbol='7226'")
    assert t["status"] == "failed" and "bot HKD" in t["result"]
    assert T.hk_status("paper")["7226"]["state"] is None                         # no Webull answer: not a verdict


def test_hk_rules(clean):
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["7234", "QLD"])
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["7234"], qty=3)
    with pytest.raises(T.TestTradeError):
        T.start("paper", ["7234"], fractional=True)


def test_refused_hk_order_is_recorded_with_a_hint(clean, clock):
    class NoHK(brokers.PaperBroker):
        def place(self, symbol, side, qty, limit, session, cid):
            if hk.is_hk(symbol):
                raise brokers.parse_rejection("HTTP Status: 417, Code: OPENAPI_MARKET_NOT_SUPPORT, Msg: market not supported")
            return super().place(symbol, side, qty, limit, session, cid)
    brokers.set_override("paper", NoHK())
    try:
        clock.set(HK_OPEN)
        prices()
        moneyops.hkd_to_bot("paper", 1500)
        T.start("paper", ["7233"])
        r = T.hk_status("paper")["7233"]
        assert r["state"] == "refused" and "OPENAPI_MARKET_NOT_SUPPORT" in r["code"] and "Webull Thailand" in r["hint"]
        assert ledger.hk_cash("paper") == 1500
        assert "7233" not in X_blocked()
    finally:
        brokers.set_override("paper", None)


def X_blocked():
    from app import execution
    return execution.blocked_symbols("paper")


def test_webull_hk_order_shape():
    o = brokers.WebullBroker.hk_order("7234", "BUY", 100, 5.2234, "cid1")
    assert o["symbol"] == "07234" and o["market"] == "HK" and o["order_type"] == "ENHANCED_LIMIT"
    assert o["limit_price"] == "5.23" and o["quantity"] == "100" and "support_trading_session" not in o
    assert "no_party_ids" not in o
    o = brokers.WebullBroker.hk_order("7226", "SELL", 100, 2.2299, "cid2", party_id="ABC123.2568")
    assert o["limit_price"] == "2.22" and o["no_party_ids"][0]["party_id"] == "ABC123.2568"
    with pytest.raises(brokers.BrokerRejected):
        brokers.WebullBroker.hk_order("7226", "BUY", 100, None, "cid3")


def test_webull_account_reads_hkd(monkeypatch):
    b = brokers.WebullBroker(env="test")
    bal = {"account_currency_assets": [{"currency": "USD", "cash_balance": "1000", "net_liquidation_value": "1500"},
                                       {"currency": "HKD", "cash_balance": "2345.6"}]}
    pos = [{"symbol": "07234", "market": "HK", "quantity": "100", "last_price": "5.2", "market_value": "520"},
           {"symbol": "QLD", "quantity": "5", "last_price": "100", "market_value": "500"}]
    monkeypatch.setattr(b, "raw_account", lambda: ("A1", bal, pos))
    monkeypatch.setattr(b, "_touch", lambda: None)
    a = b.account()
    assert a["cash"] == 1000 and a["cash_hkd"] == 2345.6
    assert a["positions"]["7234"]["currency"] == "HKD" and a["positions"]["QLD"]["currency"] == "USD"
    assert a["market_value_hkd"] == 520


def test_money_api_hkd(client, clean):
    sign_in(client)
    r = client.post("/api/money/hkd-to-bot", json={"mode": "paper", "amount": 1000})
    assert r.status_code == 200 and r.json()["hkd"] == 1000
    d = client.get("/api/money?mode=paper").json()
    assert d["hkd"]["bot_hkd"] == 1000 and d["hkd"]["account_hkd"] == 100000
    assert all((m.get("ccy") or "USD") == "USD" for m in d["moves"])
    assert client.post("/api/money/paper-convert", json={"mode": "test", "amount": 10}).status_code == 400
    tt = client.get("/api/testtrade?mode=paper").json()
    assert [s["symbol"] for s in tt["hk"]["symbols"]] == ["7234", "7226", "7233"]
