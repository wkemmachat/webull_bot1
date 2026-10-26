"""QLD Trend + IBS-dip (vol cap): the research's strategy 2."""
import numpy as np

from app import strategies as S
from app.strategies.ibs_dip import sizes, states
from conftest import NOW


def strat(**kw):
    row = dict(S.row("qld_ibs"))
    row["params"] = {**row["params"], **kw}
    return S.instance(row)


def test_seeded_with_research_settings():
    s = strat()
    assert s.type == "ibs_dip" and s.params["trade"] == "QLD" and s.params["vol_symbol"] == "QQQ"
    assert s.params["st_atr"] == 14 and s.params["st_mult"] == 4.0 and s.params["ma_days"] == 200
    assert s.params["ibs_max"] == 0.15 and s.params["adx_min"] == 20 and s.params["target_vol_pct"] == 50   # lower-cost version
    assert s.params["size_band_pct"] == 20 and s.params["tbill_cash"] is True and set(s.parking()) == {"GLD"}
    assert s.park_pcts() == "50% GLD + 50% cash" and "BIL" not in s.trade_symbols()


def test_size_band_and_fresh_entries():
    st = ["off", "trend", "trend", "trend", "dip", "off", "dip"]
    raw = [1.0, 0.9, 0.8, 0.65, 0.95, 0.5, 0.4]
    out = sizes(st, raw, 0.20)
    # enters at 0.9; 0.8 is within 20 points; 0.65 is 25 points away -> resize; 0.95 is 30 away -> resize; off -> 0; fresh 0.4
    assert list(out) == [0.0, 0.9, 0.9, 0.65, 0.95, 0.0, 0.4]


def test_targets_split_the_rest_into_parking():
    s = strat(tbill_cash=False)
    t = s.target_for("trend", 0.7)
    assert t["QLD"] == round(0.7 * 0.99, 4)
    assert abs(t["GLD"] - 0.3 * 0.495) < 1e-4 and abs(t["BIL"] - 0.3 * 0.495) < 1e-4
    assert abs(sum(t.values()) - 0.99) < 1e-3
    assert s.target_for("dip", 1.0) == {"QLD": 0.99}
    assert s.target_for("off") == {"GLD": 0.495, "BIL": 0.495}


def test_tbill_part_kept_as_cash():
    s = strat()
    t = s.target_for("trend", 0.7)
    assert set(t) == {"QLD", "GLD"} and abs(t["GLD"] - 0.3 * 0.495) < 1e-4       # the other 0.3 × 49.5% stays cash
    assert s.target_for("off") == {"GLD": 0.495}
    assert "cash" in s.describe()["rules"][4] and s.evaluate(NOW)["ok"]


def test_old_defaults_move_to_the_low_cost_version():
    import json
    from app import db
    old = dict(S.UPGRADES[0][2])
    db.run("UPDATE strategies SET params=? WHERE id='qld_ibs'", (json.dumps(old),))
    db.run("UPDATE strategies SET params=? WHERE id='usd_ibs'", (json.dumps({**S.UPGRADES[1][2], "ibs_max": 0.12}),))   # changed by you
    db.set_state("upgrades_done", [])
    try:
        assert S.upgrade_defaults() == ["qld_ibs"]
        assert S.get("qld_ibs").params["ibs_max"] == 0.15 and S.get("qld_ibs").params["tbill_cash"] is True
        assert S.get("usd_ibs").params["ibs_max"] == 0.12 and S.get("usd_ibs").params["tbill_cash"] is False
        db.run("UPDATE strategies SET params=? WHERE id='qld_ibs'", (json.dumps(old),))
        assert S.upgrade_defaults() == []                                        # once only
    finally:
        for sid, typ, name, color, params, ex in S.DEFAULTS:
            if sid in ("qld_ibs", "usd_ibs"):
                db.run("UPDATE strategies SET params=? WHERE id=?", (json.dumps(params), sid))


def test_dip_day_needs_weak_close_and_adx():
    n = 260
    c = np.linspace(100, 60, n)                              # long fall: trend off, ADX high
    h, l = c * 1.01, c * 0.99
    c2 = c.copy()
    c2[-1] = l[-1] + 0.1 * (h[-1] - l[-1])                   # closes near the low: IBS 0.1
    st, *_ = states(h, l, c2)
    assert st[-1] == "dip"
    c3 = c.copy()
    c3[-1] = l[-1] + 0.6 * (h[-1] - l[-1])                   # mid-range close: no dip
    st3, *_ = states(h, l, c3)
    assert st3[-1] == "off"


def test_evaluate_and_chart(clock):
    s = strat()
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in ("trend", "dip", "off")
    assert abs(sum(ev["target"].values()) - 0.99) < 2e-3
    kinds = {h["kind"] for h in ev["history"]}
    assert kinds <= {"BUY", "SELL", "SIZE"}
    ch = s.chart(NOW)
    assert ch["charts"][0]["candles"] and {p["id"] for p in ch["charts"][0]["panes"]} == {"ibs", "adx", "size"}
    cols, rows, worst = s.check_table(NOW, 12)
    assert len(rows) == 12 and worst < 1e-6


def test_backtest_runs_and_uses_the_size():
    from app import backtest as BT
    r = BT.run("qld_ibs", now=NOW)
    assert r["ok"], r.get("error")
    assert r["main"] == "QLD" and "QQQ" in r["series"]["bench"]
    assert max(r["series"]["expo"]) <= 1.0
    assert r["research"] and r["research"]["same_settings"]
    small = BT.run("qld_ibs", params={"target_vol_pct": 10}, now=NOW)       # a tight cap → small positions
    assert small["ok"] and 0 < max(small["series"]["expo"]) < 0.6


# ---------------------------------------------------------------- USD Trend + IBS-dip (research candidate C)
def usd(**kw):
    row = dict(S.row("usd_ibs"))
    row["params"] = {**row["params"], **kw}
    return S.instance(row)


def test_usd_seeded_with_candidate_c_settings():
    s = usd()
    p = s.params
    assert s.type == "ibs_dip" and p["trade"] == "USD" and p["vol_symbol"] == "USD" and p["leverage"] == 1
    assert (p["st_atr"], p["st_mult"], p["ma_days"], p["ibs_max"], p["adx_min"]) == (20, 4.5, 200, 0.15, 0)
    assert (p["target_vol_pct"], p["vol_days"], p["size_band_pct"]) == (40, 20, 20) and p["dip_full_size"] is True
    assert s.bench_extra() == ["SMH"] and s.history_symbols() == ["USD"]
    assert "100% on a dip signal" in " ".join(s.describe()["rules"])


def test_usd_dip_signal_takes_full_size(clock):
    s = usd()
    fr = s.frame(NOW)
    dips = (fr["ibs"] < 0.15) & (fr["state"] != "")
    assert dips.any()
    assert (fr.loc[dips, "raw_size"] == 1.0).all()                 # a dip signal → 100% the next day
    capped = usd(dip_full_size=False).frame(NOW)
    assert (capped.loc[dips, "raw_size"] <= 1.0).all()
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert set(ev["target"]) <= {"USD", "GLD"}                       # T-bill part kept as cash


def test_usd_backtest_runs_with_smh_comparison():
    from app import backtest as BT
    r = BT.run("usd_ibs", now=NOW)
    assert r["ok"], r.get("error")
    assert r["main"] == "USD" and "SMH" in r["series"]["bench"] and r["index"] == "SMH"
    assert r["research"]["cagr"] == 66.8


def test_ibs_tie_is_not_decided_by_float_noise():
    """QLD on 10 Feb 2022: close 35.75, low 35.345, high 37.37 → IBS exactly 0.2, which is not a dip (< 0.2), whatever
    tiny rounding the data feed adds."""
    import numpy as np
    from app.strategies.ibs_dip import states
    n = 260
    base = np.linspace(30, 40, n)
    h, l, c = base + 1, base - 1, base.copy()
    for hh, ll, cc in ((37.37, 35.345, 35.75), (37.37 + 1e-9, 35.345, 35.75), (37.37, 35.345 + 3e-7, 35.75 - 2e-7)):
        h[-1], l[-1], c[-1] = hh, ll, cc
        _, _, _, ibs, _ = states(h, l, c)
        assert ibs[-1] == 0.2
