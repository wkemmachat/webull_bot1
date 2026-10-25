"""SQLite storage: one file (data/bot.db) holds settings, strategies, money, orders, prices and logs.

Every helper opens a short-lived connection per thread (WAL mode), so the web server and the
scheduler thread can read and write at the same time.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from .config import DB_PATH, SECRET_KEY

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT, t INTEGER);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  created_at INTEGER, pw_changed_at INTEGER, last_login INTEGER);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id INTEGER, created_at INTEGER, last_seen INTEGER, ip TEXT, ua TEXT,
  expires_at INTEGER, revoked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, username TEXT, t INTEGER, ok INTEGER);

CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, color TEXT, params TEXT, exec TEXT,
  control TEXT DEFAULT 'active', line_on INTEGER DEFAULT 1, archived INTEGER DEFAULT 0, sort INTEGER DEFAULT 0,
  created_at INTEGER, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS strategy_state (
  strategy TEXT PRIMARY KEY, computed_at INTEGER, bar_time INTEGER, state TEXT, label TEXT, target TEXT,
  signal_time INTEGER, ok INTEGER, error TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT, strategy TEXT, t INTEGER, kind TEXT, from_state TEXT, to_state TEXT,
  price REAL, text TEXT, source TEXT, created_at INTEGER, UNIQUE(strategy, t, to_state));

CREATE TABLE IF NOT EXISTS bars (
  symbol TEXT, tf TEXT, t INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, PRIMARY KEY (symbol, tf, t));
CREATE TABLE IF NOT EXISTS rolls (
  symbol TEXT, t INTEGER, ratio REAL, gap REAL, ignored INTEGER DEFAULT 0, source TEXT, note TEXT,
  detected_at INTEGER, PRIMARY KEY (symbol, t));

CREATE TABLE IF NOT EXISTS ledger (
  mode TEXT, strategy TEXT, cash REAL DEFAULT 0, cap_in REAL DEFAULT 0, cap_out REAL DEFAULT 0,
  start_t INTEGER, hold_cash INTEGER DEFAULT 0, hold_amt REAL DEFAULT 0, applied_target TEXT, updated_at INTEGER, PRIMARY KEY (mode, strategy));
-- the bot's own unassigned cash per mode: money you gave the bot that no strategy has yet
CREATE TABLE IF NOT EXISTS pool (mode TEXT PRIMARY KEY, cash REAL DEFAULT 0, cap_in REAL DEFAULT 0, cap_out REAL DEFAULT 0, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS holdings (
  mode TEXT, strategy TEXT, symbol TEXT, qty REAL DEFAULT 0, cost REAL DEFAULT 0, PRIMARY KEY (mode, strategy, symbol));
CREATE TABLE IF NOT EXISTS money (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, t INTEGER, kind TEXT, strategy TEXT, other TEXT, amount REAL,
  invest TEXT, status TEXT, note TEXT, plan_id INTEGER, done_at INTEGER, done_amount REAL);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, strategy TEXT, reason TEXT, status TEXT, created_at INTEGER,
  start_at INTEGER, finished_at INTEGER, target TEXT, note TEXT, on_done TEXT, lots INTEGER, interval_min REAL,
  signal_id INTEGER, summary TEXT);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER, mode TEXT, strategy TEXT, step INTEGER, lot INTEGER,
  lots INTEGER, symbol TEXT, side TEXT, qty REAL, plan_qty REAL, limit_price REAL, session TEXT,
  scheduled_at INTEGER, status TEXT, client_order_id TEXT, broker_order_id TEXT, submitted_at INTEGER,
  filled_qty REAL DEFAULT 0, avg_price REAL, applied_qty REAL DEFAULT 0, applied_value REAL DEFAULT 0,
  error TEXT, retry INTEGER DEFAULT 0, checks INTEGER DEFAULT 0, updated_at INTEGER);
CREATE INDEX IF NOT EXISTS orders_plan ON orders(plan_id);
CREATE INDEX IF NOT EXISTS orders_mode_status ON orders(mode, status);

CREATE TABLE IF NOT EXISTS equity (
  mode TEXT, t INTEGER, strategy TEXT, value REAL, capital REAL, bench REAL, PRIMARY KEY (mode, t, strategy));
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER, level TEXT, source TEXT, strategy TEXT, mode TEXT,
  title TEXT, message TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS events_t ON events(t);
CREATE TABLE IF NOT EXISTS line_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER, event TEXT, strategy TEXT, title TEXT, text TEXT,
  critical INTEGER DEFAULT 0, delivery TEXT, status TEXT, sent_at INTEGER, attempts INTEGER DEFAULT 0, error TEXT);
CREATE INDEX IF NOT EXISTS line_status ON line_queue(status);
CREATE TABLE IF NOT EXISTS test_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, symbol TEXT, qty REAL, status TEXT, created_at INTEGER,
  updated_at INTEGER, finished_at INTEGER, side TEXT, cid TEXT, limit_price REAL, sent_at INTEGER, tries INTEGER DEFAULT 0,
  bought REAL DEFAULT 0, buy_value REAL DEFAULT 0, buy_fee REAL DEFAULT 0, buy_secs REAL,
  sold REAL DEFAULT 0, sell_value REAL DEFAULT 0, sell_fee REAL DEFAULT 0, sell_secs REAL,
  o_filled REAL DEFAULT 0, o_value REAL DEFAULT 0, o_fee REAL DEFAULT 0, first_sent INTEGER,
  result TEXT, error TEXT, code TEXT, raw TEXT, log TEXT);
CREATE INDEX IF NOT EXISTS test_trades_mode ON test_trades(mode, status);
CREATE TABLE IF NOT EXISTS c27_rank (week TEXT, rank INTEGER, symbol TEXT, mcap REAL, created_at INTEGER, PRIMARY KEY (week, symbol));
CREATE TABLE IF NOT EXISTS health_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER, ok INTEGER, warn INTEGER,
  err INTEGER, report TEXT);
"""

# Settings and their defaults. Values are stored as text.
DEFAULTS = {
    # trading modes: paper runs inside the bot; test = Webull test server; live = your real Webull account
    "mode_paper": "1", "mode_test": "0", "mode_live": "0",
    "paper_start_cash": "100000", "paper_strategy_cash": "10000", "paper_fee_pct": "0.0", "paper_spread_pct": "0.05",
    "follow_current_signal": "1",            # (old setting, replaced by new_money_start)
    "new_money_start": "now",
    "protect_floor_paper": "0", "protect_floor_test": "0", "protect_floor_live": "0",   # Webull cash the bot never spends below                # new money: "now" = follow today's signal · "buy" = keep cash until the next BUY signal
    "trading_paused": "0",                   # kill switch: no new orders are sent while 1
    # execution defaults (strategies may override)
    "exec_lots": "10", "exec_interval_min": "10", "exec_start_mode": "time", "exec_start_time": "22:00",
    "exec_exit_mode": "asap", "exec_session": "CORE", "exec_limit_offset_pct": "0.10", "exec_retries": "3",
    "exec_min_lot_usd": "200", "exec_min_trade_usd": "100", "exec_max_order_usd": "25000", "exec_cash_buffer_pct": "1.0",
    # LINE
    "line_token": "", "line_recipients": "[]", "line_digest_times": '["08:00","21:00"]', "line_quiet": "1",
    "line_quiet_from": "00:30", "line_quiet_to": "07:00", "line_lang": "en", "line_detail": "full", "line_per_strategy": "1",
    "line_events": "{}",
    # Webull
    "webull_region": "th", "webull_app_key": "", "webull_app_secret": "", "webull_account_id": "",
    "webull_test_app_key": "", "webull_test_app_secret": "", "webull_test_account_id": "", "webull_test_endpoint": "",
    # data + display
    "metals_source": "yahoo", "show_thb": "0", "usdthb": "", "theme": "dark",
    "health_time_ny": "16:45", "backup_keep_days": "30",
}
SECRET_KEYS = {"line_token", "webull_app_secret", "webull_test_app_secret", "webull_app_key", "webull_test_app_key"}


def _connect():
    c = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def con():
    c = getattr(_local, "c", None)
    if c is None:
        c = _connect()
        _local.c = c
    return c


# columns added after the first release: (table, column, definition)
MIGRATIONS = [("ledger", "hold_amt", "REAL DEFAULT 0"), ("orders", "fee", "REAL DEFAULT 0"), ("plans", "goal", "TEXT")]


def init():
    c = con()
    c.executescript(SCHEMA)
    for table, col, ddl in MIGRATIONS:
        have = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in have:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    return c


@contextmanager
def tx():
    c = con()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def rows(sql, args=()):
    return [dict(r) for r in con().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = con().execute(sql, args).fetchone()
    return dict(r) if r else None


def run(sql, args=()):
    return con().execute(sql, args)


# ---------------------------------------------------------------- secrets (Fernet with a key from SECRET_KEY)
_fernet = None


def _f():
    global _fernet
    if _fernet is None:
        try:
            from cryptography.fernet import Fernet
            _fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(("tsb:" + SECRET_KEY).encode()).digest()))
        except ImportError:
            _fernet = False
    return _fernet


def _enc(v: str) -> str:
    f = _f()
    if not v or not f:
        return v
    return "enc:" + f.encrypt(v.encode()).decode()


def _dec(v: str) -> str:
    if not v or not str(v).startswith("enc:"):
        return v
    f = _f()
    if not f:
        return ""
    try:
        return f.decrypt(v[4:].encode()).decode()
    except Exception:
        return ""


# ---------------------------------------------------------------- settings + state
def get_settings() -> dict:
    out = dict(DEFAULTS)
    for r in rows("SELECT k, v FROM settings"):
        out[r["k"]] = _dec(r["v"]) if r["k"] in SECRET_KEYS else r["v"]
    return out


def get_setting(k, default=None):
    r = one("SELECT v FROM settings WHERE k=?", (k,))
    if r is None:
        return DEFAULTS.get(k, default)
    return _dec(r["v"]) if k in SECRET_KEYS else r["v"]


def set_settings(d: dict):
    with tx() as c:
        for k, v in d.items():
            v = "" if v is None else (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                      (k, _enc(v) if k in SECRET_KEYS else v))


def get_json_setting(k, default):
    try:
        v = json.loads(get_setting(k) or "null")
        return default if v is None else v
    except ValueError:
        return default


def get_state(k, default=None):
    r = one("SELECT v FROM state WHERE k=?", (k,))
    if not r:
        return default
    try:
        return json.loads(r["v"])
    except ValueError:
        return default


def set_state(k, v):
    run("INSERT INTO state(k,v,t) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, t=excluded.t",
        (k, json.dumps(v), int(time.time())))


# ---------------------------------------------------------------- events (the Logs page)
def add_event(level, source, title, message="", strategy=None, mode=None, detail=None):
    cur = run("INSERT INTO events(t,level,source,strategy,mode,title,message,detail) VALUES(?,?,?,?,?,?,?,?)",
              (int(time.time()), level, source, strategy, mode, title, message,
               json.dumps(detail) if isinstance(detail, (dict, list)) else detail))
    return cur.lastrowid


def prune(days_events=180, days_line=120):
    now = int(time.time())
    with tx() as c:
        c.execute("DELETE FROM events WHERE t < ?", (now - days_events * 86400,))
        c.execute("DELETE FROM line_queue WHERE t < ? AND status IN ('sent','skipped')", (now - days_line * 86400,))
        c.execute("DELETE FROM login_attempts WHERE t < ?", (now - 30 * 86400,))
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
