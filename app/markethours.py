"""US stock/ETF trading sessions (New York time) for scheduling ETF orders.

Sessions (Webull `support_trading_session`):
  CORE  regular hours      09:30–16:00 ET (13:00 on early-close days)
  ALL   with extended hours 04:00–20:00 ET (17:00 on early-close days)
Bangkok time: CORE is 20:30–03:00 while US daylight time is on (Mar–Nov) and 21:30–04:00 in winter.
Holidays are the NYSE calendar; update HOLIDAYS / EARLY_CLOSE each year (the broker rejects
orders on a day we missed, and the bot then retries at the next session).
"""
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
BKK = ZoneInfo("Asia/Bangkok")

HOLIDAYS = {
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
    date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31), date(2027, 6, 18),
    date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
    # 2028
    date(2028, 1, 17), date(2028, 2, 21), date(2028, 4, 14), date(2028, 5, 29), date(2028, 6, 19), date(2028, 7, 4),
    date(2028, 9, 4), date(2028, 11, 23), date(2028, 12, 25),
}
EARLY_CLOSE = {date(2026, 11, 27), date(2026, 12, 24), date(2027, 11, 26), date(2028, 7, 3), date(2028, 11, 24)}

SESSIONS = {"CORE": (dtime(9, 30), dtime(16, 0), dtime(13, 0)),
            "ALL": (dtime(4, 0), dtime(20, 0), dtime(17, 0))}


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def session_bounds(d: date, session: str = "CORE"):
    """(open, close) as aware UTC datetimes for New York date d, or None if no session."""
    if not is_trading_day(d):
        return None
    o, c, early = SESSIONS.get(session, SESSIONS["CORE"])
    if d in EARLY_CLOSE:
        c = early
    return (datetime.combine(d, o, NY).astimezone(timezone.utc), datetime.combine(d, c, NY).astimezone(timezone.utc))


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_open(dt, session: str = "CORE") -> bool:
    dt = _utc(dt)
    b = session_bounds(dt.astimezone(NY).date(), session)
    return bool(b) and b[0] <= dt < b[1]


def current_close(dt, session: str = "CORE"):
    dt = _utc(dt)
    b = session_bounds(dt.astimezone(NY).date(), session)
    return b[1] if b and b[0] <= dt < b[1] else None


def next_open(dt, session: str = "CORE"):
    """dt itself if the session is open, else the next session open."""
    dt = _utc(dt)
    if is_open(dt, session):
        return dt
    d = dt.astimezone(NY).date()
    for k in range(0, 15):
        b = session_bounds(d + timedelta(days=k), session)
        if b and b[0] > dt:
            return b[0]
    raise RuntimeError("no session found in the next 15 days")


def start_time(now, mode: str = "time", hhmm: str = "22:00", session: str = "CORE"):
    """When an order plan may start.
    mode 'asap': as soon as the session is open (now if it is open).
    mode 'time': never before HH:MM Bangkok. If the session is open now and today's HH:MM has
    already passed inside this session (a signal at 01:15 or 22:15), start now. Otherwise the next
    HH:MM Bangkok time that falls inside the session on a US trading day; if that clock time is
    never inside the session, fall back to the next session open."""
    now = _utc(now)
    if mode != "time":
        return next_open(now, session)
    try:
        h, m = (int(x) for x in str(hhmm).split(":"))
    except ValueError:
        h, m = 22, 0
    local = now.astimezone(BKK)
    b = session_bounds(now.astimezone(NY).date(), session)
    if b and b[0] <= now < b[1]:
        for k in (-1, 0):                       # the session can start on the previous Bangkok day
            cand = datetime.combine(local.date() + timedelta(days=k), dtime(h, m), BKK).astimezone(timezone.utc)
            if b[0] <= cand <= now:
                return now
    for k in range(0, 15):
        cand = datetime.combine(local.date() + timedelta(days=k), dtime(h, m), BKK).astimezone(timezone.utc)
        if cand >= now - timedelta(seconds=30) and is_open(cand, session):
            return max(cand, now)
    return next_open(now, session)


def spread_lots(start, n: int, interval_min: float, session: str = "CORE", resume=None):
    """Times for n lots: start, start+interval, ... Lots that would fall outside the session move to
    the next session open (or to resume(t), e.g. the next 22:00 start time) and keep the same
    spacing from there."""
    out, t = [], _utc(start)
    step = timedelta(minutes=max(0.0, float(interval_min)))
    for _ in range(max(1, int(n))):
        if not is_open(t, session) and resume is not None:
            t = resume(t)
        t = next_open(t, session)
        out.append(t)
        t = t + step
    return out


def describe_session(session: str = "CORE"):
    o, c, _ = SESSIONS.get(session, SESSIONS["CORE"])
    return f"{o.strftime('%H:%M')}–{c.strftime('%H:%M')} New York"
