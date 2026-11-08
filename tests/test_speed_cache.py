"""Speed: a backtest stays cached until its own prices change (not every hour, not on another symbol's new bar)."""
from app import backtest, db
from app import strategies as S


def test_backtest_key_ignores_other_symbols_and_todays_moving_bar(clean, clock):
    s = S.get("qld_tbd")                                   # QQQ signal, QLD trade
    k0 = backtest._key(s, 0.0011, 0)
    db.run("INSERT OR REPLACE INTO bars(symbol,tf,t,o,h,l,c,v) VALUES('GC','1h',?,1,1,1,1,1)", (2 ** 31,))
    assert backtest._key(s, 0.0011, 0) == k0             # a gold hourly bar does not touch a QLD strategy
    clock.advance(hours=2)
    assert backtest._key(s, 0.0011, 0) == k0             # nor does the clock, within the same New York day
    r = db.one("SELECT t FROM bars WHERE symbol='QQQ' AND tf='1d' ORDER BY t DESC LIMIT 1")
    db.run("UPDATE bars SET c=c+1 WHERE symbol='QQQ' AND tf='1d' AND t=?", (r["t"],))
    assert backtest._key(s, 0.0011, 0) != k0             # its own closed prices do


def test_fast_open_close_reader_matches_the_row_loop():
    """backtest._oc reads the columns directly; it must give exactly what the old per-row loop gave."""
    from datetime import date
    import pandas as pd
    from app import backtest
    idx = pd.date_range("2026-01-02 14:30", periods=40, freq="D", tz="UTC")
    df = pd.DataFrame({"o": [100 + i * 0.5 for i in range(40)], "c": [101 + i * 0.25 for i in range(40)]}, index=idx)
    old = {pd.Timestamp(t).date(): (float(r.o), float(r.c)) for t, r in df.iterrows()}
    assert backtest._oc(df) == old
    d2 = df.copy(); d2.index = [t.date() for t in idx]                     # basket prices: plain dates
    assert backtest._oc(d2) == old
    assert backtest._oc(None) == {} and backtest._oc(df.iloc[:0]) == {}


def test_ranking_lookup_matches_a_scan():
    from app import basket
    r = basket.ranks()
    ws = sorted(r["week"].unique())
    for day in (ws[0], ws[len(ws) // 2], ws[-1]):
        w, rk = basket.ranking_for(day)
        sub = r[r["week"] == max(x for x in ws if x <= day)].sort_values("rank")
        assert w == day and rk == list(zip(sub["symbol"], sub["mcap"].astype(float)))
    assert basket.ranking_for(ws[0].replace(year=ws[0].year - 1)) == (None, [])


def test_ranking_estimated_when_yahoo_gives_no_market_caps(monkeypatch):
    """7 Nov 2026: Yahoo stopped giving market caps. The weekly ranking moves last week's caps by each stock's price change."""
    import sys, types
    from datetime import datetime, timezone, timedelta
    from app import basket, db, marketdata as md
    fake = types.ModuleType("yfinance")

    class T:
        def __init__(self, s):
            self.fast_info = {}                                  # no market cap for anyone
    fake.Ticker = T
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    monkeypatch.setattr(md, "source", lambda: "yahoo")
    r = basket.ranks()
    last = max(r["week"])
    friday = last + timedelta(days=7)
    now = datetime(friday.year, friday.month, friday.day, 23, 0, tzinfo=timezone.utc)
    try:
        n = basket.update_live(now)
        assert n >= 40
        new = db.rows("SELECT symbol, mcap FROM c27_rank WHERE week=? ORDER BY rank", (str(friday),))
        assert len(new) == n and {x["symbol"] for x in new} <= set(r[r["week"] == last]["symbol"])
        ev = db.rows("SELECT level, title, message FROM events WHERE title LIKE 'Nasdaq-100 ranking%' ORDER BY id DESC LIMIT 1")[0]
        assert ev["level"] == "warn" and ev["title"] == "Nasdaq-100 ranking estimated" and "estimated" in ev["message"]
    finally:
        db.run("DELETE FROM c27_rank WHERE week=?", (str(friday),))
        basket.clear_cache()
