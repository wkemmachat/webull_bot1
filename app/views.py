"""Data for each page of the web app (the API in main.py returns these as JSON)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import brokers, db, dip, execution, health, ledger, marketdata as md, markethours as mh, metals, notify, perf, testtrade, idle, moneyops
from . import strategies as S
from .config import APP_NAME, DISPLAY_TZ, SCHEDULER_ENABLED

TZ = ZoneInfo(DISPLAY_TZ)
NY = ZoneInfo("America/New_York")


def account(mode, max_age=60):
    key = f"acct_cache:{mode}"
    c = db.get_state(key)
    if c and time.time() - c.get("_at", 0) < max_age:
        return c, None
    try:
        a = brokers.get(mode).account()
        a["_at"] = int(time.time())
        db.set_state(key, a)
        return a, None
    except Exception as e:
        return (c if c else None), str(e)


def market_status(now=None):
    now = now or md.now_utc()
    open_ = mh.is_open(now, "CORE")
    if open_:
        cl = mh.current_close(now, "CORE")
        return {"open": True, "text": f"US market open · closes {cl.astimezone(TZ).strftime('%H:%M')}", "next": int(cl.timestamp())}
    nx = mh.next_open(now, "CORE")
    pre = mh.is_open(now, "ALL")
    when = nx.astimezone(TZ)
    day = "" if when.date() == now.astimezone(TZ).date() else when.strftime("%a ")
    return {"open": False, "text": f"US market {'pre/after hours' if pre else 'closed'} · opens {day}{when.strftime('%H:%M')}",
            "next": int(nx.timestamp())}


def topbar():
    s = db.get_settings()
    now = md.now_utc()
    modes = brokers.enabled_modes(s)
    conn = {}
    for m in ("test", "live"):
        st = db.get_state(brokers.conn_key(m)) or {}
        conn[m] = {"status": st.get("status") or "not connected", "enabled": m in modes}
    lt = db.get_state("last_tick") or {}
    return {"app": APP_NAME, "modes": modes, "conn": conn, "market": market_status(now), "paused": s.get("trading_paused") == "1",
            "scheduler": {"enabled": SCHEDULER_ENABLED, "last": lt.get("at"), "ok": bool(lt.get("at")) and time.time() - lt["at"] < 180},
            "bkk": now.astimezone(TZ).strftime("%H:%M"), "ny": now.astimezone(NY).strftime("%H:%M"),
            "issues": _issue_counts(), "data_source": md.source()}


def _issue_counts():
    rep = health.latest()
    plans = db.one("SELECT COUNT(*) n FROM plans WHERE status='active'")["n"]
    by_mode = {r["mode"]: r["n"] for r in db.rows("SELECT mode, COUNT(*) n FROM plans WHERE status='active' GROUP BY mode")}
    return {"health": (rep["counts"]["warn"] + rep["counts"]["error"]) if rep else 0, "plans": plans, "plans_by_mode": by_mode}


def _state(sid):
    r = db.one("SELECT * FROM strategy_state WHERE strategy=?", (sid,))
    if not r:
        return {}
    r["target"] = json.loads(r["target"] or "{}")
    r["detail"] = json.loads(r["detail"] or "{}")
    return r


def _state_class(s, st):
    if not st.get("ok"):
        return "err"
    if s.family == "regime":
        return {"2x": "info", "1x": "info", "0.5x": "warn", "off": "", "trend": "ok", "dip": "warn", "out": ""}.get(st.get("state"), "")
    return "ok" if st.get("state") == "long" else ""


def _spark(mode, sid, days=30):
    pts = execution.equity_series(mode, sid, days, 40)
    return [round(p["value"], 2) for p in pts]


def strategy_card(mode, s, prices=None):
    st = _state(s.id)
    v = ledger.value(mode, s.id, prices)
    ap = execution.active_plan(mode, s.id)
    d = s.describe()
    nc = (st.get("detail") or {}).get("next_check")
    state_label = st.get("label") if st.get("ok") else f"error: {st.get('error') or 'not evaluated yet'}"
    label, activity = state_label, None
    if ap:
        q = execution.plans_view(mode, sid=s.id, limit=1)
        p = q[0] if q else None
        if p and p["state"] == "queued":
            at = datetime.fromtimestamp(p["start_at"], TZ).strftime("%H:%M")
            activity = {"kind": "queued", "text": f"Plan starts {at}"}
            label = f"{label} · plan queued {at}"
        elif p:
            activity = {"kind": "running", "text": "Plan running"}
            label = f"{label} · plan running"
    waiting = execution.waiting_for_buy(mode, s) if (v.get("hold_cash") and not ap) else None
    if waiting:
        activity = {"kind": "waiting", "text": f"${v['waiting_cash']:,.0f} waits for a buy signal"}
        label = f"{label} · ${v['waiting_cash']:,.0f} waits for a buy signal"
    cfg = execution.exec_cfg(s)
    return {"id": s.id, "name": s.name, "color": s.color, "type": s.type, "family": s.family, "timeframe": s.timeframe,
            "control": s.row.get("control"), "line_on": bool(s.row.get("line_on")), "flow": d.get("flow"), "rule": d.get("rule"),
            "dip": dip.get(s.id),
            # stopped and empty in this mode: the pages hide it unless "Show stopped" is on
            "idle": s.row.get("control") == "stopped" and not ap and abs(v["value"] or 0) < 0.5 and not v["positions"],
            "state": st.get("state"), "label": label, "state_label": state_label, "activity": activity,
            "state_cls": _state_class(s, st),
            "waiting_since": waiting, "ok": bool(st.get("ok")),
            "signal_time": st.get("signal_time"), "bar_time": st.get("bar_time"), "next_check": nc,
            "value": v["value"], "net_in": v["net_in"], "pnl": v["pnl"], "ret": v["ret"], "cash": v["cash"],
            "positions": v["positions"], "target": st.get("target") or {}, "plan": bool(ap), "exec": execution.describe_cfg(cfg),
            "spark": _spark(mode, s.id), "today": perf.today_pnl(mode, s.id, v["value"], v["net_in"] or 0),
            "dd": perf.card_summary(s.id),
            "notice": ("Webull Thailand refuses leveraged ETFs on single stocks for your account (50M THB rule), so in this mode "
                       "the strategy holds the stocks themselves: it works like C2-7 Momentum 1x, not 2x."
                       if s.params.get("leverage") == "2x" and mode != "paper" and execution.single_stock_refused(mode) else None)}


def dashboard(mode):
    acct, err = account(mode)
    strats = S.all_instances()
    syms = set()
    for s in strats:
        syms |= set(ledger.get(mode, s.id)["holdings"])
    prices = md.prices(syms)
    cards = [strategy_card(mode, s, prices) for s in strats]
    bot_v = sum(c["value"] for c in cards)
    bot_in = sum(c["net_in"] for c in cards)
    series = execution.equity_series(mode, "*", 90)
    day_ago = execution.equity_series(mode, "*", 1.2)
    # today's gain leaves out money added or withdrawn today
    today = ((bot_v - day_ago[0]["value"]) - (bot_in - (day_ago[0]["capital"] or 0))) if day_ago else None
    base_today = (day_ago[0]["value"] + (bot_in - (day_ago[0]["capital"] or 0))) if day_ago else None
    un = ledger.pool_cash(mode)
    not_bot = (acct["total"] - bot_v - un) if acct and acct.get("total") is not None else None
    plans = execution.plans_view(mode, status=None, limit=50)
    active = [p for p in plans if p["status"] == "active"]
    rep = health.latest()
    events = db.rows("SELECT * FROM events WHERE level IN ('info','warn','error') AND source NOT IN ('login') ORDER BY id DESC LIMIT 7")
    bench = series[-1]["bench"] if series else None
    return {"mode": mode, "account": acct, "account_error": err, "strategies": cards,
            "bot": {"value": bot_v, "net_in": bot_in, "pnl": bot_v - bot_in, "ret": (bot_v / bot_in - 1) if bot_in else None,
                    "today": today, "today_pct": (today / base_today) if today is not None and base_today else None,
                    "bench_ret": (bench / series[-1]["capital"] - 1) if bench and series and series[-1]["capital"] else None},
            "unassigned": un, "not_bot": not_bot, "series": series, "plans": active[:4], "health": rep and {"t": rep["t"], "counts": rep["counts"],
                                                                                       "first": next((i for i in rep["items"] if i["status"] != "ok"), None)},
            "line": notify.summary(), "next": next_up(mode, strats, active), "events": events, "logins": _logins()}


def _logins():
    from . import tokenwatch
    try:
        return tokenwatch.logins()
    except Exception:
        return []


def next_up(mode, strats, active):
    now = md.now_utc()
    items = []
    for p in active:
        if p["state"] == "queued" and p["start_at"]:
            items.append({"t": p["start_at"], "title": f"{p['name']} · plan starts",
                          "sub": f"{p['lots']} lot(s) every {p['interval_min']:g} min · {_plan_text(p)}"})
    ne = metals.next_bar_end(now)
    if ne and any(s.family == "signal" for s in strats):
        items.append({"t": ne + metals.delay_min() * 60, "title": "4H bar close · metals check",
                      "sub": ", ".join(s.name.split(" · ")[0] for s in strats if s.family == "signal")})
    regs = [s for s in strats if s.family == "regime"]
    if regs:
        t = regs[0].next_check(now)
        if t:
            items.append({"t": t, "title": "Daily decision (after the US close)", "sub": ", ".join(s.name for s in regs)
                          + " · trades from the next open, only on a change"})
    ht = db.get_setting("health_time_ny") or "16:45"
    d = now.astimezone(NY).date()
    h, m = (int(x) for x in ht.split(":"))
    for k in range(0, 4):
        cand = datetime.combine(d + timedelta(days=k), datetime.min.time().replace(hour=h, minute=m), NY)
        if cand > now:
            items.append({"t": int(cand.timestamp()), "title": "Daily cross-check", "sub": "Books vs Webull, orders, data, LINE, backup"})
            break
    nd = notify.next_digest()
    if nd:
        local = now.astimezone(TZ)
        hh, mm = (int(x) for x in nd.split(":"))
        t = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if t <= local:
            t += timedelta(days=1)
        items.append({"t": int(t.timestamp()), "title": "LINE digest", "sub": "Everything set to 'Digest' since the last one"})
    items.sort(key=lambda x: x["t"])
    return items[:6]


def _plan_text(p):
    sells = {}
    buys = set()
    for o in p["orders"]:
        if o["side"] == "SELL":
            sells[o["symbol"]] = sells.get(o["symbol"], 0) + (o["plan_qty"] or 0)
        else:
            buys.add(o["symbol"])
    parts = [f"sell {q:.0f} {s}" for s, q in sells.items()] + [f"buy {s}" for s in sorted(buys)]
    return ", ".join(parts)


def strategies_list(mode):
    strats = S.all_instances()
    syms = set()
    for s in strats:
        syms |= set(ledger.get(mode, s.id)["holdings"])
    prices = md.prices(syms)
    archived = [r for r in S.rows(include_archived=True) if r["archived"]]
    return {"strategies": [strategy_card(mode, s, prices) for s in strats],
            "archived": [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in archived]}


def strategy_detail(mode, sid):
    s = S.get(sid)
    if not s:
        return None
    card = strategy_card(mode, s)
    st = _state(sid)
    sig = db.rows("SELECT * FROM signals WHERE strategy=? ORDER BY t DESC LIMIT 25", (sid,))
    cfg = execution.exec_cfg(s)
    tgt = st.get("target") or {}
    v = ledger.value(mode, sid)
    hold = []
    for sym in sorted(set(v["positions"]) | set(tgt)):
        p = v["positions"].get(sym) or {"qty": 0, "value": 0, "price": None}
        hold.append({"symbol": sym, "qty": p["qty"], "value": p["value"], "price": p["price"],
                     "now": p["value"] / v["value"] if v["value"] else 0, "target": tgt.get(sym, 0)})
    hold.append({"symbol": "Cash", "qty": None, "value": v["cash"], "now": v["cash"] / v["value"] if v["value"] else 0,
                 "target": max(0.0, 1 - sum(tgt.values()))})
    return {"mode": mode, "card": card, "row": {**s.row, "params": s.params}, "describe": s.describe(), "state": st,
            "signals": sig, "holdings": hold, "exec": cfg, "exec_text": execution.describe_cfg(cfg),
            "type": next((t for t in S.types_public() if t["type"] == s.type), None),
            "idle": idle.view(mode, s, st), "dip": dip.get(sid),
            "plans": execution.plans_view(mode, sid=sid, limit=5), "money": [m for m in ledger.moves(mode, 200) if m["strategy"] == sid or m["other"] == sid][:10]}


def money(mode):
    acct, err = account(mode)
    strats = S.all_instances(include_archived=True)
    rows = []
    syms = set()
    for s in strats:
        syms |= set(ledger.get(mode, s.id)["holdings"])
    prices = md.prices(syms)
    for s in strats:
        v = ledger.value(mode, s.id, prices)
        if s.row.get("archived") and not v["value"] and not v["cap_in"]:
            continue
        rows.append({"id": s.id, "name": s.name, "color": s.color, "cap_in": v["cap_in"], "cap_out": v["cap_out"], "net_in": v["net_in"],
                     "value": v["value"], "pnl": v["pnl"], "ret": v["ret"], "cash": v["cash"], "control": s.row.get("control")})
    tot = sum(r["value"] for r in rows)
    for r in rows:
        r["share"] = r["value"] / tot if tot else 0
    un = ledger.pool_cash(mode)
    names = {s.id: s.name for s in strats}
    mv = ledger.moves(mode, 60)
    for m in mv:
        m["name"], m["other_name"] = names.get(m["strategy"], m["strategy"]), names.get(m["other"])
    for r in rows:
        L = ledger.get(mode, r["id"])
        r["waiting"] = ledger.waiting_cash(L) if (L["hold_cash"] and execution.waiting_for_buy(mode, S.get(r["id"]), L)) else 0
    cash = (acct or {}).get("cash")
    total = (acct or {}).get("total")
    outside = ledger.outside_cash(mode, cash)
    not_bot = (total - tot - un) if total is not None else None
    floor = float(db.get_setting(f"protect_floor_{mode}") or 0)
    gb = db.get_state(f"guard_block:{mode}") or {}
    fund = {"protect_floor": floor, "guard_block": gb if gb and time.time() - gb.get("at", 0) < 86400 else None,
            "account_total": total, "account_cash": cash, "allocated": tot + un, "strategies": tot, "pool": un,
            "outside_cash": outside, "not_bot": not_bot, "own_shares": (not_bot - outside) if (not_bot is not None and outside is not None) else None}
    mv = [m for m in mv if (m.get("ccy") or "USD") == "USD"]            # HKD moves are listed in the HKD block
    return {"mode": mode, "account": acct, "account_error": err, "rows": rows, "total": tot, "unassigned": un, "fund": fund, "moves": mv,
            "new_money_start": db.get_setting("new_money_start") or "now", "hkd": moneyops.hkd_view(mode, acct)}


def positions(mode):
    acct, err = account(mode, max_age=20)
    books = {}
    for r in db.rows("SELECT h.strategy, h.symbol, h.qty, s.name, s.color FROM holdings h LEFT JOIN strategies s ON s.id=h.strategy "
                     "WHERE h.mode=? AND h.qty>1e-9 ORDER BY h.symbol", (mode,)):
        b = books.setdefault(r["symbol"], {"symbol": r["symbol"], "bot": 0.0, "owners": []})
        b["bot"] += r["qty"]
        b["owners"].append({"id": r["strategy"], "name": r["name"] or r["strategy"], "color": r["color"], "qty": r["qty"]})
    pos = (acct or {}).get("positions") or {}
    rows = []
    for sym, b in books.items():
        p = pos.get(sym) or {}
        have = p.get("qty", 0.0)
        px = p.get("last") or md.prices([sym]).get(sym)
        rows.append({**b, "account": have, "price": px, "value": b["bot"] * (px or 0), "diff": have - b["bot"] if acct else None,
                     "status": "match" if acct and abs(have - b["bot"]) < 1e-6 else ("extra" if acct and have > b["bot"] else
                                                                                     ("missing" if acct else "unknown"))})
    mine = [{"symbol": k, "qty": v.get("qty"), "value": v.get("value"), "price": v.get("last")} for k, v in pos.items() if k not in books]
    strat_cash = ledger.strategies_cash(mode)
    cash = (acct or {}).get("cash")
    return {"mode": mode, "account_error": err, "rows": rows, "not_bot": mine, "account": acct,
            "cash": {"account": cash, "strategies": strat_cash, "unassigned": ledger.pool_cash(mode),
                     "outside": ledger.outside_cash(mode, cash)},
            "checked_at": (acct or {}).get("_at")}


def execution_settings():
    s = db.get_settings()
    strats = S.all_instances()
    return {"defaults": {k: s.get(k) for k in ("exec_lots", "exec_interval_min", "exec_start_mode", "exec_start_time", "exec_exit_mode",
                                               "exec_session", "exec_limit_offset_pct", "exec_retries", "exec_min_lot_usd",
                                               "exec_min_trade_usd", "exec_max_order_usd", "new_money_start", "exec_cross")},
            "strategies": [{"id": x.id, "name": x.name, "color": x.color, "family": x.family, "override": x.row.get("exec") or {},
                            "type_defaults": x.EXEC_DEFAULTS, "effective": execution.exec_cfg(x), "text": execution.describe_cfg(execution.exec_cfg(x))}
                           for x in strats],
            "fractional": fractional_view(s), "calendar": calendar(), "timeline": timeline()}


def fractional_view(s=None):
    s = s if s is not None else db.get_settings()
    out = {}
    for m in ("live", "test", "paper"):
        st = execution.fractional_setting(m, s)
        lim = testtrade.fraction_status(m).get("LIMIT") if m != "paper" else None
        out[m] = {"on": st["on"], "source": st["source"], "value": s.get(f"exec_fractional_{m}") or "",
                  "test": ({"ok": bool(lim.get("ok")), "at": lim.get("at"), "symbol": lim.get("symbol")} if lim else None),
                  "refused": execution.fraction_refused(m)}
    return out


def calendar():
    out = []
    today = datetime.now(NY).date()
    for d in sorted(mh.HOLIDAYS | mh.EARLY_CLOSE):
        if today <= d <= today + timedelta(days=120):
            out.append({"date": d.strftime("%a %d %b %Y"), "kind": "early close" if d in mh.EARLY_CLOSE else "closed"})
    return out


def timeline():
    """Tonight in Bangkok time: US session band, queued plans, 4H closes, regime decision."""
    now = md.now_utc()
    start = now.astimezone(TZ).replace(hour=18, minute=0, second=0, microsecond=0)
    if now.astimezone(TZ).hour < 6:
        start -= timedelta(days=1)
    end = start + timedelta(hours=12)
    out = {"start": int(start.timestamp()), "end": int(end.timestamp()), "session": None, "items": [], "marks": []}
    d = start.astimezone(NY).date()
    for k in (0, 1):
        b = mh.session_bounds(d + timedelta(days=k), "CORE")
        if b and b[1] > start and b[0] < end:
            out["session"] = [int(b[0].timestamp()), int(b[1].timestamp())]
            break
    for mode in brokers.enabled_modes():
        for p in execution.plans_view(mode, limit=20):
            if p["status"] != "active" or not p["window"]:
                continue
            out["items"].append({"from": p["window"][0], "to": p["window"][1] + int((p["interval_min"] or 10) * 60),
                                 "label": f"{p['name'].split(' · ')[0]} · {p['lots']} lots", "color": p["color"], "mode": mode})
    t = start
    for _ in range(6):
        ne = metals.next_bar_end(t)
        if not ne or ne > end.timestamp():
            break
        out["marks"].append({"t": ne, "label": "4H " + datetime.fromtimestamp(ne, TZ).strftime("%H:%M")})
        t = datetime.fromtimestamp(ne + 60, timezone.utc)
    return out
