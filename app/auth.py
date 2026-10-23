"""Sign-in with a username and password.

- Passwords are stored as PBKDF2-SHA256 hashes (200,000 rounds, random salt).
- A signed cookie carries a random session id; sessions are listed in Settings and can be signed out.
- After 5 wrong passwords (per username or per IP) sign-in is locked for 15 minutes and LINE is told.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from itsdangerous import BadSignature, URLSafeSerializer

from . import db
from .config import APP_PASSWORD, APP_USERNAME, SECRET_KEY

COOKIE = "tsb_session"
REMEMBER_S = 30 * 86400
SHORT_S = 12 * 3600
LOCK_AFTER = 5
LOCK_S = 15 * 60
_ser = URLSafeSerializer(SECRET_KEY, salt="tsb-session")


def hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"


def check_pw(pw: str, stored: str) -> bool:
    try:
        _, salt, hx = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000)
    return hmac.compare_digest(dk.hex(), hx)


def ensure_env_user():
    """Create the first user from APP_USERNAME / APP_PASSWORD in .env if no user exists yet."""
    if APP_USERNAME and APP_PASSWORD and not db.one("SELECT id FROM users LIMIT 1"):
        create_user(APP_USERNAME, APP_PASSWORD)


def needs_setup() -> bool:
    return db.one("SELECT id FROM users LIMIT 1") is None


USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._@+-]{2,63}$")


def validate_new(username: str, pw: str):
    if not USERNAME_RE.match(username or ""):
        raise ValueError("Username: 3–64 characters, letters and digits; an email address is fine (. _ - @ + allowed, no spaces)")
    if len(pw) < 10:
        raise ValueError("Password: at least 10 characters")
    if pw.strip().lower() == username:
        raise ValueError("Password: must not be the same as the username")


def create_user(username: str, pw: str):
    """The bot has ONE login. A second user cannot be created (use reset_password to change it)."""
    username = username.strip().lower()
    validate_new(username, pw)
    if db.one("SELECT id FROM users LIMIT 1"):
        raise ValueError("This bot already has its login. Sign in, or reset it with: python -m app.reset_password")
    now = int(time.time())
    db.run("INSERT INTO users(username,pw_hash,created_at,pw_changed_at) VALUES(?,?,?,?)", (username, hash_pw(pw), now, now))


def change_password(user_id: int, old: str, new: str, keep_session: str | None = None):
    u = db.one("SELECT * FROM users WHERE id=?", (user_id,))
    if not u or not check_pw(old, u["pw_hash"]):
        raise ValueError("The current password is not right")
    validate_new(u["username"], new)
    with db.tx() as c:
        c.execute("UPDATE users SET pw_hash=?, pw_changed_at=? WHERE id=?", (hash_pw(new), int(time.time()), user_id))
        c.execute("UPDATE sessions SET revoked=1 WHERE user_id=? AND id<>?", (user_id, keep_session or ""))


def _locked(ip: str, username: str) -> int:
    since = int(time.time()) - LOCK_S
    r = db.one("SELECT COUNT(*) n, MAX(t) last FROM login_attempts WHERE ok=0 AND t>=? AND (ip=? OR username=?)",
               (since, ip, username))
    if (r["n"] or 0) >= LOCK_AFTER:
        return int((r["last"] or 0) + LOCK_S - time.time())
    return 0


def login(username: str, pw: str, ip: str, ua: str, remember: bool):
    """Returns (cookie_value, max_age). Raises PermissionError (locked) or ValueError (wrong)."""
    from . import notify
    username = (username or "").strip().lower()
    wait = _locked(ip, username)
    if wait > 0:
        raise PermissionError(f"Too many wrong tries. Try again in {max(1, wait // 60)} min.")
    u = db.one("SELECT * FROM users WHERE username=?", (username,))
    ok = bool(u) and check_pw(pw, u["pw_hash"])
    db.run("INSERT INTO login_attempts(ip,username,t,ok) VALUES(?,?,?,?)", (ip, username, int(time.time()), 1 if ok else 0))
    if not ok:
        if _locked(ip, username) > 0:
            db.add_event("warn", "login", "Sign-in locked", f"{LOCK_AFTER} wrong passwords from {ip} (user '{username}')")
            notify.send("login", f"Sign-in locked for 15 minutes: {LOCK_AFTER} wrong passwords from {ip}.", critical=True)
        raise ValueError("Wrong username or password")
    now = int(time.time())
    seen = db.one("SELECT id FROM sessions WHERE user_id=? AND ip=? AND ua=? AND created_at>?",
                  (u["id"], ip, ua[:200], now - 90 * 86400))
    sid = secrets.token_urlsafe(32)
    age = REMEMBER_S if remember else SHORT_S
    with db.tx() as c:
        c.execute("INSERT INTO sessions(id,user_id,created_at,last_seen,ip,ua,expires_at) VALUES(?,?,?,?,?,?,?)",
                  (sid, u["id"], now, now, ip, ua[:200], now + age))
        c.execute("UPDATE users SET last_login=? WHERE id=?", (now, u["id"]))
    db.add_event("info", "login", "Signed in", f"{u['username']} from {ip} · {device_name(ua)}")
    if not seen and db.one("SELECT COUNT(*) n FROM sessions WHERE user_id=?", (u["id"],))["n"] > 1:
        notify.send("login", f"New sign-in: {u['username']} from {ip} ({device_name(ua)}).", critical=True)
    return _ser.dumps(sid), age


def session_from_cookie(value: str | None):
    if not value:
        return None
    try:
        sid = _ser.loads(value)
    except BadSignature:
        return None
    s = db.one("SELECT s.*, u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?", (sid,))
    now = int(time.time())
    if not s or s["revoked"] or s["expires_at"] < now:
        return None
    if now - (s["last_seen"] or 0) > 300:
        db.run("UPDATE sessions SET last_seen=? WHERE id=?", (now, sid))
    return s


def logout(value: str | None):
    s = session_from_cookie(value)
    if s:
        db.run("UPDATE sessions SET revoked=1 WHERE id=?", (s["id"],))


def device_name(ua: str) -> str:
    ua = ua or ""
    os_ = "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Android" if "Android" in ua else \
        "Mac" if "Mac OS" in ua else "Windows" if "Windows" in ua else "Linux" if "Linux" in ua else "device"
    br = "Edge" if "Edg/" in ua else "Chrome" if "Chrome/" in ua else "Firefox" if "Firefox/" in ua else \
        "Safari" if "Safari/" in ua else "browser"
    return f"{br} on {os_}"
