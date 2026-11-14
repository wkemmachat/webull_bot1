"""What each strategy holds (Dashboard → What your money is in → By strategy, Portfolio → Holdings by strategy)."""
import csv
import io

import pytest

from app import db, holdings, ledger, views
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)


def _setup():
    # USD Trend + IBS-dip: 11.88 GLD + cash; QLD Vol: all cash waiting for a buy signal; ROM: cash with a planned buy
    db.run("UPDATE ledger SET cash=4578.48, cap_in=9700 WHERE mode='paper' AND strategy='usd_ibs'")
    db.run("INSERT OR REPLACE INTO holdings(mode, strategy, symbol, qty) VALUES('paper','usd_ibs','GLD',11.88)")
    db.run("UPDATE ledger SET cash=7250, cap_in=7250, hold_cash=?, hold_amt=7250 WHERE mode='paper' AND strategy='qld_tbdv'",
           (int(NOW.timestamp()) - 3600,))
    db.run("UPDATE ledger SET cash=2000, cap_in=2000 WHERE mode='paper' AND strategy='rom_tbd'")
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,limit_price,status,updated_at,retry) "
           "VALUES(1,'paper','rom_tbd',1,1,2,'ROM','BUY',8,8,120,'scheduled',?,0)", (int(NOW.timestamp()),))


def test_rows_cash_by_reason_and_totals(clean):
    _setup()
    d = holdings.build("paper")
    r = {x["id"]: x for x in d["rows"]}
    assert set(r) >= {"usd_ibs", "qld_tbdv", "rom_tbd"} and all(x["total"] >= 0.5 for x in d["rows"])
    u = r["usd_ibs"]
    assert u["positions"]["GLD"]["qty"] == pytest.approx(11.88) and u["cash"] == pytest.approx(4578.48)
    assert u["total"] == pytest.approx(4578.48 + u["positions"]["GLD"]["value"])
    q = r["qld_tbdv"]
    assert q["waits"] == pytest.approx(7250) and q["rule_cash"] == pytest.approx(0)
    rom = r["rom_tbd"]
    assert rom["orders"] == pytest.approx(960) and rom["rule_cash"] == pytest.approx(1040)
    assert d["total"] == pytest.approx(sum(x["total"] for x in d["rows"]))
    gld = next(t for t in d["symbols"] if t["symbol"] == "GLD")
    assert gld["qty"] == pytest.approx(11.88) and gld["color"]
    db.run("UPDATE ledger SET cash=0 WHERE mode='paper' AND strategy='gold_st30'")
    db.run("DELETE FROM holdings WHERE mode='paper' AND strategy='gold_st30'")
    d = holdings.build("paper")
    assert any(e["id"] == "gold_st30" for e in d["empty"]) and "gold_st30" not in {x["id"] for x in d["rows"]}   # $0: listed apart
    assert d["account"] is None and d["not_bot"] is None                      # no account given


def test_not_the_bots_and_the_webull_check(clean):
    _setup()
    d0 = holdings.build("paper")
    gld_px = d0["symbols"][0]["value"] / 11.88
    acct = {"cash": d0["cash"] + 1493.18, "cash_hkd": 2300.71, "_at": 1,
            "positions": {"GLD": {"qty": 11.88, "last": gld_px, "value": 11.88 * gld_px},
                          "OMER": {"qty": 25, "last": 17.38, "cost": 11.40, "value": 434.5},
                          "ADVMCVR11WB": {"qty": 1500, "last": 0, "cost": 0, "value": 0}}}
    acct["total"] = acct["cash"] + sum(p["value"] for p in acct["positions"].values())
    d = holdings.build("paper", acct)
    assert d["account"]["check"] == [{"symbol": "GLD", "bot": pytest.approx(11.88), "account": 11.88, "status": "match"}]
    nb = d["not_bot"]
    assert [o["symbol"] for o in nb["items"]] == ["OMER", "ADVMCVR11WB"]
    om = nb["items"][0]
    assert om["value"] == pytest.approx(434.5) and om["pnl"] == pytest.approx(149.5) and om["pnl_pct"] == pytest.approx(17.38 / 11.4 - 1)
    assert nb["cash"] == pytest.approx(1493.18) and nb["hkd"] == 2300.71 and nb["total"] == pytest.approx(1927.68)
    assert d["account"]["adds_up"] and abs(d["account"]["gap"]) < 0.01
    acct["positions"]["GLD"]["qty"] = 12.88                                    # Webull holds 1 more GLD than the bot owns
    d = holdings.build("paper", acct)
    assert d["account"]["check"][0]["status"] == "extra" and d["not_bot"]["items"][0]["symbol"] == "GLD"


def test_api_csv_and_dashboard(client):
    sign_in(client)
    _setup()
    h = client.get("/api/holdings?mode=paper").json()
    assert "rows" in h and "symbols" in h
    r = client.get("/api/holdings.csv?mode=paper")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == holdings.CSV_COLS and any(x[3] == "GLD" for x in rows[1:]) and any(x[8] == "waits for a buy signal" for x in rows[1:])
    d = views.dashboard("paper")
    assert d["holdings"] and d["holdings"]["total"] == pytest.approx(sum(x["total"] for x in d["holdings"]["rows"]))
