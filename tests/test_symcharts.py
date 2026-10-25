"""Charts by symbol for the stock-basket strategies: candles + the backtest's buys/sells."""
import pytest

from app import symcharts


@pytest.mark.parametrize("sid", ["c27_mom", "c27_mom2x"])
def test_symbol_list_and_chart(sid):
    d = symcharts.build(sid)
    assert d["ok"] and d["symbols"][0]["kind"] == "signal"
    kinds = {r["kind"] for r in d["symbols"]}
    assert "parking" in kinds and ({"stock", "2x ETF"} & kinds)
    assert d["candles"] and d["markers"]
    for r in d["symbols"][:6]:
        x = symcharts.build(sid, r["sym"])
        assert x["sym"] == r["sym"] and x["candles"]
        if r["kind"] != "signal":
            buys = [e for e in x["events"] if e["side"] == "BUY"]
            sells = [e for e in x["events"] if e["side"] == "SELL"]
            assert 0 <= len(buys) - len(sells) <= 1                 # buys and sells alternate
            assert len(x["trips"]) == len(buys)
            times = {c["time"] for c in x["candles"]}
            assert all(m["time"] in times for m in x["markers"])


def test_signal_chart_marks_on_and_off():
    x = symcharts.build("c27_mom", "QQQ")
    sides = [e["side"] for e in reversed(x["events"])]
    assert sides and all(a != b for a, b in zip(sides, sides[1:]))      # on/off alternate
    assert all(e["day"] < e["fill_day"] for e in x["events"])          # signal on a close, trade at the next open


def test_unknown_symbol_and_non_basket():
    with pytest.raises(symcharts.ChartError):
        symcharts.build("c27_mom", "ZZZZ")
    with pytest.raises(symcharts.ChartError):
        symcharts.build("qld_regime")
