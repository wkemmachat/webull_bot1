"""Orders for the next US open: sells exact, buys estimated, the LINE preview."""
from datetime import datetime, timezone

import pytest

from app import brokers, db, execution as X, ledger, notify, preview as P
from app import strategies as S
from conftest import NOW


def test_queued_plan_shows_what_will_trade(clean, clock):
    after_close = datetime(2026, 10, 21, 21, 30, tzinfo=timezone.utc)      # 17:30 New York: decided, waits for the open
    clock.set(after_close)
    s = S.get("qld_regime")
    pid = X.build_plan("paper", s, {"QLD": 0.99}, "signal", after_close, brokers.get("paper"))
    assert pid
    d = P.next_orders("paper")
    assert d["rows"] and d["next_start"] and d["next_start"] > int(after_close.timestamp())
    r = d["rows"][0]
    assert r["strategy"] == "qld_regime" and r["state"] == "queued" and r["after"] == {"QLD": 0.99}
    buy = next(i for i in r["items"] if i["side"] == "BUY")
    L = ledger.value("paper", "qld_regime")
    assert not buy["exact"] and buy["symbol"] == "QLD" and buy["price"] > 0
    assert buy["value"] == pytest.approx(0.99 * L["value"], rel=0.02) and buy["qty"] == int(buy["value"] // buy["price"])
    assert d["buys"] == pytest.approx(buy["value"], rel=1e-6) and d["sells"] == 0
    # only this strategy on its own page
    assert P.next_orders("paper", "qld_regime")["rows"] and not P.next_orders("paper", "gold_sta")["rows"]
    # LINE text names the strategy and the order
    txt = P.line_text("paper")
    assert "qld regime" in txt.lower() and "buy ≈" in txt and "QLD" in txt
    sent = []
    orig = notify.send
    notify.send = lambda ev, text, **k: sent.append((ev, text))
    try:
        P.send_preview(after_close)
    finally:
        notify.send = orig
    assert sent and sent[0][0] == "preview"


def test_sells_are_exact(clean, clock):
    s = S.get("qld_regime")
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    from test_execution import run_until_done
    run_until_done(clock, pid)
    held = ledger.get("paper", "qld_regime")["holdings"]["QLD"]
    after_close = datetime(2026, 10, 22, 21, 30, tzinfo=timezone.utc)
    clock.set(after_close)
    pid2 = X.build_plan("paper", s, s.cash_target(), "signal", after_close, brokers.get("paper"))
    r = P.next_orders("paper", "qld_regime")["rows"][0]
    sell = next(i for i in r["items"] if i["side"] == "SELL")
    assert sell["exact"] and sell["symbol"] == "QLD" and sell["qty"] == int(held) and sell["left"] == int(held)


def test_nothing_waiting(clean):
    assert P.next_orders("paper")["rows"] == [] and P.line_text("paper") is None
