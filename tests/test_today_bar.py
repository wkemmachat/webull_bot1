"""Strategy charts show today's bar so far after the last closed daily bar (drawn lighter); the signal still uses closed bars."""
from datetime import datetime, timezone

from app import marketdata as md
from app import strategies as S


def _daily_sig(spec):
    return next(c for c in spec["charts"] if c["title"].endswith(" · 1D"))


def test_today_bar_added_during_the_session(clean, clock):
    clock.set(datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc))       # Tue 11:00 New York (the demo data has this day)
    md._tbcache.clear()
    s = S.get("qld_tbd")
    spec = s.chart(md.now_utc(), "3M")
    last_closed = _daily_sig(spec)["candles"][-1]["time"]
    md.add_today_bars(spec)
    c = _daily_sig(spec)["candles"]
    today = int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp())
    assert last_closed < today and c[-1]["time"] == today and c[-1]["today"] == "live"
    assert c[-1]["low"] <= c[-1]["close"] <= c[-1]["high"] and "rgba" in c[-1]["color"]
    assert all(x.get("today") is None for x in c[:-1])
    for ch in spec["charts"]:                                              # the trade chart (QLD) gets it too
        if ch["title"].endswith(" · 1D"):
            assert ch["candles"][-1]["time"] == today
    # the strategy's own decision is unchanged: it still reads the last closed bar
    assert s.frame(md.now_utc()).index[-1].timestamp() == last_closed


def test_no_today_bar_before_the_open_or_on_a_weekend(clean, clock):
    for dt in (datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc),       # 08:00 New York, before the open
               datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)):      # Saturday
        clock.set(dt)
        md._tbcache.clear()
        spec = S.get("qld_tbd").chart(md.now_utc(), "3M")
        n = len(_daily_sig(spec)["candles"])
        md.add_today_bars(spec)
        assert len(_daily_sig(spec)["candles"]) == n


def test_closed_after_the_bell(clean, clock):
    clock.set(datetime(2026, 10, 20, 20, 2, tzinfo=timezone.utc))        # 16:02 New York, before the 16:05 cut-off
    md._tbcache.clear()
    spec = md.add_today_bars(S.get("qld_tbd").chart(md.now_utc(), "3M"))
    assert _daily_sig(spec)["candles"][-1]["today"] == "closed"
