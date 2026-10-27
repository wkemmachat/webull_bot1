"""Webull login (token) reminders. Webull's OpenAPI tokens last 15 days by default and must be renewed by hand
(Webull page → Reconnect, then the SMS code in the Webull app within 5 minutes).

LINE: one message when 5, 3 and 1 day(s) are left, and one when it has ended. If the bot was off past a step, only the
nearest step is sent (no burst of old reminders). A renewed token (new end date) starts the steps again.
Home: logins() feeds a banner from 5 days before the end.
"""
from __future__ import annotations

import time
from datetime import datetime

from . import brokers, db, notify
from .config import DISPLAY_TZ

STEPS = (5, 3, 1)
WARN_DAYS = 5


def _fmt(t):
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(t, ZoneInfo(DISPLAY_TZ)).strftime("%a %d %b %H:%M")


def logins(now=None) -> list:
    """[{mode, label, ends, days_left, status}] for the enabled Webull modes whose token end date is known."""
    now = now or time.time()
    out = []
    for mode in brokers.enabled_modes():
        if mode == "paper":
            continue
        try:
            st = brokers.get(mode).status()
        except Exception:
            continue
        lap = st.get("lapses_at")
        if not lap:
            continue
        left = (lap - now) / 86400
        out.append({"mode": mode, "label": brokers.MODE_LABEL[mode], "ends": int(lap), "ends_text": _fmt(lap),
                    "days_left": round(left, 2), "status": "ended" if left <= 0 else ("soon" if left <= WARN_DAYS else "ok")})
    return out


def check(now=None) -> list:
    """Send the due LINE reminders. Returns what was sent (for tests and the log)."""
    now = now or time.time()
    sent = []
    for x in logins(now):
        key = f"token_alert:{x['mode']}"
        st = db.get_state(key) or {}
        if st.get("ends") != x["ends"]:                       # a new token: start the reminders again
            st = {"ends": x["ends"], "sent": []}
        left = x["days_left"]
        due = None
        if left <= 0:
            due = 0
        else:
            crossed = [d for d in STEPS if left <= d]
            if crossed:
                due = min(crossed)
        if due is not None and due not in st["sent"]:
            st["sent"] = sorted(set(st["sent"]) | {d for d in STEPS if d >= due} | ({0} if due == 0 else set()))
            if due == 0:
                txt = (f"Webull {x['label']} login has ENDED ({x['ends_text']}). The bot cannot send orders until you reconnect: "
                       "Webull page → Reconnect, then enter the SMS code in the Webull app (Menu → Messages → OpenAPI "
                       "Notifications) within 5 minutes.")
            else:
                n = max(1, int(left + 0.999)) if left > 1 else 1
                txt = (f"Webull {x['label']} login ends in {n} day{'s' if n > 1 else ''} ({x['ends_text']} Bangkok). Renew it: "
                       "Webull page → Reconnect, then enter the SMS code in the Webull app within 5 minutes. Best while the US "
                       "market is closed.")
            notify.send("broker", txt, critical=(due <= 1))
            db.add_event("warn" if due else "error", "webull", f"Webull {x['label']} login: {'ended' if due == 0 else f'{due} day(s) left'}",
                         txt, mode=x["mode"])
            sent.append((x["mode"], due))
        db.set_state(key, st)
    return sent
