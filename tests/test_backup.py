"""23 Nov 2026: small nightly backups kept 7 days, a secret-free download, the Dashboard reminder."""
import gzip
import sqlite3
import time

from app import db, engine
from app.config import BACKUP_DIR
from test_api import client, sign_in  # noqa: F401  (fixture)


def _seed():
    old = int(time.time()) - 800 * 86400
    new = int(time.time()) - 5 * 86400
    db.run("DELETE FROM bars WHERE symbol IN ('ZZQ','ZZG')")
    db.run("INSERT INTO bars(symbol,tf,t,o,h,l,c,v) VALUES('ZZQ','1d',?,1,1,1,1,1)", (new,))
    db.run("INSERT INTO bars(symbol,tf,t,o,h,l,c,v) VALUES('ZZG','1h',?,1,1,1,1,1)", (new,))
    db.run("INSERT INTO bars(symbol,tf,t,o,h,l,c,v) VALUES('ZZG','1h',?,1,1,1,1,1)", (old,))    # older than Yahoo keeps
    db.set_state("data_updated:ZZQ:1d", int(time.time()))
    db.set_state("bt_upd:ZZQ:1dtr", int(time.time()))
    db.set_settings({"line_token": "SECRET-LINE", "webull_app_secret": "SECRET-WB"})


def _open(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def test_nightly_backup_is_small_checked_and_keeps_secrets(clean):
    _seed()
    p = engine.backup()
    c = _open(p)
    cut = int(time.time()) - 700 * 86400
    assert not c.execute("SELECT 1 FROM bars WHERE NOT (tf='1h' AND t<?)", (cut,)).fetchall()
    bars = c.execute("SELECT symbol, tf FROM bars WHERE symbol IN ('ZZQ','ZZG')").fetchall()
    assert [(r["symbol"], r["tf"]) for r in bars] == [("ZZG", "1h")]         # only the hourly bar Yahoo no longer has
    assert not c.execute("SELECT 1 FROM state WHERE k LIKE 'data_updated:%' OR k LIKE 'bt_upd:%'").fetchall()
    tok = c.execute("SELECT v FROM settings WHERE k='line_token'").fetchone()["v"]
    assert tok and tok != ""                                                  # stays (encrypted) on the server
    assert db.get_state("backup_last")["ok"] is True
    assert db.one("SELECT * FROM events WHERE title='Database backup' ORDER BY id DESC LIMIT 1")["message"].endswith("checked")
    assert db.one("SELECT COUNT(*) n FROM bars WHERE symbol IN ('ZZQ','ZZG')")["n"] == 3   # the live database is untouched


def test_keeps_7_days(clean):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for f in BACKUP_DIR.glob("bot-*.db"):
        f.unlink()
    for d in range(1, 11):
        (BACKUP_DIR / f"bot-2026-10-{d:02d}.db").write_bytes(b"x")
    engine.backup()
    assert len(list(BACKUP_DIR.glob("bot-*.db"))) == 7


def test_download_has_no_secrets(clean):
    _seed()
    gz = engine.backup_download()
    assert gz.name.endswith("-no-secrets.db.gz")
    raw = gz.with_suffix("")
    raw.write_bytes(gzip.decompress(gz.read_bytes()))
    c = _open(raw)
    s = {r["k"]: r["v"] for r in c.execute("SELECT k, v FROM settings")}
    for k in db.SECRET_KEYS:
        assert not s.get(k)
    assert all(r["pw_hash"] == "" for r in c.execute("SELECT pw_hash FROM users"))
    assert not c.execute("SELECT 1 FROM sessions").fetchall() and not c.execute("SELECT 1 FROM login_attempts").fetchall()
    assert c.execute("SELECT COUNT(*) FROM bars WHERE symbol IN ('ZZQ','ZZG')").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM strategies").fetchone()[0] > 0     # the rest is all there
    assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert db.get_state("backup_downloaded")["name"] == gz.name


def test_restored_copy_downloads_prices_again(clean, monkeypatch):
    """After a restore the bars are gone and the 'last downloaded' marks too: the first update asks for the full history."""
    from app import marketdata as md
    import pandas as pd
    db.run("DELETE FROM bars WHERE symbol='ZZR'")
    asked = {}
    monkeypatch.setattr(md, "fetch", lambda sym, tf, days: asked.setdefault(tf, days) and pd.DataFrame(columns=list("ohlcv")))
    md.update("ZZR", "1d")
    assert asked["1d"] == 365 * 6


def test_reminder(clean):
    db.run("DELETE FROM state WHERE k='backup_downloaded'")
    r = engine.backup_reminder()
    assert r and r["last"] is None
    db.set_state("backup_downloaded", {"at": int(time.time()) - 2 * 86400, "name": "x", "size": 1})
    assert engine.backup_reminder() is None
    db.set_state("backup_downloaded", {"at": int(time.time()) - 9 * 86400, "name": "x", "size": 1})
    assert engine.backup_reminder()["days"] == 9


def test_api_download_and_dashboard(client):
    sign_in(client)
    db.run("DELETE FROM state WHERE k='backup_downloaded'")
    assert client.get("/api/dashboard?mode=paper").json()["backup"]["last"] is None
    r = client.get("/api/backup")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/gzip")
    assert gzip.decompress(r.content)[:16] == b"SQLite format 3\x00"
    assert client.get("/api/dashboard?mode=paper").json()["backup"] is None
    srv = client.get("/api/settings").json()["server"]
    assert srv["backup_keep"] == 7 and srv["backup_downloaded"]
