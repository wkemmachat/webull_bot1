"""CWEB · Trend + Hang Seng crash buys (26 Nov 2026, research Pick 4+): the day-by-day rules (walk), the trend part (breakout,
FXI gate, volatility size, trailing stop), the Hang Seng's close (Hong Kong time), the live target and the day limit order
(one order at a fixed price, not re-priced, not retried, cancelled before the close), and the backtest."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app import backtest as BT, brokers, db, engine, execution as X, ledger, marketdata as md, markethours as mh
from app import strategies as S
from app.strategies import hk_crash as H
from conftest import NOW

P = H.HkCrashStrategy.default_params()


def _fr(o, l, c, g, tw):
    n = len(o)
    idx = pd.bdate_range("2026-03-02", periods=n, tz="UTC")
    fr = pd.DataFrame({"o": o, "h": np.maximum(o, c), "l": l, "c": c, "hs_ret": g, "tw": tw}, index=idx)
    fr["stopped"], fr["raw"] = False, False
    return fr


def test_big_crash_take_profit_at_the_next_open():
    #          day 0   1 (crash)   2 (opens +5%)   3
    fr = _fr(o=[10, 10, 10.5, 10.4], l=[9.9, 9.8, 10.3, 10.2], c=[10, 10.1, 10.4, 10.3], g=[0, -0.035, 0.01, 0], tw=[0, 0, 0, 0])
    W = H.walk(fr, P)
    assert list(W["big_new"]) == [False, True, False, False]
    assert list(W["open_w"]) == [0, 1, 0, 0]                     # bought at day 1's open, sold at day 2's open (+5% ≥ 4%)
    assert W["tp"].iloc[2]


def test_big_crash_held_two_days_without_take_profit():
    fr = _fr(o=[10, 10, 10.2, 10.1, 10], l=[9.9] * 5, c=[10] * 5, g=[0, -0.031, 0.0, 0.0, 0.0], tw=[0] * 5)
    W = H.walk(fr, P)
    assert list(W["open_w"]) == [0, 1, 1, 0, 0]                  # day 2 opens +2%: kept; sold at day 3's open
    assert not W["tp"].any()


def test_take_profit_waits_for_the_open():
    fr = _fr(o=[10, 10, np.nan], l=[9.9, 9.9, np.nan], c=[10, 10, np.nan], g=[0, -0.04, np.nan], tw=[0, 0, 0])
    W = H.walk(fr, P)
    assert W["tp_wait"].iloc[2] and W["big"].iloc[2]             # before today's open: the crash buy is kept for now


def test_small_crash_limit_fills_or_not_and_largest_part_wins():
    #           0     1 (−2%, low reaches 9.9)   2 (−2%, low stays above)   3 (−2% while trend holds 60%)
    fr = _fr(o=[10, 10, 10, 10], l=[9.95, 9.85, 9.95, 9.5], c=[10, 10, 10, 10], g=[0, -0.02, -0.02, -0.02], tw=[0, 0, 0.6, 0.6])
    W = H.walk(fr, P)
    assert W["small"].iloc[1] and W["fill"].iloc[1] and W["limit"].iloc[1] == pytest.approx(9.9)
    assert W["w"].iloc[1] == pytest.approx(0.4) and W["fill_px"].iloc[1] == pytest.approx(9.9)
    assert W["small"].iloc[2] and not W["fill"].iloc[2]          # not reached: nothing bought
    assert W["open_w"].iloc[3] == pytest.approx(0.6) and not W["fill"].iloc[3]   # the trend part (60%) is larger already


def test_hang_seng_close_counts_after_16_15_hong_kong():
    hs = pd.DataFrame({"c": [100.0, 96.0]}, index=pd.to_datetime(["2026-11-25", "2026-11-26"]).tz_localize("UTC"))
    before = datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc)           # 16:00 Hong Kong
    after = datetime(2026, 11, 26, 8, 20, tzinfo=timezone.utc)           # 16:20 Hong Kong (15:20 Bangkok)
    assert list(H.hk_closed(hs, before).index.date) == [pd.Timestamp("2026-11-25").date()]
    assert len(H.hk_closed(hs, after)) == 2
    assert len(H.hk_closed(hs, datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc))) == 1   # a later bar is never seen early


def test_trend_breakout_gate_size_and_trailing_stop():
    n = 260
    idx = pd.bdate_range("2025-01-01", periods=n, tz="UTC")
    k = np.r_[np.full(240, 30.0), [31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50]]
    kw = pd.DataFrame({"o": k, "h": k, "l": k, "c": k}, index=idx)
    fx = pd.DataFrame({"o": 1.0, "h": 1.0, "l": 1.0, "c": np.linspace(30, 40, n)}, index=idx)
    rng = np.random.default_rng(1)
    c = 20 * np.cumprod(1 + rng.normal(0, 0.02, n))
    c[-3:] = c[-4] * np.array([0.9, 0.8, 0.79])                     # CWEB falls > 15% from its high while KWEB still rises
    cw = pd.DataFrame({"o": c, "h": c, "l": c, "c": c}, index=idx)
    hs = pd.DataFrame({"c": np.full(n, 20000.0)}, index=idx)
    fr = H.signals(cw, kw, fx, hs, P)
    i = 240
    assert fr["don"].iloc[i] and fr["raw"].iloc[i] and fr["tw"].iloc[i] > 0     # breakout on the first close above the 20-day high
    assert fr["tw"].iloc[i] == pytest.approx(min(1.0, 0.30 / fr["vol"].iloc[i]))
    assert fr["stopped"].iloc[-1] and fr["tw"].iloc[-1] == 0 and fr["raw"].iloc[-1]   # trailing stop: out though the trend is on
    p0 = dict(P, trail_pct=0.0)
    assert H.signals(cw, kw, fx, hs, p0)["tw"].iloc[-1] > 0         # Pick 4 (no stop) stays in


def test_live_evaluation_and_backtest_run(clean):
    s = S.get("cweb_trend_crash")
    assert s is not None and "cweb_trend_crash" in S.QUIET_DEFAULTS    # added quietly (LINE off), with no money of its own
    ev = s.evaluate(NOW)
    assert ev["ok"], ev.get("error")
    assert ev["state"] in H.STATE_COLOR and set(ev["target"]) <= {"CWEB"}
    assert ev["detail"]["tiles"] and ev["checks"]
    r = BT.run("cweb_trend_crash")
    assert r["ok"], r.get("error")
    assert r["main"] == "CWEB" and r["index"] == "KWEB" and r["stats"]
    ch = s.chart(NOW, "8M")
    assert [c["id"] for c in ch["charts"]] == ["trade", "signal", "gate"]
    cols, rows, worst = s.check_table(NOW, 8)
    assert rows and worst < 1e-6


def test_hang_seng_is_downloaded_right_after_hong_kongs_close(monkeypatch):
    monkeypatch.setattr(md, "source", lambda: "yahoo")
    t = datetime(2026, 11, 26, 8, 20, tzinfo=timezone.utc)               # 16:20 Hong Kong
    last = datetime(2026, 11, 26, 7, 50, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr("time.time", lambda: t.timestamp())
    assert engine._daily_due("^HSI", t, last)                              # the close is final: download now
    assert not engine._daily_due("^HSI", t, t.timestamp() - 60)            # already have it


def _cweb_with_money(mode="paper"):
    s = S.get("cweb_trend_crash")
    if ledger.get(mode, s.id)["cash"] < 1000:
        db.run("UPDATE ledger SET cash=cash+10000, cap_in=COALESCE(cap_in,0)+10000 WHERE mode=? AND strategy=?", (mode, s.id))
    return s


def test_day_limit_is_one_order_at_its_price_not_repriced_and_cancelled_at_the_close(clean, clock):
    s = _cweb_with_money()
    L = ledger.get("paper", s.id)
    if L["cash"] < 1000:
        pytest.skip("no paper money for the strategy in this setup")
    b = brokers.get("paper")
    px = b.quote("CWEB")["price"]
    sess = mh.session_bounds(NOW.astimezone(mh.NY).date())
    lim = round(px * 0.9, 2)                                               # 10% under the market: will not fill
    ev = {"ok": True, "target": {"CWEB": 0.396}, "rest": {"CWEB": {"limit": lim, "until": int(sess[1].timestamp())}}}
    pid = X.reconcile("paper", s, ev, NOW, b, db.get_settings())
    plan = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    assert plan["lots"] == 1 and plan["rest"]
    X.process(clock.dt)
    o = db.one("SELECT * FROM orders WHERE plan_id=?", (pid,))
    assert o["status"] == "submitted" and o["limit_price"] == pytest.approx(lim)
    clock.advance(minutes=30)                                              # far past the normal re-pricing time
    X.process(clock.dt)
    o = db.one("SELECT * FROM orders WHERE plan_id=?", (pid,))
    assert o["status"] == "submitted" and o["retry"] == 0
    assert X.reconcile("paper", s, ev, clock.dt, b, db.get_settings()) is None        # no market top-up while it rests
    clock.set(sess[1] - timedelta(minutes=1, seconds=30))                  # under 2 minutes before the close: cancelled
    X.process(clock.dt)
    clock.advance(seconds=20)
    X.process(clock.dt)                                                    # … and read back as cancelled
    rows = db.rows("SELECT * FROM orders WHERE plan_id=?", (pid,))
    assert len(rows) == 1 and rows[0]["status"] == "cancelled"            # not sent again
    assert db.one("SELECT COUNT(*) n FROM events WHERE title LIKE 'Day limit not filled%'")["n"] == 1


def test_day_limit_fills_when_the_price_reaches_it(clean, clock):
    s = _cweb_with_money()
    if ledger.get("paper", s.id)["cash"] < 1000:
        pytest.skip("no paper money for the strategy in this setup")
    b = brokers.get("paper")
    px = b.quote("CWEB")["price"]
    sess = mh.session_bounds(NOW.astimezone(mh.NY).date())
    ev = {"ok": True, "target": {"CWEB": 0.396}, "rest": {"CWEB": {"limit": round(px * 1.02, 2), "until": int(sess[1].timestamp())}}}
    pid = X.reconcile("paper", s, ev, NOW, b, db.get_settings())
    for _ in range(5):
        clock.advance(minutes=1)
        X.process(clock.dt)
    o = db.one("SELECT * FROM orders WHERE plan_id=?", (pid,))
    assert o["status"] == "filled"
    assert ledger.get("paper", s.id)["holdings"].get("CWEB", 0) > 0
