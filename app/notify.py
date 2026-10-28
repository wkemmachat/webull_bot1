"""LINE alerts (Messaging API push; LINE Notify closed on 31 Mar 2025).

Every alert is queued in `line_queue` first. Each event type is sent:
  instant  right away (several alerts in the same minute are joined into one message to save quota)
  digest   collected and sent at the digest times (default 08:00 and 21:00 Bangkok)
  off      not sent (still listed in Logs)
Quiet hours hold instant alerts until they end, except CRITICAL ones (a failed order, Webull disconnected,
a new sign-in, a health-check problem). Each strategy has its own LINE switch (Strategies page).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from . import db
from .config import APP_NAME, DISPLAY_TZ, PUBLIC_URL

log = logging.getLogger("notify")
TZ = ZoneInfo(DISPLAY_TZ)
PUSH_URL = "https://api.line.me/v2/bot/message/push"
QUOTA_URL = "https://api.line.me/v2/bot/message/quota"
USAGE_URL = "https://api.line.me/v2/bot/message/quota/consumption"
MAX_LEN = 4900

# event key: (label, description, default delivery, critical)
EVENTS = {
    "signal": ("Buy / sell signal", "A strategy decided to enter or exit, with the numbers it used.", "instant", False),
    "regime": ("Regime state change", "QLD or Semis moved between 2x, 1x, 0.5x and off.", "instant", False),
    "plan_start": ("Plan started", "The first lot of a split plan went out.", "digest", False),
    "plan_done": ("Plan finished", "Summary: shares, average price, slippage vs the first quote.", "instant", False),
    "lot_filled": ("Every lot filled", "One message per lot. Noisy, off by default.", "off", False),
    "lot_failed": ("Lot failed after retries", "Webull refused or never filled the lot.", "instant", True),
    "money": ("Money added, withdrawn or moved", "Confirmation with the new capital.", "instant", False),
    "report": ("Daily report per strategy", "Value, state, holdings and the day's fills.", "digest", False),
    "health_problem": ("Health check: problem", "Books differ from Webull, a missed step, a stuck order…", "instant", True),
    "health_warning": ("Health check: warning", "Something to look at, not urgent.", "digest", False),
    "data": ("Data problem", "Prices could not be downloaded (at most one alert per 6 hours).", "instant", False),
    "broker": ("Webull disconnected or token expiring", "Webull's login token is ending or was refused; approve again in the Webull app.", "instant", True),
    "login": ("Sign-in from a new device", "Or 5 wrong passwords in a row.", "instant", True),
    "system": ("Bot started / stopped / updated", "Server restarts and settings changes.", "digest", False),
    "preview": ("Orders for the next US open", "After the US close: what each strategy will buy or sell at the next open "
                "(sells exact, buys estimated). Arrives after quiet hours.", "instant", False),
    "etf2x": ("New 2x ETF found", "Weekly search after the Nasdaq-100 ranking: a 2x ETF that passed the checks for a stock in the "
              "C2-7 2x list. Nothing changes until you add it on the strategy page.", "instant", False),
    "dip": ("Strong buy zone: a strategy reached its 80th percentile", "Once a day after the US close: a strategy fell deeper below its "
            "backtest high than on 80% of its days in the last 10 years (a buy-the-dip zone in the research). Once per dip.",
            "instant", False),
    "weekly": ("Weekly report (Saturday morning)", "Each strategy's real week next to its backtest over the same days, fees, and the "
               "real cost of trading (fills vs the day's open, where the daily backtests fill).", "instant", False),
    "review": ("Expected returns: yearly check", "The yearly backtest check of every strategy's expected return, and a monthly "
               "reminder while the research review is due.", "instant", False),
}


def event_modes() -> dict:
    saved = db.get_json_setting("line_events", {})
    out = {}
    for k, (_, _, default, critical) in EVENTS.items():
        m = saved.get(k, default)
        if critical and m == "off":
            m = "instant"
        out[k] = m
    return out


def recipients() -> list:
    r = db.get_json_setting("line_recipients", [])
    return [x for x in r if x.get("id")]


def configured() -> bool:
    return bool(db.get_setting("line_token")) and any(x.get("enabled", True) for x in recipients())


def send(event: str, text: str, strategy: str | None = None, title: str | None = None, critical: bool | None = None):
    """Queue an alert. Returns the queue id (or None when the strategy's LINE switch is off / event off)."""
    if event not in EVENTS:
        event = "system"
    crit = EVENTS[event][3] if critical is None else critical
    if strategy:
        r = db.one("SELECT line_on FROM strategies WHERE id=?", (strategy,))
        if r and not r["line_on"] and not crit:
            return None
    mode = event_modes().get(event, "instant")
    status = "skipped" if mode == "off" else "pending"
    cur = db.run("INSERT INTO line_queue(t,event,strategy,title,text,critical,delivery,status) VALUES(?,?,?,?,?,?,?,?)",
                 (int(time.time()), event, strategy, title or EVENTS[event][0], text, 1 if crit else 0, mode, status))
    return cur.lastrowid


# ---------------------------------------------------------------- LINE API
def push(to: str, text: str, token: str | None = None):
    token = (token or db.get_setting("line_token") or "").strip()
    if not token or not to:
        return False, "LINE channel access token or recipient is not set (LINE alerts page)"
    try:
        r = httpx.post(PUSH_URL, timeout=15, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       json={"to": to.strip(), "messages": [{"type": "text", "text": text[:MAX_LEN]}]})
    except Exception as e:
        return False, f"Could not reach LINE: {e}"
    if r.status_code == 200:
        return True, None
    try:
        msg = r.json().get("message", r.text)
    except Exception:
        msg = r.text
    hints = {401: " (check the channel access token)", 400: " (check the user/group ID: it starts with U or C)",
             429: " (monthly message quota reached or too many requests)"}
    return False, f"LINE error {r.status_code}: {msg}{hints.get(r.status_code, '')}"


_transport = {"push": push}


def set_transport(fn):
    """Tests: replace the LINE call."""
    _transport["push"] = fn or push


def quota(force=False) -> dict:
    """{'limit', 'used'} from LINE's quota API, cached for an hour."""
    q = db.get_state("line_quota") or {}
    if not force and time.time() - q.get("at", 0) < 3600:
        return q
    token = (db.get_setting("line_token") or "").strip()
    if not token:
        return {}
    try:
        h = {"Authorization": f"Bearer {token}"}
        a = httpx.get(QUOTA_URL, headers=h, timeout=10).json()
        b = httpx.get(USAGE_URL, headers=h, timeout=10).json()
        q = {"limit": a.get("value") if a.get("type") == "limited" else None, "type": a.get("type"),
             "used": b.get("totalUsage"), "at": int(time.time())}
        db.set_state("line_quota", q)
    except Exception as e:
        log.warning("LINE quota: %s", e)
    return q


# ---------------------------------------------------------------- dispatcher (called every tick)
def _hm(s: str):
    h, m = (int(x) for x in s.split(":"))
    return h * 60 + m


def in_quiet(now_local: datetime) -> bool:
    if db.get_setting("line_quiet") != "1":
        return False
    a, b = _hm(db.get_setting("line_quiet_from") or "00:30"), _hm(db.get_setting("line_quiet_to") or "07:00")
    m = now_local.hour * 60 + now_local.minute
    return (a <= m < b) if a < b else (m >= a or m < b)


def _deliver(text: str, scope: str):
    """Send to every enabled recipient whose scope covers this message. Returns (ok, error)."""
    errs, sent = [], 0
    for r in recipients():
        if not r.get("enabled", True):
            continue
        if r.get("scope", "all") == "reports" and scope != "report":
            continue
        ok, err = _transport["push"](r["id"], text)
        if ok:
            sent += 1
        else:
            errs.append(err)
    if errs and not sent:
        return False, errs[0]
    return True, (errs[0] if errs else None)


def _header(kind: str) -> str:
    return f"{APP_NAME} · {kind}"


def _strategy_name(sid):
    r = db.one("SELECT name FROM strategies WHERE id=?", (sid,)) if sid else None
    return r["name"] if r else "Bot"


def dispatch(now: datetime | None = None):
    if not configured():
        return
    now = now or datetime.now(TZ)
    local = now.astimezone(TZ)
    quiet = in_quiet(local)
    q = db.get_state("line_quota") or {}
    near_limit = q.get("limit") and q.get("used") is not None and q["used"] >= 0.9 * q["limit"]
    # instant (and held) items
    items = db.rows("SELECT * FROM line_queue WHERE status IN ('pending','held','failed') AND delivery='instant' "
                    "AND attempts < 6 AND t > ? ORDER BY id", (int(time.time()) - 6 * 3600,))
    send_now = []
    for it in items:
        if quiet and not it["critical"]:
            if it["status"] != "held":
                db.run("UPDATE line_queue SET status='held' WHERE id=?", (it["id"],))
            continue
        if near_limit and not it["critical"]:
            db.run("UPDATE line_queue SET delivery='digest', status='pending' WHERE id=?", (it["id"],))
            continue
        send_now.append(it)
    if send_now:
        text = "\n\n".join(it["text"] for it in send_now)
        if len(send_now) > 1:
            text = f"{_header(str(len(send_now)) + ' alerts')}\n\n" + text
        ok, err = _deliver(text + f"\n{PUBLIC_URL}", "alert")
        ids = [it["id"] for it in send_now]
        with db.tx() as c:
            for i in ids:
                c.execute("UPDATE line_queue SET status=?, sent_at=?, attempts=attempts+1, error=? WHERE id=?",
                          ("sent" if ok else "failed", int(time.time()) if ok else None, err, i))
        if not ok:
            db.add_event("error", "line", "LINE alert not delivered", err or "")
    # digests
    times = db.get_json_setting("line_digest_times", ["08:00", "21:00"])
    today = local.strftime("%Y-%m-%d")
    done = db.get_state("line_digest_done") or {}
    for hhmm in sorted(times):
        try:
            due = _hm(hhmm) <= local.hour * 60 + local.minute
        except ValueError:
            continue
        if due and done.get(hhmm) != today and local.hour * 60 + local.minute - _hm(hhmm) < 120:
            send_digest(hhmm)
            done[hhmm] = today
            db.set_state("line_digest_done", done)
        elif due and done.get(hhmm) != today:
            done[hhmm] = today                      # missed by more than 2 hours (bot was off): skip, next digest picks it up
            db.set_state("line_digest_done", done)


def send_digest(label: str = "") -> bool:
    items = db.rows("SELECT * FROM line_queue WHERE delivery='digest' AND status IN ('pending','failed') AND attempts<6 ORDER BY id")
    if not items:
        return True
    per = db.get_setting("line_per_strategy") == "1"
    groups: dict = {}
    for it in items:
        groups.setdefault(it["strategy"] if per else "*", []).append(it)
    ok_all = True
    for sid, its in groups.items():
        title = _strategy_name(sid) if sid not in ("*", None) else "Bot"
        reports = [i for i in its if i["event"] == "report"]
        other = [i for i in its if i["event"] != "report"]
        parts = [f"{_header('Digest ' + label)}{' · ' + title if per else ''}"]
        lines, seen = [], {}
        for i in other:                                  # the same message several times (e.g. "Bot started.") once, with a count
            t = i["text"]
            if t in seen:
                seen[t] += 1
            else:
                seen[t] = 1
                lines.append(t)
        parts += [i["text"] for i in reports] + [("• " + t.replace("\n", "\n  ") + (f" (×{seen[t]})" if seen[t] > 1 else ""))
                                                   for t in lines]
        ok, err = _deliver("\n".join(parts)[:MAX_LEN], "report" if reports and not other else "alert")
        with db.tx() as c:
            for i in its:
                c.execute("UPDATE line_queue SET status=?, sent_at=?, attempts=attempts+1, error=? WHERE id=?",
                          ("sent" if ok else "failed", int(time.time()) if ok else None, err, i["id"]))
        ok_all = ok_all and ok
    return ok_all


def test_message():
    return _deliver(f"{_header('test')}\nTest message from your bot. LINE alerts are working. ✅\n{PUBLIC_URL}", "alert")


def preview() -> list:
    """Two sample messages for the LINE page."""
    return [
        "BUY · Silver #1 (Donchian 30/15)\n4H close 52.48 > 30-bar high 52.31\nPlan: sell 145 SGOV → buy ≈199 AGQ\n10 lots × 10 min from 22:00 BKK",
        "Morning report · Thu 22 Oct\nBot $116,135 · day +1.12%\nGold #1 LONG UGL · +9.2%\nQLD regime 2x · +9.9%\nCheck: 12 ok · 1 warning",
    ]


def next_digest(now: datetime | None = None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    times = sorted(db.get_json_setting("line_digest_times", ["08:00", "21:00"]))
    for d in (0, 1):
        for hhmm in times:
            try:
                h, m = (int(x) for x in hhmm.split(":"))
            except ValueError:
                continue
            t = (now + timedelta(days=d)).replace(hour=h, minute=m, second=0, microsecond=0)
            if t > now:
                return t.strftime("%H:%M")
    return None


def summary() -> dict:
    since = int(time.time()) - 86400
    r = db.one("SELECT SUM(status='sent') sent, SUM(status='failed') failed, SUM(status IN ('pending','held')) waiting "
               "FROM line_queue WHERE t>=?", (since,))
    return {"sent_24h": r["sent"] or 0, "failed_24h": r["failed"] or 0, "waiting": r["waiting"] or 0,
            "configured": configured(), "next_digest": next_digest(), "quota": db.get_state("line_quota") or {}}


def recent(limit=20):
    return db.rows("SELECT id,t,event,strategy,title,text,critical,delivery,status,sent_at,error FROM line_queue "
                   "WHERE status<>'skipped' ORDER BY id DESC LIMIT ?", (limit,))


def settings_public() -> dict:
    s = db.get_settings()
    tok = s.get("line_token") or ""
    return {"token_set": bool(tok), "token_hint": ("…" + tok[-6:]) if tok else "", "recipients": recipients(),
            "digest_times": db.get_json_setting("line_digest_times", ["08:00", "21:00"]), "quiet": s.get("line_quiet") == "1",
            "quiet_from": s.get("line_quiet_from"), "quiet_to": s.get("line_quiet_to"), "lang": s.get("line_lang"),
            "detail": s.get("line_detail"), "per_strategy": s.get("line_per_strategy") == "1",
            "events": [{"key": k, "label": v[0], "desc": v[1], "critical": v[3], "mode": event_modes()[k]} for k, v in EVENTS.items()]}


def save_settings(d: dict):
    upd = {}
    if d.get("token"):
        upd["line_token"] = d["token"].strip()
    if "recipients" in d:
        rec = []
        for r in d["recipients"] or []:
            rid = str(r.get("id", "")).strip()
            if not rid:
                continue
            if rid[0] not in "UCR":
                raise ValueError(f"LINE ID '{rid}' should start with U (user), C (group) or R (room)")
            rec.append({"id": rid, "name": str(r.get("name") or "")[:40], "enabled": bool(r.get("enabled", True)),
                        "scope": "reports" if r.get("scope") == "reports" else "all"})
        upd["line_recipients"] = json.dumps(rec)
    if "digest_times" in d:
        ts = []
        for t in d["digest_times"] or []:
            h, m = (int(x) for x in str(t).split(":"))
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError(f"Bad time {t}")
            ts.append(f"{h:02d}:{m:02d}")
        upd["line_digest_times"] = json.dumps(sorted(set(ts)))
    for k in ("quiet_from", "quiet_to"):
        if k in d:
            h, m = (int(x) for x in str(d[k]).split(":"))
            upd[f"line_{k}"] = f"{h:02d}:{m:02d}"
    for k in ("quiet", "per_strategy"):
        if k in d:
            upd[f"line_{k}"] = "1" if d[k] else "0"
    for k in ("lang", "detail"):
        if k in d:
            upd[f"line_{k}"] = str(d[k])
    if "events" in d:
        cur = db.get_json_setting("line_events", {})
        for k, m in (d["events"] or {}).items():
            if k in EVENTS and m in ("instant", "digest", "off"):
                cur[k] = "instant" if (EVENTS[k][3] and m == "off") else m
        upd["line_events"] = json.dumps(cur)
    db.set_settings(upd)
