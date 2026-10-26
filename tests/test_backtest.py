"""Backtest: the strategy's own signals, traded at the bot's times, on total-return prices."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from app import backtest as BT, db, marketdata as md, markethours as mh
from app import strategies as S
from conftest import NOW


@pytest.fixture(scope="module")
def results():
    BT._cache.clear()
    return {s.id: BT.run(s.id, now=NOW) for s in S.all_instances()}


def test_every_strategy_runs(results):
    for sid, r in results.items():
        assert r["ok"], (sid, r.get("error"))
        m = r["stats"]["MAX"]["strategy"]
        assert m["years"] > 0.5 and m["maxdd"] <= 0 and "MAX" in r["ranges"]
        assert len(r["series"]["t"]) == len(r["series"]["strategy"]) == len(r["series"]["dd"])
        assert r["series"]["strategy"][0] == pytest.approx(BT.START_CASH)


def test_always_in_equals_buy_and_hold(results):
    r = results["qld_regime"]                         # the demo QQQ only rises: always "2x" = 99% QLD
    if r["stats"]["MAX"]["strategy"]["trades"]:
        pytest.skip("demo data changed state")
    s, b = r["series"]["strategy"], r["series"]["bench"]["QLD"]
    # bought at the 2nd day's open with 99% of the money; the rest stays cash
    assert s[-1] / s[1] == pytest.approx(0.99 * b[-1] / b[1] + 0.01 * s[1] / s[1], rel=0.03)


def test_daily_trades_fill_at_next_open(results):
    r = results["semis_regime"]
    trades = [t for t in r["trades"] if t["kind"] != "START"]
    assert trades
    usd = md._csv("USD", "1d")
    opens = {pd.Timestamp(t).date(): o for t, o in zip(usd.index, usd["o"])}
    for t in trades[:5]:
        d = datetime.fromtimestamp(t["t"], timezone.utc).astimezone(md.NY).date()
        assert t["prices"]["USD"] == pytest.approx(opens[d], rel=1e-6)
        assert datetime.fromtimestamp(t["t"], timezone.utc).astimezone(md.NY).strftime("%H:%M") == "09:30"


def test_metals_fills_follow_the_execution_rules(results):
    r = results["gold_sta"]
    trades = [t for t in r["trades"] if t["kind"] in ("BUY", "SELL")]
    assert trades
    for t in trades:
        ts = datetime.fromtimestamp(t["t"], timezone.utc)
        assert mh.is_open(ts, "CORE")                                    # only while the US market is open
        if t["kind"] == "BUY":
            bkk = ts.astimezone(mh.BKK)
            assert bkk.hour >= 22 or bkk.hour < 4                        # entries not before 22:00 Bangkok


def test_costs_and_ranges(results):
    r = results["gold_st30"]
    assert r["fees"] > 0 and r["cost_pct"] == pytest.approx(0.11)          # Webull TH 0.107% (default setting)
    one = r["stats"]["1Y"]["strategy"]
    assert 0.9 < one["years"] < 1.1
    assert {"year", "strategy"} <= set(r["years"][0])


def test_fee_setting_changes_the_result():
    a = BT.run("gold_st30", now=NOW)
    db.set_settings({"backtest_cost_pct": "0.30"})
    try:
        b = BT.run("gold_st30", now=NOW)
    finally:
        db.set_settings({"backtest_cost_pct": "0.11"})
    assert b["cost_pct"] == pytest.approx(0.30)
    assert b["fees"] > a["fees"] * 2
    assert b["stats"]["MAX"]["strategy"]["cagr"] < a["stats"]["MAX"]["strategy"]["cagr"]
    assert BT.run("gold_st30", now=NOW, cost=0.0005)["cost_pct"] == pytest.approx(0.05)


def test_try_other_settings_is_not_saved():
    a = BT.run("gold_st30", now=NOW)
    b = BT.run("gold_st30", params={"atr": 10, "mult": 1.5}, now=NOW)
    assert b["ok"] and b["custom"] and b["stats"]["MAX"]["strategy"]["trades"] > a["stats"]["MAX"]["strategy"]["trades"]
    assert S.get("gold_st30").params["atr"] == 30


def test_research_numbers_shown_for_default_settings(results):
    assert results["qld_tbd"]["research"]["cagr"] == 32.9 and results["qld_tbd"]["research"]["same_settings"]
    assert BT.run("qld_tbd", params={"rsi_buy": 10}, now=NOW)["research"]["same_settings"] is False
