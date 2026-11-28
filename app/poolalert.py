"""Pool alerts (28 Nov 2026): when the strategy pool is on, four things are watched for you.

1. Good time to add extra money: the pool backtest of today's members falls deeper than the chosen share of its past
   days (default the 80th percentile). Once per fall; armed again only after the fall is shallower than the 70th.
   Research (Help → Design decisions, 28 Nov 2026): from the first day of such falls since 2005 the pool was higher a
   year later almost every time, but waiting for the zone with regular savings lost to adding them at once in 84% of
   5-year periods — so it is for money kept aside.
2. Monthly add reminder: on the chosen day (the next weekday when it falls on a weekend or US holiday) until "Done this
   month". Timing inside the month gained nothing (+0.3% since 2005, −1.5% over 10 years).
3. Real vs backtest: the real pool (time-weighted, so money added does not count) trails the backtest of the same
   members over the same days by more than the chosen points.
4. A member past its backtest's worst fall: from the strategy's own deep-fall check (app/dip.py, LINE "Deep fall").

LINE goes out for one mode only (Live when it is on), so two pools do not send the same news twice; the Dashboard shows
each mode's own cards. The per-strategy "good time to add money" LINE alert is not sent for pool members (dip.py)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db, markethours as mh, notify, perf, pool
from . import strategies as S
from .config import DISPLAY_TZ

log = logging.getLogger("poolalert")
TZ = ZoneInfo(DISPLAY_TZ)
NY = ZoneInfo("America/New_York")
DEFAULTS = {"zone_pct": 80, "month_day": 1, "gap_pts": 5.0}
ZONES = pool.ZONE_TH
GAP_MIN_DAYS = 5                # trading days of the pool's own record before the gap is judged
MONTH_HOUR = 8                  # the monthly reminder goes out from 08:00 Bangkok on its day
LATE_DAYS = 3                   # the bot was off on the day: LINE still goes up to 3 days later (the card stays until Done)
EVENT_OF = {"zone": "pool_add", "month": "pool_month", "gap": "pool_gap", "worst": "drawdown"}
MODE_LABEL = {"live": "Live", "test": "Webull test", "paper": "Paper"}


def settings(mode: str) -> dict:
    return {**DEFAULTS, **(pool.cfg(mode).get("alerts") or {})}


def set_settings(mode: str, d: dict) -> dict:
    a = settings(mode)
    if d.get("zone_pct") is not None:
        z = int(d["zone_pct"])
        if z not in ZONES:
            raise ValueError(f"Add-money percentile: one of {', '.join(map(str, ZONES))}")
        a["zone_pct"] = z
    if d.get("month_day") is not None:
        m = int(d["month_day"])
        if not 1 <= m <= 28:
            raise ValueError("Monthly reminder day: 1 to 28")
        a["month_day"] = m
    if d.get("gap_pts") is not None:
        g = float(d["gap_pts"])
        if not 1 <= g <= 50:
            raise ValueError("Real vs backtest: 1 to 50 points")
        a["gap_pts"] = round(g, 1)
    c = pool.cfg(mode)
    c["alerts"] = a
    pool._save(mode, c)
    if "line" in d:                                     # {"zone": true, "month": false, ...} → the LINE page's switches
        ev = {EVENT_OF[k]: ("instant" if v else "off") for k, v in (d["line"] or {}).items() if k in EVENT_OF}
        if ev:
            notify.save_settings({"events": ev})
    return public(mode)


def public(mode: str) -> dict:
    m = notify.event_modes()
    return {**settings(mode), "zones": list(ZONES), "rearm": pool.ZONE_REARM,
            "line": {k: m.get(e, "instant") != "off" for k, e in EVENT_OF.items()}}


def line_mode() -> str | None:
    """The one mode whose pool alerts go to LINE: Live when Live is on and its pool is on, else the first pool that is on."""
    for mode in notify.money_modes() + ["live", "test", "paper"]:
        if pool.on(mode):
            return mode
    return None


def _bt(mode, c=None):
    c = c or pool.cfg(mode)
    if not c["members"]:
        return {}
    return pool.backtest(list(c["members"]), pool.slot_pct(c), float(c["cap_pct"]), float(c["min_pct"]))


def ordinal(n) -> str:
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _budget_dropped(qid) -> bool:
    """The LINE message was not sent because the month's LINE budget was used up, and there is room again (a new month)."""
    if not qid:
        return False
    r = db.one("SELECT status, error FROM line_queue WHERE id=?", (qid,))
    if not r or r["status"] != "skipped" or not (r["error"] or "").startswith("Monthly LINE budget"):
        return False
    return notify.budget()["state"] in ("ok", "tight", "low")


# ---------------------------------------------------------------- 1. good time to add extra money
def zone_text(mode, z, th, n_members) -> str:
    r = (z.get("rows") or {}).get(str(th)) or {}
    t = (f"▲ Good time to add extra money to the pool ({MODE_LABEL.get(mode, mode)})\n"
         f"Today's {n_members} members: {z['depth']:.1f}% below their high · deeper than {int(z['pct'])}% of past days.")
    if r.get("n"):
        t += (f"\nSince {str(z.get('from') or '')[:4]}, from the first day of such falls: higher a year later {r['up']} of {r['n']} "
              f"times, typically {r['med']:+.0f}%, worst 1 in 10 {r['p10']:+.1f}%.")
    return t + "\nFor money you keep aside; regular money goes in when you have it. Once per fall."


def zone_check(mode, bt, send=True) -> dict | None:
    z = (bt or {}).get("zone") or {}
    if z.get("pct") is None:
        return None
    th = settings(mode)["zone_pct"]
    st = db.get_state(f"poolzone:{mode}") or {}
    if st.get("day") == z["day"] and st.get("th") == th:
        return st
    if "armed" not in st:                               # first look (or after a reset): a fall already in the zone counts from its first day
        last = (z.get("last") or {}).get(str(th)) or {}
        st = {"armed": not last.get("open"), "since": last.get("day") if last.get("open") else None, "sent": False}
    if st.get("armed", True) and z["pct"] >= th:
        st.update(armed=False, since=z["day"], sent=False)
    elif z["pct"] < pool.ZONE_REARM:
        st.update(armed=True, since=None, sent=False)
    n = len(pool.cfg(mode)["members"])
    if not st.get("armed") and z["pct"] >= th and not st.get("sent"):
        db.add_event("info", "pool", f"Good time to add extra money to the pool ({ordinal(z['pct'])} percentile, {z['depth']:.1f}%)",
                     zone_text(mode, z, th, n))
        if send and line_mode() == mode:
            st["qid"] = notify.send("pool_add", zone_text(mode, z, th, n))
        st["sent"] = True                               # once per fall, whatever the mode
    elif not st.get("armed") and z["pct"] >= th and send and line_mode() == mode and _budget_dropped(st.get("qid")):
        st["qid"] = notify.send("pool_add", zone_text(mode, z, th, n))      # still in the zone: once more, now there is room
    st.update(day=z["day"], th=th, pct=z["pct"], depth=z["depth"])
    db.set_state(f"poolzone:{mode}", st)
    return st


# ---------------------------------------------------------------- 2. monthly add reminder
def reminder_day(y: int, m: int, day: int) -> date:
    d = date(y, m, min(day, 28))
    for _ in range(10):
        if d.weekday() < 5 and mh.is_trading_day(d):
            return d
        d += timedelta(days=1)
    return d


def month_check(mode, now=None, bt=None, send=True) -> dict:
    local = (now or datetime.now(TZ)).astimezone(TZ)
    key = local.strftime("%Y-%m")
    st = db.get_state(f"poolmonth:{mode}") or {}
    due = reminder_day(local.year, local.month, settings(mode)["month_day"])
    if st.get("month") != key:
        first = not st                                  # never run before (just installed): no reminder for a day long past
        st = {"month": key, "sent": False, "done": first and (local.date() - due).days > LATE_DAYS}
    st["due"] = str(due)
    st["show"] = local.date() >= due and not st["done"]
    if st["show"] and not st["sent"] and local.hour >= MONTH_HOUR and (local.date() - due).days <= LATE_DAYS:
        z = ((bt or {}).get("zone") or {})
        where = (f" Pool: {abs(z['depth']):.1f}% below its high ({ordinal(z['pct'])} percentile)." if z.get("pct") is not None else "")
        txt = f"📅 Monthly add · {local.strftime('%B')} ({MODE_LABEL.get(mode, mode)})\nToday is your day to add this month's savings to the pool.{where}"
        if send and line_mode() == mode:
            notify.send("pool_month", txt)
        db.add_event("info", "pool", f"Monthly add reminder · {local.strftime('%B')}", txt)
        st["sent"] = True
    db.set_state(f"poolmonth:{mode}", st)
    return st


def month_done(mode, now=None) -> dict:
    local = (now or datetime.now(TZ)).astimezone(TZ)
    st = db.get_state(f"poolmonth:{mode}") or {}
    st.update(month=local.strftime("%Y-%m"), done=True, show=False, sent=True, done_at=int(time.time()))
    db.set_state(f"poolmonth:{mode}", st)
    return st


# ---------------------------------------------------------------- 3. real vs backtest
def gap(mode, bt, c=None) -> dict | None:
    """The real pool's return since it started (time-weighted, from the closes) against the backtest of the same members
    over the same days. None until both have GAP_MIN_DAYS days."""
    c = c or pool.cfg(mode)
    t0 = pool.since(mode, c)
    tail = (bt or {}).get("daily_tail") or []
    if not t0 or not tail:
        return None
    pday = datetime.fromtimestamp(t0, timezone.utc).astimezone(NY).date()
    days, idx = perf.real_index(mode, "*")
    if len(idx) < 2:
        return None
    pairs = [(d, x) for d, x in zip(days[1:], idx[1:])]
    base = next((x for d, x in reversed(pairs) if d < pday), 1.0)
    after = [(d, x) for d, x in pairs if d >= pday]
    if len(after) < GAP_MIN_DAYS:
        return None
    end_day, end_x = after[-1]
    bt_days = [(date.fromisoformat(d), v) for d, v in tail]
    b0 = next((v for d, v in reversed(bt_days) if d < pday), None)
    b1 = next((v for d, v in reversed(bt_days) if d <= end_day), None)
    if b0 is None or b1 is None:
        return None
    real, model = end_x / base - 1, b1 / b0 - 1
    return {"real": round(real * 100, 2), "model": round(model * 100, 2), "gap": round((real - model) * 100, 2),
            "from": str(pday), "to": str(end_day), "days": len(after)}


def gap_check(mode, bt, send=True) -> dict | None:
    g = gap(mode, bt)
    if not g:
        return None
    lim = settings(mode)["gap_pts"]
    st = db.get_state(f"poolgap:{mode}") or {"armed": True}
    if st.get("to") == g["to"] and st.get("lim") == lim:
        return st
    if st.get("armed", True) and g["gap"] < -lim:
        txt = (f"⚠ Real pool {abs(g['gap']):.1f} points behind its backtest ({MODE_LABEL.get(mode, mode)})\n"
               f"Since {datetime.fromisoformat(g['from']).strftime('%d %b')}: real {g['real']:+.1f}%, backtest {g['model']:+.1f}%. "
               "Dashboard → see the gap.")
        db.add_event("warn", "pool", f"Real pool {abs(g['gap']):.1f} points behind its backtest", txt)
        if send and line_mode() == mode:
            st["qid"] = notify.send("pool_gap", txt)
        st["armed"] = False
    elif g["gap"] > -lim / 2:
        st["armed"] = True                              # back within half the limit: armed again
    st.update(g, lim=lim, show=g["gap"] < -lim)
    db.set_state(f"poolgap:{mode}", st)
    return st


# ---------------------------------------------------------------- 4. a member past its backtest's worst fall
def worst_members(mode, c=None) -> list:
    from . import dip
    c = c or pool.cfg(mode)
    out = []
    for sid in c["members"]:
        d = db.get_state(f"dip:{sid}") or {}
        lv = dip.warn_level(d.get("of_worst"), d.get("worst10_years"))
        if lv and lv >= 100:
            s = S.get(sid)
            out.append({"id": sid, "name": s.name if s else sid, "depth": d.get("depth"), "worst": d.get("worst10"),
                        "years": d.get("worst10_years"), "day": d.get("day")})
    return out


# ---------------------------------------------------------------- run (engine, every few minutes) and the Dashboard's view
def run(now=None) -> dict:
    out = {}
    for mode in ("live", "test", "paper"):
        if not pool.on(mode):
            continue
        try:
            c = pool.cfg(mode)
            bt = _bt(mode, c)
            if not bt.get("ready") or bt.get("error"):
                month_check(mode, now, None)
                continue
            out[mode] = {"zone": zone_check(mode, bt), "month": month_check(mode, now, bt), "gap": gap_check(mode, bt)}
        except Exception as e:                          # never stops the tick
            log.warning("pool alerts %s: %s", mode, e)
    return out


def view(mode: str, bt: dict | None = None, now=None) -> dict:
    """The Dashboard's cards: what is showing now (nothing is sent from here)."""
    a = settings(mode)
    z = (bt or {}).get("zone") or {}
    zs = db.get_state(f"poolzone:{mode}") or {}
    zone = None
    if z.get("pct") is not None and z["pct"] >= a["zone_pct"]:
        r = (z.get("rows") or {}).get(str(a["zone_pct"])) or {}
        zone = {"pct": z["pct"], "depth": z["depth"], "since": zs.get("since") or ((z.get("last") or {}).get(str(a["zone_pct"])) or {}).get("day"),
                "th": a["zone_pct"], "row": r, "from": z.get("from")}
    ms = db.get_state(f"poolmonth:{mode}") or {}
    local = (now or datetime.now(TZ)).astimezone(TZ)
    due = reminder_day(local.year, local.month, a["month_day"])
    month = None
    if local.date() >= due and not (ms.get("month") == local.strftime("%Y-%m") and ms.get("done")) \
            and (ms or (local.date() - due).days <= LATE_DAYS):
        month = {"name": local.strftime("%B"), "day": a["month_day"], "due": str(due),
                 "depth": z.get("depth"), "pct": z.get("pct")}
    gs = db.get_state(f"poolgap:{mode}") or {}
    gp = {k: gs.get(k) for k in ("real", "model", "gap", "from", "to", "days", "lim")} if gs.get("show") else None
    return {"settings": public(mode), "zone": zone, "month": month, "gap": gp, "worst": worst_members(mode)}
