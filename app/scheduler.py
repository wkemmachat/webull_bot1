"""Background loop inside the web server process (keep ONE copy of the bot with the scheduler on)."""
from __future__ import annotations

import logging
import threading
import time

from . import engine
from .config import TICK_SECONDS

log = logging.getLogger("scheduler")
_thread = None
_stop = threading.Event()


def _loop():
    time.sleep(2)
    while not _stop.is_set():
        try:
            engine.tick()
        except Exception:
            log.exception("tick failed")
        _stop.wait(TICK_SECONDS)


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="bot-scheduler", daemon=True)
    _thread.start()
    log.info("scheduler started (every %ss)", TICK_SECONDS)


def stop():
    _stop.set()


def run_now():
    threading.Thread(target=engine.tick, daemon=True).start()
