"""Limit prices for thin ETFs: a quote with no trade yet today is widened, and every retry chases the price."""
from datetime import datetime, timezone

from app import db, execution as X

NOW = datetime(2026, 10, 27, 13, 36, tzinfo=timezone.utc)           # 09:36 New York, a trading day
OPEN_TS = datetime(2026, 10, 27, 13, 30, tzinfo=timezone.utc).timestamp()


def _o(retry=0, side="BUY"):
    return {"plan_id": 999, "lot": 1, "symbol": "ROM", "retry": retry, "session": "CORE", "side": side}


def test_fresh_quote_is_unchanged():
    q = {"price": 146.0, "bid": None, "ask": None, "time": OPEN_TS + 60}
    assert X.lot_limit(_o(), q, "BUY", 0.001, NOW) == round(146.0 * 1.001, 2)


def test_quote_from_before_the_open_is_widened():
    q = {"price": 143.04, "bid": None, "ask": None, "time": OPEN_TS - 17 * 3600}   # yesterday's close
    assert X.lot_limit(_o(), q, "BUY", 0.001, NOW) == round(round(143.04 * 1.001, 2) * 1.005, 2)
    assert X.lot_limit(_o(side="SELL"), q, "SELL", 0.001, NOW) == round(round(143.04 * 0.999, 2) * 0.995, 2)
    q["ask"] = 145.0                                                              # a real ask: used as is
    assert X.lot_limit(_o(), q, "BUY", 0.001, NOW) == round(145.0 * 1.001, 2)


def test_retries_chase_from_the_first_limit(clean):
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,limit_price,status,retry,scheduled_at,updated_at) "
           "VALUES(999,'live','rom_tbd',1,1,2,'ROM','BUY',15,143.18,'cancelled',0,0,0)")
    stale = {"price": 143.04, "bid": None, "ask": None, "time": OPEN_TS + 60}
    assert X.lot_limit(_o(1), stale, "BUY", 0.001, NOW) == round(143.18 * 1.005, 2)    # same quote: still moves up
    assert X.lot_limit(_o(3), stale, "BUY", 0.001, NOW) == round(143.18 * 1.015, 2)
    assert X.lot_limit(_o(9), stale, "BUY", 0.001, NOW) == round(143.18 * 1.02, 2)     # capped
    fresh = {"price": 146.13, "bid": None, "ask": None, "time": OPEN_TS + 600}
    assert X.lot_limit(_o(1), fresh, "BUY", 0.001, NOW) == round(146.13 * 1.001, 2)    # the market is higher: follow it
