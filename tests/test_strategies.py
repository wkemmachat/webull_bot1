"""All six default strategies evaluate on the demo prices and give a sane target and chart."""
import pytest

from app import strategies as S
from conftest import NOW

IDS = ["gold_sta", "gold_st30", "silver_dc", "silver_st", "qld_regime", "semis_regime", "qld_tbd"]


def test_six_defaults_seeded():
    assert {r["id"] for r in S.rows()} >= set(IDS)


@pytest.mark.parametrize("sid", IDS)
def test_evaluate(sid):
    s = S.get(sid)
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    t = ev["target"]
    assert 0 <= sum(t.values()) <= 1.0 + 1e-9                     # 0 = flat in cash (metals since 26 Oct 2026)
    assert sum(t.values()) > 0 or s.family == "signal"
    assert set(t) <= set(s.trade_symbols()) | set(s.cash_target())
    assert ev["bar_time"] <= NOW.timestamp()


@pytest.mark.parametrize("sid", IDS)
def test_chart_has_indicators(sid):
    s = S.get(sid)
    spec = s.chart(NOW)
    charts = spec["charts"]
    assert charts and charts[0]["candles"]
    if s.type == "regime":
        assert len(charts) == 2                                   # the signal index AND the traded ETF
        assert {c["title"].split(" ")[0] for c in charts} == {s.params["signal"], s.params["trade"]}
        assert any(p for p in charts[0]["panes"])                 # volatility pane
    elif sid == "gold_sta":
        names = " ".join(l["name"] for l in charts[0]["lines"])
        assert "Supertrend" in names
        assert any("ADX" in p["title"] for p in charts[0]["panes"])


def test_gold_signal_uses_adx_filter():
    a, b = S.get("gold_sta"), S.get("gold_st30")
    assert a.params["adx_min"] == 20 and b.params.get("adx_min", 0) == 0
    ha, hb = a.evaluate(NOW)["history"], b.evaluate(NOW)["history"]
    # the ADX filter can only delay or skip entries, never add them
    assert len([h for h in ha if h["kind"] == "BUY"]) <= len([h for h in hb if h["kind"] == "BUY"]) + 1
