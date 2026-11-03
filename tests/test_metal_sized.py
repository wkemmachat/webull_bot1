"""Silver challengers S1 and S3 (type metal_trend_sized, "Gold & Silver Challengers", 3 Nov 2026): the bot's rule against
an independent restatement of the research rule, no look-ahead, sized and two-ETF targets in evaluate and the backtest, the
two new default strategies, and that the existing metals strategies are unchanged."""
import json

import numpy as np
import pandas as pd
import pytest

from app import backtest as BT, db, health, ledger, metals
from app import indicators as I
from app import strategies as S
from app.strategies.metal_trend import TrendSizedStrategy
from conftest import NOW

IDS = ("silver_gold_ok", "silver_lead_1x")


def series(sym):
    return metals.series(sym, NOW)["adj4"]


def research_targets(sv, g, p):
    """Research engine (stage3.combo with xfilter / gsr / 1x / size_from_vol) restated with pandas on the bot's 4H bars:
    returns (2x weight before the 1% buffer and before the resize band, 1x on)."""
    st = I.supertrend(sv.h.values, sv.l.values, sv.c.values, p["atr"], p["mult"])
    up = st["up"] & ~np.isnan(st["atr"])
    n = len(sv)
    ok = np.ones(n, bool)

    def sessions(b):
        ny = b.index.tz_convert("America/New_York")
        last = ny.hour == 14
        day = (ny + pd.Timedelta(hours=6)).normalize()
        return pd.Series(b.c.values[last], index=day[last]), np.cumsum(last) - 1
    dsv, ksv = sessions(sv)
    pick = lambda arr, fill: np.where(ksv >= 0, np.asarray(arr)[np.clip(ksv, 0, None)], fill)
    if p["gold_confirm"]:
        gs = I.supertrend(g.h.values, g.l.values, g.c.values, p["gold_atr"], p["gold_mult"])
        gup = gs["up"] & ~np.isnan(gs["atr"])
        ge = pd.to_datetime(g["end"], utc=True).values
        j = np.searchsorted(ge, pd.to_datetime(sv["end"], utc=True).values, side="right") - 1
        ok &= np.where(j >= 0, gup[np.clip(j, 0, None)], False)
    if p["daily_ma"]:
        ma = dsv.rolling(p["daily_ma"]).mean()
        ok &= pick((ma.isna() | (dsv > ma)).values, False).astype(bool)
    if p["gsr_ma"]:
        dg, _ = sessions(g)
        r = (dg.reindex(dsv.index) / dsv).ffill()
        rm = r.rolling(p["gsr_ma"]).mean()
        ok &= pick((rm.isna() | (r < rm)).values, False).astype(bool)
    v = np.log(dsv).diff().rolling(p["size_vol_days"]).std() * np.sqrt(252) * 2
    size = pick(np.where(v.isna(), 1.0, np.minimum(1.0, p["target_vol_pct"] / 100 / v)), 1.0)
    w2 = np.where(up & ok, size, 0.0)
    one = up & ~ok & bool(p["one_x_etf"])
    return w2, one


def test_two_defaults_seeded_quiet_without_live_money(clean):
    a, b = S.get("silver_gold_ok"), S.get("silver_lead_1x")
    assert a.type == b.type == "metal_trend_sized"
    assert a.params["gold_confirm"] is True and a.params["atr"] == 40 and a.params["target_vol_pct"] == 70 and a.params["size_vol_days"] == 40
    assert b.params["one_x_etf"] == "SLV" and b.params["gsr_ma"] == 100 and b.params["daily_ma"] == 100 and b.params["atr"] == 180
    assert ("GC", "1h") in a.data_needs() and ("GC", "1h") in b.data_needs()
    for sid in IDS:
        assert ledger.get("live", sid)["cap_in"] == 0 and not ledger.get("live", sid)["holdings"]
    db.run("DELETE FROM strategies WHERE id IN ('silver_gold_ok','silver_lead_1x')")
    db.set_state("seeded_defaults", [d[0] for d in S.DEFAULTS if d[0] not in IDS])
    assert sorted(S.seed()) == sorted(IDS)
    assert S.get("silver_gold_ok").row["line_on"] == 0 and S.get("silver_lead_1x").row["line_on"] == 0


@pytest.mark.parametrize("sid", IDS)
def test_rule_matches_the_research_rule(clean, sid):
    s = S.get(sid)
    sv, g = series("SI"), series("GC")
    res = s.compute(sv)
    w2, one = research_targets(sv, g, s.params)
    w0 = s.warmup()
    st_bot = np.where(res["size"].values > 0, 2, np.where(res["one_x"].values, 1, 0))[w0:]
    st_ref = np.where(w2 > 0, 2, np.where(one, 1, 0))[w0:]
    assert (st_bot == st_ref).all()
    # the size held follows the research size within the 10% resize band
    on = res["size"].values[w0:] > 0
    held, raw = res["size"].values[w0:][on], w2[w0:][on]
    assert (np.abs(held - raw) <= 0.1 * held + 0.006).all()


@pytest.mark.parametrize("sid", IDS)
def test_no_look_ahead(clean, sid):
    s = S.get(sid)
    sv = series("SI")
    full = s.compute(sv)
    for cut in (len(sv) - 1, len(sv) - 9, len(sv) - 77):
        part = s.compute(sv.iloc[:cut])
        for col in ("size", "one_x", "want"):
            assert (part[col].values == full[col].values[:cut]).all(), (cut, col)


@pytest.mark.parametrize("sid", IDS)
def test_evaluate_health_chart(clean, sid):
    s = S.get(sid)
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    t = ev["target"]
    assert t == {} or (list(t) == ["AGQ"] and 0 < t["AGQ"] <= 0.99) or t == {"SLV": 0.99}
    assert all(h["kind"] in ("BUY", "SELL", "SIZE") for h in ev["history"])
    for h in ev["history"][:3]:
        assert s.signal_message(h).split(" · ")[0] in ("BUY", "SELL", "RESIZE")
    tbl = health.indicator_table(s, NOW, rows=30)
    assert tbl["rows"] and all(r["ok"] for r in tbl["rows"]), tbl["rows"][:2]
    assert s.chart(NOW, "3M")["charts"]
    assert s.describe()["rules"]


def test_bar_targets_and_backtest_two_etfs(clean):
    s = S.get("silver_lead_1x")
    res = s.compute(series("SI"))
    tg = s.bar_targets(res)
    kinds = {tuple(sorted(t)) for t in tg}
    assert kinds <= {(), ("AGQ",), ("SLV",)}
    r = BT.run("silver_lead_1x", now=NOW)
    assert r["ok"], r.get("error")
    syms = {k for tr in r.get("trades", []) for k in list(tr.get("to", {})) + list(tr.get("from", {}))}
    assert syms <= {"AGQ", "SLV"}


def test_existing_metals_strategies_unchanged(clean):
    for sid, typ in (("gold_sta", "supertrend"), ("gold_st30", "supertrend"), ("silver_dc", "donchian"), ("silver_st", "supertrend")):
        s = S.get(sid)
        assert s.type == typ and not hasattr(s, "bar_targets")
        r = BT.run(sid, now=NOW)
        assert r["ok"], (sid, r.get("error"))


def test_waits_for_gold_bar_of_the_same_four_hours(clean, monkeypatch):
    s = S.get("silver_gold_ok")
    full = s._gold(NOW)
    monkeypatch.setattr(TrendSizedStrategy, "_gold", lambda self, now=None: full.iloc[:-1])
    ev = s.evaluate(NOW)
    assert not ev["ok"] and "Waiting for gold" in ev["error"]
    monkeypatch.setattr(TrendSizedStrategy, "_gold", lambda self, now=None: full.iloc[:0])
    ev = s.evaluate(NOW)
    assert not ev["ok"] and "Waiting for gold" in ev["error"]
    res = s.compute(series("SI"), full.iloc[:0])                  # no gold at all: gold's OK fails, nothing throws
    assert not res["gold_ok"].any() and not (res["size"] > 0).any()


def test_short_gold_history_does_not_trade_the_ratio(clean, monkeypatch):
    s = S.get("silver_lead_1x")
    full = s._gold(NOW)
    monkeypatch.setattr(TrendSizedStrategy, "_gold", lambda self, now=None: full.iloc[-300:])   # about 50 days of gold
    ev = s.evaluate(NOW)
    assert not ev["ok"] and "gold history" in ev["error"]


def test_switch_between_2x_and_1x_is_not_a_buy(clean):
    s = S.get("silver_lead_1x")
    h = {"kind": "SIZE", "from": "AGQ 55%", "to": "SLV 99%", "text": "x"}
    assert s.signal_message(h).startswith("SWITCH")
    assert s.signal_message({**h, "to": "AGQ 40%"}).startswith("RESIZE")
    ev = s.evaluate(NOW)
    for h in ev["history"]:
        cash_from, cash_to = h["from"] == "cash", h["to"] == "cash"
        assert h["kind"] == ("BUY" if cash_from else "SELL" if cash_to else "SIZE"), h


def test_backtest_rebalances_drift_for_sized_targets_only(clean, monkeypatch):
    from app.strategies.base import StrategyBase as Strategy
    monkeypatch.setattr(Strategy, "rebalance_band", lambda self: 0.01)
    BT._cache.clear()
    r = BT.run("silver_lead_1x", now=NOW)                      # AGQ at about half: a 1% band drifts
    assert r["ok"], r.get("error")
    reb = [t for t in r["trades"] if t["kind"] == "REBALANCE"]
    assert reb and all(t["why"].startswith("rebalance") for t in reb)
    assert len(reb) < len(r["trades"])
    r2 = BT.run("silver_st", now=NOW)                          # 99% targets: the old metals path is unchanged
    assert r2["ok"] and not [t for t in r2["trades"] if t["kind"] == "REBALANCE"]
