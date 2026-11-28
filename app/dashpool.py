"""Dashboard when the strategy pool is on (Dashboard v2, 28 Nov 2026).

Built around the questions you ask when you open it:
  1. Does anything need me?            → attention: problems only (the routine checks shrink to one green line)
  2. How much, and how is it doing?    → the pool's value, its real (time-weighted) return, profit, money put in
  3. Is it working as expected?        → this month, the fall from the top and money at work, each against the normal
                                         range of the pool's own backtest of today's members
  4. What happens next?                → tonight's decisions and the orders planned for the next open
Everything else (members, where the money is, who made the profit, month by month) sits below.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from . import db, execution, ledger, notify, perf, pool
from . import strategies as S

log = logging.getLogger("dashpool")
NY = ZoneInfo("America/New_York")
TOO_EARLY_DAYS = 20               # trading days of the pool's own record before it is compared with the backtest


def _month_rows(days, idx, pool_day):
    """Real return per calendar month from the time-weighted index (the last month runs to today)."""
    out, prev_end, cur, start_v = [], 1.0, None, 1.0
    for d, x in zip(days[1:], idx[1:]):
        k = (d.year, d.month)
        if cur is None:
            cur, start_v = k, prev_end
        if k != cur:
            out.append({"y": cur[0], "m": cur[1], "ret": prev_end / start_v - 1})
            cur, start_v = k, prev_end
        prev_end = x
    if cur is not None:
        out.append({"y": cur[0], "m": cur[1], "ret": prev_end / start_v - 1, "partial": True})
    for r in out:
        r["before_pool"] = pool_day is not None and (r["y"], r["m"]) < (pool_day.year, pool_day.month)
        r["mixed"] = pool_day is not None and (r["y"], r["m"]) == (pool_day.year, pool_day.month) and pool_day.day > 1
    return out


def _attention(mode, d, pv, check):
    """Problems that need you (each with what to do), and the routine checks that are fine (one line)."""
    items, ok = [], []
    for x in d.get("logins") or []:
        if x["status"] != "ok":
            ended = x["status"] == "ended"
            items.append({"level": "err" if ended or x["days_left"] <= 1 else "warn",
                          "title": f"Webull {x['label']} login {'has ended' if ended else 'ends in ' + str(max(1, round(x['days_left']))) + ' day(s)'}",
                          "text": "No orders can be sent after it ends. Renew it while the US market is closed.",
                          "action": {"label": "Renew now", "href": "#/webull"}})
        elif x.get("mode") == mode:
            ok.append(f"Webull login · {int(x['days_left'])} days left")
    if d.get("account_error"):
        items.append({"level": "err", "title": "Webull account not readable", "text": str(d["account_error"])[:160],
                      "action": {"label": "Webull page", "href": "#/webull"}})
    if d.get("bp_wait"):
        items.append({"level": "warn", "title": "Buys are waiting for Webull's buying power",
                      "text": "Webull lets the bot use less than the cash right now; the buys go ahead once it is back.",
                      "action": {"label": "Money", "href": "#/money"}})
    h = d.get("health") or None
    if h:
        c = h["counts"]
        if c.get("error") or c.get("warn"):
            first = h.get("first") or {}
            items.append({"level": "err" if c.get("error") else "warn",
                          "title": f"Cross-check: {first.get('title') or 'a problem'}", "text": (first.get("detail") or "")[:180],
                          "action": {"label": "Health check", "href": "#/health"}})
        else:
            ok.append(f"Cross-check · {c.get('ok', 0)} ok")
    for m in pv.get("waiting") or []:
        w = m.get("wait") or {}
        if w.get("since") and time.time() - w["since"] > 86400:
            items.append({"level": "warn", "title": f"{m['name'].split(' · ')[0]} has waited over a day for money",
                          "text": f"Only ${pv['free']:,.0f} is free (smallest trade ${pv['min_usd']:,.0f}). Add money, or lower the trade size.",
                          "action": {"label": "Pool settings", "href": "#/money"}})
    ln = d.get("line") or {}
    if ln.get("failed_24h"):
        items.append({"level": "warn", "title": f"{ln['failed_24h']} LINE message(s) failed in the last 24 h", "text": "Check the LINE page.",
                      "action": {"label": "LINE", "href": "#/line"}})
    elif ln.get("configured"):
        bg = ln.get("budget") or {}
        ok.append(f"LINE · {ln.get('sent_24h', 0)} sent in 24 h" + (f" · {bg['used']}/{bg['cap']} this month" if bg.get("cap") else ""))
    bg = ln.get("budget") or {}
    if ln.get("configured") and bg.get("state") in ("low", "stop", "full"):
        items.append({"level": "err" if bg["state"] == "full" else "warn",
                      "title": f"LINE: {bg['used']} of {bg['cap']} messages used this month",
                      "text": bg.get("text", "") + ". Everything still shows on the site.",
                      "action": {"label": "LINE", "href": "#/line"}})
    b = d.get("backup")
    if b:
        items.append({"level": "warn", "title": "No backup downloaded for " + (f"{b['days']} days" if b.get("last") else "a while"),
                      "text": "Keep a copy off the server.", "action": {"label": "Download backup", "href": "/api/backup"}})
    bt = check.get("bt") or {}
    worst = ((bt.get("all") or {}).get("maxdd"))
    if check.get("fall") is not None and worst is not None and check["fall"] * 100 < worst:
        items.append({"level": "warn", "title": "The fall from the top is past the backtest's worst",
                      "text": f"{check['fall'] * 100:.1f}% now; the worst fall in this mix's backtest was {worst:.1f}%. Nothing is broken by itself; worth a look.",
                      "action": {"label": "Backtest", "href": "#/backtest"}})
    hb = db.get_state("heartbeat") or {}
    if hb.get("last"):
        ok.insert(0, "Bot running · " + datetime.fromtimestamp(hb["last"], timezone.utc).astimezone(ZoneInfo("Asia/Bangkok")).strftime("%H:%M"))
    return {"items": items, "ok": ok}


def build(mode: str, d: dict) -> dict:
    """The extra Dashboard data when the pool is on. d is views.dashboard()'s result (value, account, health, …)."""
    c = pool.cfg(mode)
    pv = pool.view(mode)
    b = d["bot"]
    t0 = pool.since(mode, c)
    pool_day = datetime.fromtimestamp(t0, timezone.utc).astimezone(NY).date() if t0 else None
    out = {"pool": pv, "since": t0}
    try:
        days, idx = perf.real_index(mode, "*", b["value"], b["net_in"])
    except Exception as e:
        log.warning("real index: %s", e)
        days, idx = [], []
    check = {"fall": None, "month": None, "since_ret": None, "since_days": 0}
    if len(idx) >= 2:
        hi = max(idx)
        check["fall"] = idx[-1] / hi - 1 if hi > 0 else None
        months = _month_rows(days, idx, pool_day)
        out["months"] = months
        if months:
            check["month"] = months[-1]["ret"]
        if pool_day:
            base = next((x for dd, x in zip(reversed(days[1:]), reversed(idx[1:])) if dd < pool_day), 1.0)
            check["since_ret"] = idx[-1] / base - 1
            check["since_days"] = len({dd for dd in days[1:] if dd >= pool_day})
        out["curve"] = [[str(dd), round((x - 1) * 100, 2)] for dd, x in zip(days[1:], idx[1:])]
    check["too_early"] = check["since_days"] < TOO_EARLY_DAYS
    check["work"] = (pv["in_trades"] / pv["total"]) if pv["total"] > 0 else None
    bt = pool.backtest(list(c["members"]), pool.slot_pct(c), float(c["cap_pct"]), float(c["min_pct"])) if c["members"] else {}
    check["bt"] = {k: bt.get(k) for k in ("ready", "done", "of", "error", "ranges", "all", "periods", "fixed", "idle", "slot_pct")}
    out["check"] = check
    out["btchart"] = {k: bt.get(k) for k in ("ready", "weekly", "zone", "all", "periods")} if bt.get("ready") and not bt.get("error") else None
    try:
        from . import poolalert
        out["alerts"] = poolalert.view(mode, bt if bt.get("ready") else None)
    except Exception as e:
        log.warning("pool alerts view: %s", e)
        out["alerts"] = None
    out["attention"] = _attention(mode, d, pv, check)
    plans = []
    for p in d.get("plans") or []:
        st = db.get_state(f"pooltrade:{mode}:{p['strategy']}") or {}
        buys = sorted({o["symbol"] for o in p["orders"] if o["side"] == "BUY"})
        sells = sorted({o["symbol"] for o in p["orders"] if o["side"] == "SELL"})
        plans.append({"name": p["name"], "color": p.get("color"), "state": p["state"], "start_at": p["start_at"], "lots": p["lots"],
                      "interval": p["interval_min"], "buys": buys, "sells": sells,
                      "amount": st.get("amount") if buys and st.get("t", 0) >= (p["created_at"] or 0) - 600 else None})
    out["plans"] = plans
    return out
