"""Test setup: an empty data folder, offline demo prices (DATA_SOURCE=csv), no scheduler, a frozen clock.

Run:  ./.venv/bin/python -m pytest -q
"""
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="tsb-test-"))
os.environ.update({"DATA_DIR": str(TMP), "DATA_SOURCE": "csv", "SCHEDULER_ENABLED": "0", "COOKIE_SECURE": "0",
                   "SECRET_KEY": "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz", "APP_USERNAME": "", "APP_PASSWORD": ""})
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pytest  # noqa: E402

# Wednesday 21 Oct 2026, 15:00 UTC = 11:00 New York (market open), 22:00 Bangkok
NOW = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)

import make_demo_data  # noqa: E402

make_demo_data.main(TMP / "csv", 500, NOW)

from app import db, engine, marketdata as md, moneyops, notify  # noqa: E402
from app import strategies as S  # noqa: E402

_real_time = time.time


class Clock:
    """Freezes both the bot's market clock and time.time() at a datetime."""

    def __init__(self, mp):
        self.mp = mp
        self.set(NOW)

    def set(self, dt):
        self.dt = dt
        md.set_clock(dt)
        self.mp.setattr(time, "time", lambda: dt.timestamp())
        return dt

    def advance(self, **kw):
        from datetime import timedelta
        return self.set(self.dt + timedelta(**kw))


@pytest.fixture(scope="session", autouse=True)
def app_ready():
    md.set_clock(NOW)
    db.init()
    S.load_plugins()
    S.seed()
    engine.refresh_data(NOW, force=True)
    yield
    md.set_clock(None)


@pytest.fixture
def clock(monkeypatch):
    c = Clock(monkeypatch)
    yield c
    md.set_clock(NOW)


TABLES = ("ledger", "holdings", "money", "pool", "plans", "orders", "equity", "line_queue", "events", "signals", "strategy_state")


@pytest.fixture
def clean():
    """Empty books, orders and LINE queue; default settings; paper money seeded again."""
    with db.tx() as c:
        for t in TABLES:
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM state WHERE k NOT IN ('data_status') AND k NOT LIKE 'roll%' AND k NOT LIKE 'contract%'")
        c.execute("DELETE FROM settings")
        c.execute("UPDATE strategies SET control='active', line_on=1, exec=NULL")
    db.init()
    md.clear_quotes()
    notify.set_transport(None)
    moneyops.seed_paper()
    yield
    notify.set_transport(None)
    from app import brokers
    for m in brokers.MODES:
        brokers.set_override(m, None)
