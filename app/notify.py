"""LINE alerts (Messaging API push; LINE Notify closed on 31 Mar 2025).

Every alert is queued in `line_queue` first. Each event type is sent:
  instant  right away (several alerts in the same minute are joined into one message to save quota)
  digest   collected and sent at the digest times (default 08:00 and 21:00 Bangkok); paused from Saturday 12:00 to
           Monday 08:00 (Bangkok) unless switched off: what comes in then waits for Monday 08:00
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
    "system": ("Settings and strategy changes", "New strategies, Stop & sell, pausing trading and other changes. Deploys and "
               "normal restarts are only written to Logs.", "digest", False),
    "restart": ("Bot restarted unexpectedly", "The bot did not shut down normally (a crash, out of memory or the server lost "
                "power). Deploys and normal restarts send nothing.", "instant", False),
    "preview": ("Orders for the next US open", "After the US close: what each strategy will buy or sell at the next open "
                "(sells exact, buys estimated). Arrives after quiet hours.", "instant", False),
    "etf2x": ("New 2x ETF found", "Weekly search after the Nasdaq-100 ranking: a 2x ETF that passed the checks for a stock in the "
              "C2-7 2x list. Nothing changes until you add it on the strategy page.", "instant", False),
    "etfwatch": ("New 2x ETFs this week", "Saturday morning: an index, sector or commodity 2x ETF entered the top 50 by money traded a "
                 "day, or a new one was listed. It only reports; you decide what to research.", "instant", False),
    "dip": ("Good time to add money: a strategy reached its 85th percentile", "Once a day after the US close: a strategy fell "
            "deeper below its backtest high than on 85% of its past days, and in its backtest such falls were followed by gains "
            "(the times it got there and how many were up a year later, $1,000 typically became …). Only strategies where this "
            "worked; once per fall.", "instant", False),
    "pool_add": ("Pool: good time to add extra money", "Once per fall: the pool backtest of today's members fell deeper than the "
                 "chosen share of its past days (Pool settings → alerts). Again only after it climbs back above the 70th.", "instant", False),
    "pool_month": ("Pool: monthly add reminder", "On the chosen day each month (the next weekday if it is a weekend or US holiday).",
                   "instant", False),
    "pool_gap": ("Pool: real behind its backtest", "The real pool trails the backtest of the same members since the pool started by "
                 "more than the chosen points (checked after each close).", "instant", False),
    "drawdown": ("Deep fall: a strategy near or past its worst backtest fall", "Once a day after the US close: a strategy fell to 75% "
                 "of its worst fall in the last 10 years of its backtest, and again when it goes past it. Once per fall; with your own "
                 "money's fall in each mode. A warning only: nothing is sold.", "instant", False),
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


# ---------------------------------------------------------------- LINE follows the money
# With "Automatic" on (the default), a strategy's LINE switch is on while the strategy is not Stopped (Active, Paused or
# Stop & sell) and holds money: cash of at least $1 or any shares, in Live (or, when Live is off, in the modes that are on).
# The switches are rewritten every scheduler tick and whenever the LINE or Strategies page loads. A message is still sent
# while the switch is on from before, so the last messages of a strategy that is being emptied or stopped (the move, the
# final sale, "stopped") still arrive; the next sync then turns it off.
AUTO_MIN_CASH = 1.0


def line_auto() -> bool:
    return db.get_setting("line_auto", "1") == "1"


def money_modes(settings=None) -> list:
    from . import brokers
    m = brokers.enabled_modes(settings)
    return ["live"] if "live" in m else m


def auto_on(sid: str, control: str | None = None, modes: list | None = None) -> bool:
    if control is None:
        r = db.one("SELECT control FROM strategies WHERE id=?", (sid,))
        control = r["control"] if r else None
    if not control or control == "stopped":
        return False
    from . import pool
    for m in (money_modes() if modes is None else modes):
        if pool.is_member(m, sid):                 # a pool member's money is the pool: it gets money when its signal comes
            return True
        L = db.one("SELECT cash FROM ledger WHERE mode=? AND strategy=?", (m, sid))
        if L and (L["cash"] or 0) >= AUTO_MIN_CASH:
            return True
        if db.one("SELECT 1 FROM holdings WHERE mode=? AND strategy=? AND qty>1e-9", (m, sid)):
            return True
    return False


def sync_auto() -> list:
    """Write every strategy's automatic LINE switch. Returns [(id, on)] for the ones that changed (each one logged)."""
    from . import pool
    if not line_auto():
        return []
    modes = money_modes()
    changed = []
    for r in db.rows("SELECT id, name, control, line_on FROM strategies WHERE archived=0"):
        on = auto_on(r["id"], r["control"], modes)
        if bool(r["line_on"]) != on:
            db.run("UPDATE strategies SET line_on=? WHERE id=?", (1 if on else 0, r["id"]))
            changed.append((r["id"], on))
            why = ("a strategy pool member" if on and any(pool.is_member(m, r["id"]) for m in modes) else
                   "not Stopped and holds money") if on else ("Stopped" if r["control"] == "stopped" else "no money left")
            db.add_event("info", "line", f"{r['name']}: LINE alerts turned {'on' if on else 'off'} automatically", why,
                         strategy=r["id"])
    return changed


def send(event: str, text: str, strategy: str | None = None, title: str | None = None, critical: bool | None = None):
    """Queue an alert. Returns the queue id (or None when the strategy's LINE switch is off / event off)."""
    if event not in EVENTS:
        event = "system"
    crit = EVENTS[event][3] if critical is None else critical
    if strategy:
        r = db.one("SELECT line_on FROM strategies WHERE id=?", (strategy,))
        if r and not r["line_on"] and not crit and not (line_auto() and auto_on(strategy)):
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


_clock: dict = {"now": None}      # the dispatcher's "now" (tests pass a fixed time), for the monthly count


def _deliver(text: str, scope: str):
    """Send to every enabled recipient whose scope covers this message. Returns (ok, error). Each push to each recipient is
    one LINE message: counted for the monthly budget."""
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
    if sent:
        _count(sent, _clock["now"])
    if errs and not sent:
        return False, errs[0]
    return True, (errs[0] if errs else None)


# ---------------------------------------------------------------- monthly message budget (28 Nov 2026)
# LINE's free plan allows 300 messages a month and every push to every recipient counts. On 27 Nov 2026 the bot hit the
# limit (LINE answered 429) and the rest of the month's alerts, critical ones included, could not be sent. The budget
# spreads the month's messages over its days and keeps a reserve that only critical alerts may use.
BUDGET_DEFAULT = 300
RESERVE = 30            # kept for critical alerts (failed order, Webull disconnected, new sign-in, health problem)


def _month(now: datetime) -> str:
    return now.astimezone(TZ).strftime("%Y-%m")


def _count(n: int, now: datetime | None = None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    c = db.get_state("line_count") or {}
    if c.get("month") != _month(now):
        c = {"month": _month(now), "n": 0, "days": {}}
    day = now.strftime("%Y-%m-%d")
    c["n"] = int(c.get("n", 0)) + n
    c.setdefault("days", {})[day] = int(c["days"].get(day, 0)) + n
    db.set_state("line_count", c)


def budget_cap() -> int:
    try:
        cap = int(db.get_setting("line_budget") or BUDGET_DEFAULT)
    except ValueError:
        cap = BUDGET_DEFAULT
    q = db.get_state("line_quota") or {}
    if q.get("limit"):
        cap = min(cap, int(q["limit"]))
    return max(cap, 0)


def _digest_slots(day: datetime) -> list:
    times = sorted(db.get_json_setting("line_digest_times", ["08:00", "21:00"]))
    pause = weekend_pause_on()
    return [t for t in times if not (pause and weekend_paused(day, t))]


def budget(now: datetime | None = None) -> dict:
    """Where this month's LINE messages stand and what may be sent now.
    state: ok · tight (routine instant alerts wait for the digest) · low (one digest a day) · stop (critical only) · full."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    cap = budget_cap()
    c = db.get_state("line_count") or {}
    mine = int(c.get("n", 0)) if c.get("month") == _month(now) else 0
    today = now.strftime("%Y-%m-%d")
    today_used = int((c.get("days") or {}).get(today, 0)) if c.get("month") == _month(now) else 0
    q = db.get_state("line_quota") or {}
    used = mine
    if q.get("used") is not None and q.get("at") and _month(datetime.fromtimestamp(q["at"], TZ)) == _month(now):
        used = max(used, int(q["used"]))              # LINE's own count also has messages sent from elsewhere
    rec = [r for r in recipients() if r.get("enabled", True)]
    per_alert = max(1, sum(1 for r in rec if r.get("scope", "all") != "reports"))
    per_digest = max(1, len(rec))
    first = now.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    dim = (nxt - first).days
    days_left = dim - now.day + 1                      # today included
    left = cap - used
    reserve = min(RESERVE, cap // 10)
    free = left - reserve
    # what today may use: the room left at the start of today, spread over the days left (unused room carries on)
    allow_today = (free + today_used) / days_left if days_left else free
    m = now.hour * 60 + now.minute
    slots_today = _digest_slots(now)
    digests_left_today = sum(1 for t in slots_today if _hm(t) > m)
    # the month's remaining digests at two a day (or the times set) must fit in the free room; if not, one a day
    future = 0
    for d in range(1, days_left):
        future += len(_digest_slots(now + timedelta(days=d)))
    need_digests = (future + digests_left_today) * per_digest
    if left <= 0:
        state = "full"
    elif free <= 0:
        state = "stop"
    elif need_digests > free:
        state = "low"
    elif today_used + per_alert + digests_left_today * per_digest > allow_today:
        state = "tight"
    else:
        state = "ok"
    return {"cap": cap, "used": used, "left": max(left, 0), "free": max(int(free), 0), "reserve": reserve, "state": state,
            "text": BUDGET_TEXT[state],
            "today": today_used, "allow_today": max(int(allow_today), 0), "days_left": days_left,
            "per_alert": per_alert, "per_digest": per_digest, "month": _month(now)}


BUDGET_TEXT = {
    "ok": "On pace",
    "tight": "Today's share is used: routine instant alerts wait for the next digest",
    "low": "Running low: one digest a day, routine instant alerts wait for it",
    "stop": "Only critical alerts until the 1st: the rest stays on the site",
    "full": "Monthly limit reached: nothing more until the 1st",
}


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
    _clock["now"] = local
    if _transport["push"] is push:
        quota()                                       # LINE's own count, cached for an hour
    b = budget(local)
    # instant (and held) items
    items = db.rows("SELECT * FROM line_queue WHERE status IN ('pending','held','failed') AND delivery='instant' "
                    "AND attempts < 6 AND t > ? ORDER BY id", (int(time.time()) - 6 * 3600,))
    send_now = []
    for it in items:
        if b["state"] == "full" or (b["state"] == "stop" and not it["critical"]):
            db.run("UPDATE line_queue SET status='skipped', error=? WHERE id=?", (f"Monthly LINE budget ({b['cap']}) – shown on the site", it["id"]))
            continue
        if quiet and not it["critical"]:
            if it["status"] != "held":
                db.run("UPDATE line_queue SET status='held' WHERE id=?", (it["id"],))
            continue
        if b["state"] in ("tight", "low") and not it["critical"]:
            db.run("UPDATE line_queue SET delivery='digest', status='pending', error=? WHERE id=?",
                   ("Moved to the digest: monthly LINE budget", it["id"]))
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
    pause = weekend_pause_on()
    today = local.strftime("%Y-%m-%d")
    done = db.get_state("line_digest_done") or {}
    for hhmm in sorted(times):
        try:
            due = _hm(hhmm) <= local.hour * 60 + local.minute
        except ValueError:
            continue
        if due and done.get(hhmm) != today and pause and weekend_paused(local, hhmm):
            done[hhmm] = today                      # weekend pause: what was collected waits for Monday 08:00
            db.set_state("line_digest_done", done)
        elif due and done.get(hhmm) != today and local.hour * 60 + local.minute - _hm(hhmm) < 120:
            b = budget(local)
            slots = _digest_slots(local)
            if b["state"] in ("stop", "full"):
                _skip_digest(b)
            elif b["state"] == "low" and slots and hhmm != slots[0]:
                pass                                # one digest a day: what was collected waits for tomorrow's first
            else:
                send_digest(hhmm)
            done[hhmm] = today
            db.set_state("line_digest_done", done)
        elif due and done.get(hhmm) != today:
            done[hhmm] = today                      # missed by more than 2 hours (bot was off): skip, next digest picks it up
            db.set_state("line_digest_done", done)


def weekend_pause_on() -> bool:
    return (db.get_setting("line_weekend_pause") or "1") == "1"


def weekend_paused(day: datetime, hhmm: str) -> bool:
    """A digest time falls in the weekend pause: Saturday from 12:00 to Monday before 08:00 (Bangkok)."""
    wd, m = day.weekday(), _hm(hhmm)
    return (wd == 5 and m >= 12 * 60) or wd == 6 or (wd == 0 and m < 8 * 60)


def _skip_digest(b):
    db.run("UPDATE line_queue SET status='skipped', error=? WHERE delivery='digest' AND status IN ('pending','failed')",
           (f"Monthly LINE budget ({b['cap']}) – shown on the site",))


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
    """The next digest as text: "08:00" today or tomorrow, "Mon 08:00" further out (the weekend pause)."""
    t = next_digest_at(now)
    if t is None:
        return None
    now = (now or datetime.now(TZ)).astimezone(TZ)
    return t.strftime("%H:%M") if (t.date() - now.date()).days <= 1 else t.strftime("%a %H:%M")


def next_digest_at(now: datetime | None = None):
    """The next digest time (Bangkok), or None."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    times = sorted(db.get_json_setting("line_digest_times", ["08:00", "21:00"]))
    pause = weekend_pause_on()
    for d in range(0, 4):
        for hhmm in times:
            try:
                h, m = (int(x) for x in hhmm.split(":"))
            except ValueError:
                continue
            t = (now + timedelta(days=d)).replace(hour=h, minute=m, second=0, microsecond=0)
            if t > now and not (pause and weekend_paused(t, hhmm)):
                return t
    return None


def summary() -> dict:
    since = int(time.time()) - 86400
    r = db.one("SELECT SUM(status='sent') sent, SUM(status='failed') failed, SUM(status IN ('pending','held')) waiting "
               "FROM line_queue WHERE t>=?", (since,))
    return {"sent_24h": r["sent"] or 0, "failed_24h": r["failed"] or 0, "waiting": r["waiting"] or 0,
            "configured": configured(), "next_digest": next_digest(), "quota": db.get_state("line_quota") or {},
            "budget": budget()}


def recent(limit=20):
    return db.rows("SELECT id,t,event,strategy,title,text,critical,delivery,status,sent_at,error FROM line_queue "
                   "WHERE status<>'skipped' OR error LIKE 'Monthly LINE budget%' ORDER BY id DESC LIMIT ?", (limit,))


def settings_public() -> dict:
    s = db.get_settings()
    tok = s.get("line_token") or ""
    return {"token_set": bool(tok), "token_hint": ("…" + tok[-6:]) if tok else "", "recipients": recipients(),
            "digest_times": db.get_json_setting("line_digest_times", ["08:00", "21:00"]), "quiet": s.get("line_quiet") == "1",
            "quiet_from": s.get("line_quiet_from"), "quiet_to": s.get("line_quiet_to"), "lang": s.get("line_lang"),
            "detail": s.get("line_detail"), "per_strategy": s.get("line_per_strategy") == "1",
            "weekend_pause": weekend_pause_on(), "auto": s.get("line_auto", "1") == "1",
            "budget": int(s.get("line_budget") or BUDGET_DEFAULT),
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
    if d.get("budget") not in (None, ""):
        n = int(d["budget"])
        if not 20 <= n <= 100000:
            raise ValueError("Monthly message budget: 20 to 100,000")
        upd["line_budget"] = str(n)
    for k in ("quiet", "per_strategy", "auto", "weekend_pause"):
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
