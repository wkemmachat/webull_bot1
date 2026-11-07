"""Gold and silver backtests read OANDA spot before the bot's own futures bars; live signals never do."""
import pandas as pd
import pytest

from app import backtest as BT, metals
from conftest import NOW


@pytest.fixture
def history(monkeypatch):
    monkeypatch.setenv("METALS_HISTORY", "1")
    metals._cache.clear()
    BT._cache.clear()
    yield
    metals._cache.clear()
    BT._cache.clear()


def test_live_series_has_no_history_and_backtest_series_does(history):
    live = metals.series("GC", NOW)
    assert live["first_real"] is None
    with metals.long_history():
        lg = metals.series("GC", NOW)
    assert lg["first_real"] == live["raw1"].index[0]
    assert lg["raw1"].index[0] < pd.Timestamp("2006-04-01", tz="UTC")
    # the bot's own bars are untouched, and the spot years join them without a jump
    own = lg["raw1"][lg["raw1"].index >= lg["first_real"]]
    assert own["c"].equals(live["raw1"]["c"])
    before = lg["raw1"][lg["raw1"].index < lg["first_real"]]["c"]
    assert abs(before.iloc[-1] / own["c"].iloc[0] - 1) < 0.05
    assert metals.series("GC", NOW)["first_real"] is None              # outside a backtest: still the short series


def test_metals_backtest_goes_back_to_2008_and_says_so(history):
    r = BT.run("gold_st30", now=NOW)
    own = str(metals.series("GC", NOW)["raw1"].index[0].date())
    # it starts where the ETF's daily prices start (the test data's UGL: 2024), before the bot's own gold bars
    assert r["ok"] and r["data"]["from"] < own
    assert list(r["data"]["built"]) == ["GC=F"] and "OANDA" in r["data"]["built_from"] and "OANDA" in r["data"]["note"]


def test_switch_off_keeps_the_short_backtest(monkeypatch):
    monkeypatch.setenv("METALS_HISTORY", "0")
    metals._cache.clear(); BT._cache.clear()
    r = BT.run("gold_st30", now=NOW)
    assert r["data"]["from"] > "2024-01-01" and not r["data"]["built"]
