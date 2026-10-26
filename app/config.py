"""Settings read from the environment (.env). Everything else lives in the database and is edited in the app."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR") or (BASE_DIR / "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH") or (DATA_DIR / "bot.db"))
CSV_DIR = DATA_DIR / "csv"
BACKUP_DIR = Path(os.getenv("BACKUP_DIR") or (DATA_DIR / "backups"))

APP_NAME = os.getenv("APP_NAME", "Webull Strategy Bot")
DISPLAY_TZ = os.getenv("DISPLAY_TZ", "Asia/Bangkok")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "1") == "1"
# yahoo = live data from Yahoo Finance (default) · csv = offline files in data/csv (tests and demos)
DATA_SOURCE = os.getenv("DATA_SOURCE", "yahoo")
TICK_SECONDS = int(os.getenv("TICK_SECONDS", "30"))

# Optional first user. If not set, the app asks you to create a username and password on first open.
APP_USERNAME = os.getenv("APP_USERNAME", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


def _secret_key() -> str:
    """SECRET_KEY from .env, else a random key kept in data/secret.key (created on first start)."""
    k = os.getenv("SECRET_KEY", "").strip()
    if k and k not in ("replace-with-a-long-random-string", "change-me") and len(k) >= 32:
        return k
    p = DATA_DIR / "secret.key"
    if p.exists():
        return p.read_text().strip()
    k = secrets.token_urlsafe(48)
    p.write_text(k)
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return k


SECRET_KEY = _secret_key()
