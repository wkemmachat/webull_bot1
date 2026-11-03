"""Gold · Slow trend + calm + RSI dips (type metal_trend_calm, challenger G1 of "Gold & Silver Challengers", 3 Nov 2026):
the bot's rule against an independent restatement of the research rule, no look-ahead, the new default strategy, and that
Gold #1 / Gold #2 are unchanged."""
import numpy as np
import pandas as pd
import pytest

from app import db, health, ledger, metals
from app import strategies as S
from app.strategies.metal_trend import TrendCalmDipStrategy, daily_from_4h
from conftest import NOW

G1 = dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index("gold_trend_calm")][4])


def bars():
    return metals.series("GC", NOW)["adj4"]


def research_want(b, p):
    """The research engine (metals/scripts lib.py + stage3.combo) restated with pandas on the same 4H bars."""
    from app import indicators as I
    st = I.supertrend(b.h.values, b.l.values, b.c.values, p["atr"], p["mult"])
    up = st["up"] & ~np.isnan(st["atr"])
    ny = b.index.tz_convert("America/New_York")
    sess = (ny + pd.Timedelta(hours=6)).normalize()
    # a session's close: its 14:00 bar, known from that bar on (the demo data has full sessions)
    is_last = ny.hour == 14
    dc = pd.Series(b.c.values[is_last], index=sess[is_last])
    ma = dc.rolling(p["daily_ma"]).mean()
    flt = (dc > ma) | ma.isna()
    v = np.log(dc).diff().rolling(p["vol_days"]).std()
    thr = v.rolling(p["vol_lookback"], min_periods=p["vol_lookback"]).quantile(p["vol_q"] / 100)
    calm = thr.isna() | (v <= thr)
    r = pd.Series(I.rsi(dc.values, p["rsi_len"]), index=dc.index)
    s200, s5 = dc.rolling(p["dip_ma"]).mean(), dc.rolling(p["exit_ma"]).mean()
    dip, cur = [], False
    for i in range(len(dc)):
        if cur and dc.iloc[i] > s5.iloc[i]:
            cur = False
        elif not cur and r.iloc[i] < p["rsi_buy"] and dc.iloc[i] > s200.iloc[i]:
            cur = True
        dip.append(cur)
    dip = pd.Series(dip, index=dc.index)
    # for each 4H bar: the last session whose 14:00 bar has closed (this bar included)
    k = np.cumsum(is_last) - 1
    ok = k >= 0
    pick = lambda s: np.where(ok, s.values[np.clip(k, 0, None)], False)
    return ((up & pick(flt).astype(bool) & pick(calm).astype(bool)) | pick(dip).astype(bool)).astype(int)


def test_default_strategy_seeded_quiet_and_without_live_money(clean):
    s = S.get("gold_trend_calm")
    assert s and s.type == "metal_trend_calm" and s.params == TrendCalmDipStrategy.merge_params(G1)
    assert s.params["atr"] == 150 and s.params["mult"] == 4 and s.params["daily_ma"] == 50 and s.params["vol_q"] == 80
    assert s.params["etf"] == "UGL" and s.params["cash_etf"] == ""
    assert ledger.get("live", "gold_trend_calm")["cap_in"] == 0 and not ledger.get("live", "gold_trend_calm")["holdings"]


def test_reseed_adds_it_with_line_off(clean):
    db.run("DELETE FROM strategies WHERE id='gold_trend_calm'")
    db.set_state("seeded_defaults", [d[0] for d in S.DEFAULTS if d[0] != "gold_trend_calm"])
    assert S.seed() == ["gold_trend_calm"]
    assert S.get("gold_trend_calm").row["line_on"] == 0


def test_rule_matches_the_research_rule(clean):
    b = bars()
    s = S.get("gold_trend_calm")
    res = s.compute(b)
    want = research_want(b, s.params)
    w0 = s.warmup()
    assert len(b) > w0 + 100
    assert (res["want"].values[w0:] == want[w0:]).mean() == 1.0
    assert res["want"].values[w0:].sum() > 0 and (1 - res["want"].values[w0:]).sum() > 0   # both states happen


def test_no_look_ahead(clean):
    b = bars()
    s = S.get("gold_trend_calm")
    full = s.compute(b)["want"].values
    for cut in (len(b) - 1, len(b) - 7, len(b) - 40, len(b) - 333):
        part = s.compute(b.iloc[:cut])["want"].values
        assert (part == full[:cut]).all(), cut


def test_daily_closes_are_the_1400_bar_and_known_only_after_it(clean):
    b = bars()
    dc, days, known = daily_from_4h(b)
    ny = b.index.tz_convert("America/New_York")
    last = np.where(ny.hour == 14)[0]
    assert len(dc) >= len(last) and np.allclose(dc[:len(last)][-50:], b.c.values[last][-50:])
    i = last[-1]
    assert known[i] == known[i - 1] + 1                   # the session's close becomes known at its 14:00 bar, not earlier
    assert known[i + 1] == known[i] if i + 1 < len(b) else True


def test_short_session_completes_at_the_next_bar():
    idx = pd.DatetimeIndex(["2026-11-24 23:00", "2026-11-25 03:00", "2026-11-25 07:00", "2026-11-25 11:00", "2026-11-25 15:00",
                            "2026-11-25 19:00",                                   # 14:00 New York: Wednesday's last bar
                            "2026-11-26 23:00",                                   # Friday session opens (Thursday shut)
                            "2026-11-27 03:00", "2026-11-27 07:00", "2026-11-27 11:00", "2026-11-27 15:00",  # short Friday, no 14:00 bar
                            "2026-11-29 23:00"], tz="UTC")                       # Sunday 18:00: Monday's session
    b = pd.DataFrame({"o": 1.0, "h": 1.0, "l": 1.0, "c": np.arange(1, 13, dtype=float)}, index=idx)
    dc, days, known = daily_from_4h(b)
    assert list(dc) == [6.0, 11.0]
    assert list(known) == [-1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 1]   # Friday's close is known at Monday's first bar


def test_evaluate_and_health_check(clean):
    s = S.get("gold_trend_calm")
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["target"] in ({"UGL": 0.99}, {})
    assert ev["state"] in ("long", "flat") and any("Supertrend(150, 4)" in c["k"] for c in ev["checks"])
    assert all(h["kind"] in ("BUY", "SELL") for h in ev["history"])
    tbl = health.indicator_table(s, NOW, rows=40)
    assert tbl["rows"] and all(r["ok"] for r in tbl["rows"]), tbl["rows"][:3]
    ch = s.chart(NOW, "3M")
    assert ch["charts"] and ch["charts"][0]["lines"]
    d = s.describe()
    assert "Supertrend" in d["rule"] and d["rules"]


def test_gold_1_and_2_unchanged(clean):
    a, b2 = S.get("gold_sta"), S.get("gold_st30")
    assert a.type == "supertrend" and a.params["atr"] == 30 and a.params["adx_min"] == 20
    assert b2.type == "supertrend" and b2.params["atr"] == 30 and b2.params["adx_min"] == 0
    tbl = health.indicator_table(a, NOW, rows=10)
    assert tbl["cols"][1] == "Supertrend · bot"
