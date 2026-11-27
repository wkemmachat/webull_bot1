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


def _fill(side, price, t, mode="live", symbol="AIBU"):
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,limit_price,status,retry,scheduled_at,"
           "filled_qty,avg_price,updated_at) VALUES(998,?,'aibu_s2pp',1,1,1,?,?,10,0,'filled',0,0,10,?,?)",
           (mode, symbol, side, price, int(t)))


def test_own_fill_newer_than_the_quote_sets_the_price(clean):
    """27 Nov: AIBU's quote said $46.69 a minute after the bot bought at $45.30; the sell limit sat above the market."""
    old_q = {"price": 46.69, "bid": None, "ask": None, "time": OPEN_TS - 17 * 3600}
    _fill("BUY", 45.30, NOW.timestamp() - 60)
    o = {**_o(side="SELL"), "symbol": "AIBU", "mode": "live"}
    assert X.lot_limit(o, old_q, "SELL", 0.001, NOW) == round(round(45.30 * 0.999, 2) * 0.995, 2)  # from the fill, past the spread
    assert X.lot_limit({**o, "mode": "paper"}, old_q, "SELL", 0.001, NOW) < 46.69     # another mode's fill does not count
    newer = {"price": 45.80, "bid": 45.75, "ask": 45.85, "time": NOW.timestamp() - 5}
    assert X.lot_limit(o, newer, "SELL", 0.001, NOW) == round(45.75 * 0.999, 2)      # a newer quote wins
    _fill("BUY", 44.00, NOW.timestamp() - 3 * 3600, symbol="AIBX")
    assert X.own_fill("live", "AIBX", int(NOW.timestamp()) - X.OWN_FILL_S) is None    # too old to be a price


def test_an_old_quote_lets_retries_move_further(clean):
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,limit_price,status,retry,scheduled_at,updated_at) "
           "VALUES(999,'live','rom_tbd',1,1,2,'ROM','SELL',15,100.0,'cancelled',0,0,0)")
    old_q = {"price": 100.1, "bid": None, "ask": None, "time": NOW.timestamp() - 1200}    # no trade for 20 minutes
    assert X.lot_limit(_o(9, "SELL"), old_q, "SELL", 0.001, NOW) == round(100.0 * 0.955, 2)  # 4.5%, past the 2% cap
    assert X.lot_limit(_o(20, "SELL"), old_q, "SELL", 0.001, NOW) == round(100.0 * 0.95, 2)  # capped at 5%


def test_test_trade_sells_from_its_own_buy(clean):
    from app import testtrade
    db.run("INSERT INTO test_trades(mode,symbol,qty,status,created_at,updated_at,bought,buy_value,sold,sell_value) "
           "VALUES('live','AIBU',1,'selling',?,?,1,45.30,0,0)", (int(NOW.timestamp()) - 60, int(NOW.timestamp()) - 30))
    stale = {"price": 46.69, "bid": None, "ask": None, "time": OPEN_TS - 17 * 3600}
    assert testtrade._test_limit(stale, "SELL", 0, "AIBU", "live", NOW) == round(round(45.30 * 0.999, 2) * 0.995, 2)
    assert testtrade._test_limit(stale, "SELL", 0, "AIBU") == round(round(46.69 * 0.999, 2) * 0.995, 2)  # old call: as before
