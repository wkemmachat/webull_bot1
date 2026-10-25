"""C2-7 Momentum basket: QQQ on/off signal, weekly top-12 → strongest 7, 2x ETFs, no top-ups, gold + T-bills when off."""
import json

import numpy as np
import pytest

from app import basket, brokers, db, execution as X, ledger
from app import strategies as S
from app.strategies.momentum import signal_states
from conftest import NOW


def test_research_data_is_bundled():
    r = basket.ranks()
    assert str(r["week"].min()) == "2016-10-28" and str(r["week"].max()) >= "2026-10-23"
    w, rk = basket.ranking_for(NOW.date())
    assert str(w) == "2026-10-16" and rk[0][0] in ("NVDA", "AAPL", "MSFT", "GOOGL") and len(rk) == 50
    assert len(basket.members()) == 100
    px = basket.prices("AAPL")
    assert str(px.index[0]) == "2016-01-04" and px["c"].iloc[-1] > 100


def test_momentum_list_picks_the_strongest_of_the_largest():
    w, picks, rows = basket.momentum_list(NOW.date(), pool=12, hold=7, lookback=126)
    assert len(rows) == 12 and len(picks) == 7
    moms = {r["symbol"]: r["mom"] for r in rows}
    worst_picked = min(moms[s] for s in picks)
    assert all(moms[r["symbol"]] <= worst_picked for r in rows if not r["picked"] and moms[r["symbol"]] is not None)
    assert picks == [r["symbol"] for r in rows if r["picked"]]                    # largest first


def test_signal_rule_matches_the_research():
    n = 400
    c = np.r_[np.linspace(100, 200, 300), np.linspace(200, 150, 100)]
    st, sup, sl, se, r = signal_states(c, c * 1.01, c * 0.99, c, 14, 4.0, 200, 2, 5.0, 5)
    assert st[250] == "trend"                          # rising: Supertrend up and above SMA200
    assert st[-1] in ("out", "dip") and "dip" in set(st[300:])


def test_targets_1x_2x_and_off():
    one, two = S.get("c27_mom"), S.get("c27_mom2x")
    picks = ["NVDA", "AAPL", "ASML", "MSFT", "AMZN", "META", "AVGO"]
    t1 = one.target_for("trend", picks)
    assert set(t1) == set(picks) and sum(t1.values()) == pytest.approx(0.99, abs=0.002)
    t2 = two.target_for("dip", picks)
    assert {"NVDL", "AAPU", "MSFU", "AMZU", "METU", "AVGX", "ASML"} == set(t2)            # ASML has no 2x ETF
    assert two.target_for("out", picks) == {"GLD": 0.495, "SGOV": 0.495}
    assert two.fallback_for("NVDL") == "NVDA"


def test_no_top_ups_new_names_get_one_seventh():
    s = S.get("c27_mom")
    target = s.target_for("trend", ["NVDA", "AAPL", "MSFT", "AMZN", "META", "AVGO", "GOOGL"])
    held = {"NVDA": 0.30, "AAPL": 0.20, "MSFT": 0.10, "AMZN": 0.10, "META": 0.10, "TSLA": 0.19}   # TSLA left the list
    adj = s.adjust_target(target, held)
    assert adj["NVDA"] == 0.30 and adj["AAPL"] == 0.20                                   # kept as they are
    assert "TSLA" not in adj
    assert adj["AVGO"] == pytest.approx(0.99 / 7, abs=1e-3)                              # new, largest first
    assert adj["GOOGL"] == pytest.approx(0.99 - 0.80 - 0.99 / 7, abs=2e-3)               # limited to what is left
    assert "GLD" not in adj


def test_live_plan_keeps_goal_and_buys_seven(clean, clock):
    s = S.get("c27_mom")
    ev = s.evaluate(NOW)
    assert ev["ok"] and len(ev["detail"]["basket"]["picks"]) == 7
    ev = dict(ev, state="trend", target=s.target_for("trend", ev["detail"]["basket"]["picks"]))
    from app import marketdata as md
    for sym in ev["target"]:
        md.set_quote(sym, float(basket.prices(sym)["c"].iloc[-1]))
    b = brokers.get("paper")
    pid = X.reconcile("paper", s, ev, NOW, b, db.get_settings())
    assert pid
    plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    assert json.loads(plan["goal"]) == ev["target"]
    buys = {r["symbol"] for r in db.rows("SELECT DISTINCT symbol FROM orders WHERE plan_id=? AND side='BUY'", (pid,))}
    assert buys == set(ev["target"])
    assert X.reconcile("paper", s, ev, NOW, b, db.get_settings()) is None            # same goal: plan kept, not rebuilt
    assert db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"] == "active"


def test_backtest_basket_runs_both_leverages():
    from app import backtest as BT
    a, b = BT.run("c27_mom", now=NOW), BT.run("c27_mom2x", now=NOW)
    assert a["ok"] and b["ok"], (a.get("error"), b.get("error"))
    assert a["vs"] == "QQQ" and b["vs"] == "QLD" and set(a["parking"]) == {"GLD", "SGOV"}
    kinds = {t["kind"] for t in a["trades"]}
    assert "LIST" in kinds or "BUY" in kinds
    assert b["stats"]["MAX"]["strategy"]["vol"] > a["stats"]["MAX"]["strategy"]["vol"] * 1.4   # 2x moves about twice as much
