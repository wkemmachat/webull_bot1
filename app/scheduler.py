"""Background loop inside the web server process (keep ONE copy of the bot with the scheduler on)."""
from __future__ import annotations

import logging
import threading
import time

from . import engine, execution
from .config import TICK_SECONDS

ORDERS_SECONDS = 5          # the order loop: fills, cancels, re-pricing and the next lots, apart from the slow tick

log = logging.getLogger("scheduler")
_thread = None
_othread = None
_stop = threading.Event()


def _loop():
    time.sleep(2)
    while not _stop.is_set():
        try:
            engine.tick()
        except Exception:
            log.exception("tick failed")
        _stop.wait(TICK_SECONDS)


def _orders_loop():
    """Orders on their own: checked every few seconds while any are working or due, so price refreshes and strategy
    checks in the tick (which can take a minute at the open) never hold up a fill, a cancel or the next lot."""
    time.sleep(5)
    while not _stop.is_set():
        try:
            if execution.orders_busy():
                execution.process()
        except Exception:
            log.exception("order loop failed")
        _stop.wait(ORDERS_SECONDS)


def start():
    global _thread, _othread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="bot-scheduler", daemon=True)
    _thread.start()
    _othread = threading.Thread(target=_orders_loop, name="bot-orders", daemon=True)
    _othread.start()
    log.info("scheduler started (every %ss; orders every %ss)", TICK_SECONDS, ORDERS_SECONDS)


def stop():
    _stop.set()


def run_now():
    threading.Thread(target=engine.tick, daemon=True).start()
