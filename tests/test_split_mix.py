"""QLD · Split 2C (type split_mix, legs trend_gate + ibd_gate ×2): the IBD market-direction walk, the yearly sub-account mix
rebuilt independently from the legs' own targets, the settings checks, the health recompute and the new default ("Strategy
research and stress tests", round 2 QLD split C, 15 Nov 2026)."""
import json

import numpy as np
import pytest

from app import health
from app import strategies as S
from app.strategies.ibd_gate import ibd_direction
from conftest import NOW


def default(sid):
    return dict(S.DEFAULTS[[d[0] for d in S.DEFAULTS].index(sid)][4])


P = default("qld_split_2c")


def make(params=None):
    return S.TYPES["split_mix"]({"id": "t_mix", "name": "test mix", "params": {**P, **(params or {})}})


# ---------------------------------------------------------------- IBD market direction
def test_ibd_correction_and_follow_through():
    c, v = [100.0] * 5, [1000.0] * 5
    for _ in range(6):                                    # six distribution days: down 0.5% on rising volume
        c.append(c[-1] * 0.995); v.append(v[-1] + 100)
        c.append(c[-1]); v.append(900)
    up, dd, cnt, att = ibd_direction(np.array(c), np.array(v), dist=6, window=25, expire_pct=5.0)
    assert dd.sum() == 6 and up[:15].all() and not up[-1]
    # rally attempt: day 1 up, then flat days, a 2% gain on higher volume on day 4 = follow-through
    c2, v2 = list(c), list(v)
    c2.append(c2[-1] * 1.002); v2.append(800)              # day 1
    c2 += [c2[-1]] * 2; v2 += [800, 800]                   # days 2–3
    c2.append(c2[-1] * 1.02); v2.append(2000)              # day 4: +2% on higher volume
    up2, _, _, att2 = ibd_direction(np.array(c2), np.array(v2), dist=6, window=25, expire_pct=5.0)
    assert not up2[-2] and up2[-1] and att2[-1] == 4


def test_ibd_distribution_days_expire_on_a_5pct_rise():
    c, v = [100.0] * 3, [1000.0] * 3
    for _ in range(5):
        c.append(c[-1] * 0.995); v.append(v[-1] + 100)
    c += [c[-1] * 1.10]; v += [500]                        # 5%+ above every distribution day: all of them stop counting
    c.append(c[-1] * 0.995); v.append(v[-1] + 100)        # one more distribution day: only 1 live, not 6
    up, dd, cnt, _ = ibd_direction(np.array(c), np.array(v), dist=6, window=25, expire_pct=5.0)
    assert up.all() and cnt[-1] == 1
    up0, _, cnt0, _ = ibd_direction(np.array(c), np.array(v), dist=6, window=25, expire_pct=0.0)
    assert not up0[-1] and cnt0[-1] == 6


# ---------------------------------------------------------------- the mix, rebuilt from the legs
def test_mix_matches_the_legs_targets():
    s = make()
    fr = s.frame(NOW)
    legs = s.legs()
    assert [lg.type for lg in legs] == ["trend_gate", "ibd_gate", "ibd_gate"]
    frs = [lg.frame(NOW) for lg in legs]
    idx = fr.index
    W = np.array([[lg.target_for(f.loc[d, "state"], f.loc[d, "size"]).get("QLD", 0.0) for d in idx] for lg, f in zip(legs, frs)]).T
    G = np.array([[lg.target_for(f.loc[d, "state"], f.loc[d, "size"]).get("GLD", 0.0) for d in idx] for lg, f in zip(legs, frs)]).T
    assert np.allclose(fr[["l1_w", "l2_w", "l3_w"]].values, W)
    from app import marketdata as md
    q = md.daily_closed("QLD", NOW)["c"].reindex(idx).values
    g = md.daily_closed("GLD", NOW)["c"].reindex(idx).values
    years = [d.year for d in idx.tz_convert("America/New_York")]
    v, want = np.full(3, 1 / 3), []
    for i in range(len(idx)):
        if i:
            if years[i] != years[i - 1]:
                v = np.full(3, v.sum() / 3)
            rq, rg = np.nan_to_num(q[i] / q[i - 1] - 1), np.nan_to_num(g[i] / g[i - 1] - 1)   # a missing day = no change
            v = v * (1 + W[i - 1] * rq + G[i - 1] * rg)
        want.append((v * W[i]).sum() / v.sum())
    want = np.array(want)
    size = fr["size"].values
    for i in range(1, len(idx)):                          # the size moves only when a leg's target changes or a year starts
        if years[i] == years[i - 1] and (W[i] == W[i - 1]).all():
            assert size[i] == size[i - 1]
        else:
            assert size[i] == pytest.approx(round(want[i], 4), abs=1e-4)
    assert fr["size"].between(0, 0.99).all() and fr["legs_in"].max() >= 1


def test_daily_rebalance_is_the_plain_average():
    fr = make({"rebalance_legs": "daily"}).frame(NOW)
    avg = fr[["l1_w", "l2_w", "l3_w"]].mean(axis=1).values
    ch = (fr[["l1_w", "l2_w", "l3_w"]].diff().abs().sum(axis=1) > 0).values
    assert np.allclose(fr["size"].values[ch], np.round(avg[ch], 4), atol=1e-4)


def test_settings_checks():
    legs = json.loads(P["legs"])
    with pytest.raises(ValueError):                       # every leg must trade the mix's ETF
        make({"legs": json.dumps([legs[0], {**legs[1], "params": {**legs[1]["params"], "trade": "SSO"}}])})
    with pytest.raises(ValueError):
        make({"legs": json.dumps(legs[:1])})
    with pytest.raises(ValueError):                       # legs may park differently, but in the same gold ETF
        make({"legs": json.dumps([legs[0], {**legs[1], "params": {**legs[1]["params"], "gold_symbol": "IAU"}}])})
    with pytest.raises(ValueError):                       # weights: all or none
        make({"legs": json.dumps([{**legs[0], "weight": 60}, legs[1]])})
    assert make({"legs": json.dumps([legs[0], {**legs[1], "params": {**legs[1]["params"], "gold_share_pct": 0}}])})
    with pytest.raises(ValueError):
        make({"legs": json.dumps([legs[0], {"type": "split_mix", "params": {}}])})
    s = make({"legs": legs[:2]})                          # a list (JSON body) works too
    assert len(s.legs()) == 2 and s.share_word() == "half"


def test_evaluate_target_and_checks():
    s = make()
    ev = s.evaluate(NOW)
    assert ev["ok"] and ev["state"] in ("trend", "dip", "volatile", "out")
    size = ev["detail"]["size"]
    t = ev["target"]
    assert t.get("QLD", 0) == pytest.approx(size, abs=1e-4)
    assert t.get("GLD", 0) == pytest.approx(0.5 * (0.99 - size), abs=1e-3)
    assert sum(t.values()) <= 0.99 + 1e-6
    keys = [c["k"] for c in ev["checks"]]
    assert keys[0].startswith("Leg 1 · QLD-A") and any(k.startswith("Leg 2 · QLD-B") for k in keys)
    assert any(k.startswith("Leg 3 · QLD-C") for k in keys) and keys[-1] == "Size"
    assert all(h["kind"] in ("BUY", "SELL") for h in ev["history"])
    assert len(ev["detail"]["tiles"]) == 3 and ev["detail"]["log"][0]["l1"]
    d = s.describe()
    assert "a third" in d["rule"] and len(d["rules"]) >= 6
    ch = s.chart(NOW, "1Y")
    assert ch["charts"][0]["candles"] and [p["id"] for p in ch["charts"][0]["panes"]] == ["legs", "size"]


def test_health_recompute_matches():
    s = make()
    t = health.indicator_table(s, NOW)
    assert t["cols"][:1] == ["Close"] and len(t["rows"]) == 12 and t["max_diff"] == 0
    for lg in s.legs():
        cols, rows, worst = lg.check_table(NOW, 12)
        assert len(rows) == 12 and worst == 0, (lg.name, rows[:2])


def test_default_added_quietly(clean):
    r = S.row("qld_split_2c")
    assert r and r["type"] == "split_mix"
    assert "qld_split_2c" in S.QUIET_DEFAULTS
    st = S.get("qld_split_2c")
    assert set(st.trade_symbols()) == {"QLD", "GLD"} and set(st.read_symbols()) == {"QQQ", "QLD"}
    assert st.legs()[1].params["ibd_expire_pct"] == 5.0
    from app import backtest
    out = backtest.run("qld_split_2c")
    assert out.get("ok") is not False and "MAX" in out["stats"]
