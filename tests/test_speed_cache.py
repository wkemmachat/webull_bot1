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
