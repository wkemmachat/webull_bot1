"""Strategy pool (PRD 27 Nov 2026): slot sizing, group cap, smallest trade, shared cash, money back when a trade ends,
non-members, no parking, the pool backtest, and the manual money buttons while the pool is on."""
import time

import numpy as np
import pandas as pd
import pytest

from app import db, engine, ledger, pool
from app import strategies as S
from conftest import NOW

MODE = "paper"


def _reset(cash=100_000.0):
    """Empty strategy books and a pool of `cash` in bot unassigned."""
    with db.tx() as c:
        c.execute("DELETE FROM ledger WHERE mode=?", (MODE,))
        c.execute("DELETE FROM holdings WHERE mode=?", (MODE,))
        c.execute("DELETE FROM plans WHERE mode=?", (MODE,))
        c.execute("DELETE FROM orders WHERE mode=?", (MODE,))
    ledger.pool(MODE)
    db.run("UPDATE pool SET cash=? WHERE mode=?", (cash, MODE))


def _ev(target):
    return {"ok": True, "target": target, "bar_time": int(NOW.timestamp())}


def _on(members, slot=15.0, cap=25.0, minp=2.0):
    pool.set_members(MODE, members)
    pool.set_settings(MODE, on_=True, slot=slot, cap=cap, minp=minp)


def _cash(sid):
    return round(ledger.get(MODE, sid)["cash"], 2)


def test_suggested_slot():
    assert pool.suggested_slot(10) == 15.0
    assert pool.suggested_slot(20) == 10.0          # 7.5% → kept at 10%
    assert pool.suggested_slot(5) == 25.0           # 30% → kept at 25%
    assert pool.suggested_slot(7) == 21.5


def test_trade_start_gets_the_slot_and_the_group_cap_cuts_the_second(clean):
    _reset()
    _on(["qld_split_2c", "usd_trend_split", "usd_ibs"])
    evs = {sid: (S.get(sid), _ev(t)) for sid, t in (("qld_split_2c", {"QLD": 0.99}), ("usd_trend_split", {"USD": 0.99}),
                                                    ("usd_ibs", {"USD": 0.99}))}
    out = pool.step(MODE, evs, NOW)
    assert _cash("qld_split_2c") == 15_000.0
    assert _cash("usd_trend_split") == 15_000.0                       # first semiconductor member: its full slot
    assert _cash("usd_ibs") == 10_000.0                               # second one: what is left of the 25% group cap
    assert ledger.pool_cash(MODE) == 60_000.0
    assert len(out["funded"]) == 3
    assert db.get_state(f"pooltrade:{MODE}:usd_ibs")["capped"]
    # a second check changes nothing: they are in their trades
    pool.step(MODE, evs, NOW)
    assert ledger.pool_cash(MODE) == 60_000.0


def test_short_of_cash_is_shared_and_under_the_smallest_trade_waits(clean):
    _reset(20_000.0)
    _on(["qld_split_2c", "rom_split_2c", "sso_macd_calm"], slot=50.0, cap=100.0, minp=2.0)
    evs = {sid: (S.get(sid), _ev({sym: 0.99})) for sid, sym in (("qld_split_2c", "QLD"), ("rom_split_2c", "ROM"), ("sso_macd_calm", "SSO"))}
    pool.step(MODE, evs, NOW)
    each = [_cash(s) for s in ("qld_split_2c", "rom_split_2c", "sso_macd_calm")]
    assert max(each) - min(each) < 0.02 and abs(sum(each) - 20_000) < 0.05   # slots of 10,000 each, 20,000 free: shared
    # nothing free now: a fourth member with a signal waits for money
    pool.set_members(MODE, ["qld_split_2c", "rom_split_2c", "sso_macd_calm", "ddm_calm_guard"])
    evs["ddm_calm_guard"] = (S.get("ddm_calm_guard"), _ev({"DDM": 0.99}))
    out = pool.step(MODE, evs, NOW)
    assert "ddm_calm_guard" in out["waiting"] and _cash("ddm_calm_guard") == 0
    assert db.get_state(f"poolwait:{MODE}:ddm_calm_guard")["why"] == "free cash"
    db.run("INSERT INTO strategy_state(strategy,computed_at,ok,target,state,label) VALUES('ddm_calm_guard',?,1,'{\"DDM\": 0.99}','in','IN') "
           "ON CONFLICT(strategy) DO UPDATE SET target=excluded.target, ok=1", (int(time.time()),))
    v = pool.view(MODE)
    assert [m["id"] for m in v["waiting"]] == ["ddm_calm_guard"]


def test_money_comes_back_when_the_trade_ends_not_before(clean):
    _reset()
    _on(["qld_split_2c"])
    s = S.get("qld_split_2c")
    pool.step(MODE, {"qld_split_2c": (s, _ev({"QLD": 0.99}))}, NOW)
    ledger.book_fill(MODE, "qld_split_2c", "QLD", "BUY", 100, 9_000.0)        # bought; 6,000 left as the trade's cash
    pool.step(MODE, {"qld_split_2c": (s, _ev({"QLD": 0.99}))}, NOW)
    assert _cash("qld_split_2c") == 6_000.0                               # in its trade: nothing moves
    ledger.book_fill(MODE, "qld_split_2c", "QLD", "SELL", 100, 9_900.0)       # sold with a profit
    pool.step(MODE, {"qld_split_2c": (s, _ev({"QLD": 0.99}))}, NOW)
    assert _cash("qld_split_2c") == 15_900.0                              # signal still on (e.g. a partial plan): stays
    pool.step(MODE, {"qld_split_2c": (s, _ev({"GLD": 0.5}))}, NOW)        # out (gold parking does not count)
    assert _cash("qld_split_2c") == 0.0
    assert ledger.pool_cash(MODE) == 100_900.0
    row = db.one("SELECT * FROM money WHERE mode=? AND strategy='qld_split_2c' AND kind='withdraw'", (MODE,))
    assert row["note"] == pool.NOTE_OUT and abs(row["done_amount"] - 15_900) < 0.01
    v = ledger.value(MODE, "qld_split_2c")
    assert abs(v["pnl"] - 900) < 0.01                                      # its own P&L still counts what it gave back


def test_non_members_hand_back_cash_and_only_sell(clean):
    _reset()
    ledger.credit(MODE, "usd_ibs", 5_000.0)                                # money from before the pool
    ledger.credit(MODE, "rom_vol_ibs", 4_000.0)
    ledger.book_fill(MODE, "rom_vol_ibs", "ROM", "BUY", 10, 3_000.0)       # still holds a trade
    _on(["qld_split_2c"])
    pool.step(MODE, {}, NOW)
    assert _cash("usd_ibs") == 0.0                                         # cash only: back at once
    assert _cash("rom_vol_ibs") == 1_000.0                                 # holds shares: keeps its trade until it ends
    assert pool.no_buys(MODE, "rom_vol_ibs") and not pool.no_buys(MODE, "qld_split_2c")
    v = pool.view(MODE)
    assert any(r["id"] == "rom_vol_ibs" and r["leaving"] for r in v["outside"])
    pool.remove(MODE, "qld_split_2c", sell=True)
    s = S.get("qld_split_2c")
    assert pool.pool_target(MODE, s, {"QLD": 0.99}) == {}                # sell now: target 0 at the next check


def test_members_do_not_park(clean):
    s = S.get("usd_trend_split")
    park = pool.parking(s)
    t = {"USD": 0.5, **{k: 0.25 for k in park}}
    assert pool.strip_parking(s, t) == {"USD": 0.5}
    assert pool.main_symbol(s) == "USD" and pool.group_of(s) == "semis"


def test_pool_off_changes_nothing(clean):
    s = S.get("qld_split_2c")
    assert not pool.on(MODE)
    assert pool.pool_target(MODE, s, {"QLD": 0.5, "GLD": 0.49}) == {"QLD": 0.5, "GLD": 0.49}
    assert not pool.no_buys(MODE, "qld_split_2c")
    assert pool.step(MODE, {}, NOW) == {}


def test_live_member_needs_a_test_trade(clean):
    with pytest.raises(ValueError, match="test trade"):
        pool.set_members("live", ["magx_s1p_s2pp"])
    db.run("INSERT INTO test_trades(mode,symbol,qty,status,created_at) VALUES('live','MAGX',1,'ok',?)", (int(time.time()),))
    pool.set_members("live", ["magx_s1p_s2pp"])
    assert "magx_s1p_s2pp" in pool.cfg("live")["members"]


def test_manual_money_buttons_are_blocked_while_the_pool_is_on(clean):
    from fastapi.testclient import TestClient
    from app.main import app
    _reset()
    _on(["qld_split_2c"])
    c = TestClient(app)
    from app import main
    app.dependency_overrides[main.user] = lambda: {"username": "t"}
    try:
        r = c.post("/api/money/add", json={"mode": MODE, "strategy": "qld_split_2c", "amount": 100})
        assert r.status_code == 400 and "pool is on" in r.json()["detail"]
        r = c.get(f"/api/pool?mode={MODE}")
        assert r.status_code == 200 and r.json()["on"] and r.json()["members"][0]["id"] == "qld_split_2c"
    finally:
        app.dependency_overrides.clear()


def test_simulator_rules():
    idx = pd.bdate_range("2024-01-01", periods=6)
    R = pd.DataFrame({"a": [0, 0.10, 0.0, 0.0, 0.0, 0.0], "b": [0, 0.0, 0.0, -0.10, 0.0, 0.0]}, index=idx)
    X = pd.DataFrame({"a": [0, 1, 1, 0, 0, 0], "b": [0, 0, 0, 1, 1, 0]}, index=idx, dtype=float)
    avail = X.notna()
    v, _ = pool.simulate(R, X, avail, {"a": "g1", "b": "g2"}, slot=0.5, cap=1.0, minp=0.02, C=100.0)
    assert v.iloc[1] == pytest.approx(105.0)                 # a holds 50 → +10% = +5
    assert v.iloc[3] == pytest.approx(100.0)                 # a sells at that open (its money is still in use that day):
                                                              # b gets the free 50 of its 52.5 slot → −10% = −5
    v2, _ = pool.simulate(R, X, avail, {"a": "g", "b": "g"}, slot=0.5, cap=0.3, minp=0.02, C=100.0)
    assert v2.iloc[1] == pytest.approx(103.0)                # group cap 30%: a gets 30


def test_engine_check_funds_a_member_and_plans_its_trade(clean, clock):
    _reset()
    _on(["qld_split_2c", "ddm_calm_guard"])
    engine.tick(NOW)
    v = pool.view(MODE)
    funded = [m for m in v["members"] if m["value"] > 0]
    for m in funded:
        assert abs(m["value"] - 15_000) < 1 or m["status"][1].startswith("In a trade")
        assert db.one("SELECT COUNT(*) n FROM plans WHERE mode=? AND strategy=?", (MODE, m["id"]))["n"] >= 1
    others = [s for s in ("usd_ibs", "gold_sta", "rom_vol_ibs") if ledger.get(MODE, s)["cash"] > 0.01]
    assert not others                                       # seeded paper money of non-members went back to the pool
    assert abs(v["total"] - (v["free"] + v["in_trades"])) < 0.01


def test_no_paper_start_money_while_the_pool_is_on(clean):
    from app import moneyops
    _on(["ddm_calm_guard"])
    before, cash0 = db.one("SELECT COUNT(*) n FROM money WHERE note='Paper start'")["n"], _cash("ddm_calm_guard")
    seeded = db.get_state("paper_seeded")
    db.set_state("paper_seeded", None)
    try:
        moneyops.seed_paper()
        moneyops.seed_new_paper("ddm_calm_guard")
        assert db.one("SELECT COUNT(*) n FROM money WHERE note='Paper start'")["n"] == before
        assert _cash("ddm_calm_guard") == cash0
    finally:
        db.set_state("paper_seeded", seeded or 1)


def test_member_holding_only_cash_is_not_called_in_a_trade(clean):
    _on(["ddm_calm_guard"])
    ledger.credit(MODE, "ddm_calm_guard", 5000)
    row = next(m for m in pool.view(MODE)["members"] if m["id"] == "ddm_calm_guard")
    assert not row["status"][1].startswith("In a trade")


def test_health_line_adds_up(clean):
    from app import health
    _reset(50_000)
    _on(["ddm_calm_guard"])
    items = []
    health._pool_item(items, MODE, "Paper")
    assert items and items[0]["status"] == "ok" and "= $" in items[0]["detail"]


def test_choose_members_groups_by_the_etf_traded():
    assert pool.underlying(S.get("qld_split_2c"))[0] == "QLD"
    assert pool.underlying(S.get("qld_split_2c"))[1] == "Nasdaq-100 2x"
    assert pool.underlying(S.get("usd_trend_split"))[0] == pool.underlying(S.get("semis_regime"))[0] == "USD"
    assert pool.underlying(S.get("silver_lead_1x"))[0] == "AGQ"                       # AGQ first, SLV as its 1x fallback
    c1, c2 = pool.underlying(S.get("c27_mom")), pool.underlying(S.get("c27_mom2x"))
    assert c1[0] == c2[0] and c1[1].endswith("stocks")                                 # the two baskets share one group
    r = pool.ranks(MODE)
    assert r["qld_split_2c"]["etf"] == "QLD" and set(r["qld_split_2c"]) >= {"r10", "dd10", "ret_dd", "cap_group"}


def test_line_stays_on_for_members_without_money(clean):
    """27 Nov (Live): turning the pool on took the members' money back and Automatic LINE switched them off, so the
    buy signal at the close (before the pool funds the trade) would not have been sent."""
    from app import notify
    _reset(50_000)
    _on(["usd_trend_split"])
    assert _cash("usd_trend_split") == 0
    assert notify.auto_on("usd_trend_split", "active", ["paper"])
    assert not notify.auto_on("rom_vol_ibs", "active", ["paper"])            # not a member, no money: off as before
    assert not notify.auto_on("usd_trend_split", "stopped", ["paper"])       # Stopped: off
    pool.set_settings(MODE, on_=False)
    assert not notify.auto_on("usd_trend_split", "active", ["paper"])        # pool off: follows the money again


def test_member_holding_only_gold_parking_is_selling_it(clean):
    _on(["qld_split_2c"])
    db.run("INSERT INTO holdings(mode,strategy,symbol,qty,cost) VALUES(?,?,?,?,?)", (MODE, "qld_split_2c", "GLD", 3, 1000))
    row = next(m for m in pool.view(MODE)["members"] if m["id"] == "qld_split_2c")
    assert row["status"][1].startswith("Selling its gold parking")


def test_fractions_sell_to_two_decimals_and_crumbs_do_not_block_the_pool(clean, clock):
    """27 Nov (Live): Webull failed sells of 1.278945 GLD; the parking was left over and the money stayed out of the pool."""
    from app import execution
    _reset(20_000)
    _on(["qld_split_2c"])
    assert execution._down(1.278945, execution.SELL_DP) == 1.2789
    sid = "qld_split_2c"
    ledger.credit(MODE, sid, 5000)
    db.run("INSERT INTO holdings(mode,strategy,symbol,qty,cost) VALUES(?,?,?,?,?)", (MODE, sid, "GLD", 1.278945, 425))
    ledger.set_applied_target(MODE, sid, {})
    evs = {sid: (S.get(sid), _ev({}))}
    pool.step(MODE, evs, NOW, None)
    assert ledger.get(MODE, sid)["applied_target"] is None             # leftover parking: re-planned
    assert _cash(sid) == 5000                                          # money waits until the gold is sold
    pool.step(MODE, evs, NOW, None)
    assert db.get_state(f"poolsweep:{MODE}:{sid}")                     # at most once per 10 minutes
    db.run("UPDATE holdings SET qty=0.008945 WHERE mode=? AND strategy=? AND symbol='GLD'", (MODE, sid))   # sold: a crumb left
    pool.step(MODE, evs, NOW, None)
    assert _cash(sid) == 0                                             # the crumb does not keep the money out
    pool.step(MODE, {sid: (S.get(sid), _ev({"QLD": 0.99}))}, NOW, None)
    assert _cash(sid) > 0                                              # and it still gets money for its next trade
