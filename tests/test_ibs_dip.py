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
    assert s.params["ibs_max"] == 0.2 and s.params["adx_min"] == 20 and s.params["target_vol_pct"] == 50
    assert s.params["size_band_pct"] == 20 and set(s.parking()) == {"GLD", "BIL"}


def test_size_band_and_fresh_entries():
    st = ["off", "trend", "trend", "trend", "dip", "off", "dip"]
    raw = [1.0, 0.9, 0.8, 0.65, 0.95, 0.5, 0.4]
    out = sizes(st, raw, 0.20)
    # enters at 0.9; 0.8 is within 20 points; 0.65 is 25 points away -> resize; 0.95 is 30 away -> resize; off -> 0; fresh 0.4
    assert list(out) == [0.0, 0.9, 0.9, 0.65, 0.95, 0.0, 0.4]


def test_targets_split_the_rest_into_parking():
    s = strat()
    t = s.target_for("trend", 0.7)
    assert t["QLD"] == round(0.7 * 0.99, 4)
    assert abs(t["GLD"] - 0.3 * 0.495) < 1e-4 and abs(t["BIL"] - 0.3 * 0.495) < 1e-4
    assert abs(sum(t.values()) - 0.99) < 1e-3
    assert s.target_for("dip", 1.0) == {"QLD": 0.99}
    assert s.target_for("off") == {"GLD": 0.495, "BIL": 0.495}


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
    assert set(ev["target"]) <= {"USD", "GLD", "BIL"}


def test_usd_backtest_runs_with_smh_comparison():
    from app import backtest as BT
    r = BT.run("usd_ibs", now=NOW)
    assert r["ok"], r.get("error")
    assert r["main"] == "USD" and "SMH" in r["series"]["bench"] and r["index"] == "SMH"
    assert r["research"]["cagr"] == 66.8
