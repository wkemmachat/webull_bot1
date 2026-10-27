"""FastAPI web app: the JSON API and the single-page app in app/static (no build step)."""
from __future__ import annotations

import csv
import io
import asyncio
import json
import logging
import math
import threading
import time
from datetime import datetime
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import auth, backtest, etf2x, perf, preview, expected, symcharts, brokers, db, engine, execution, golive, health, ledger, marketdata as md, moneyops, notify, scheduler, testtrade, views, idle, portfolio, weekly
from . import strategies as S
from .config import APP_NAME, BASE_DIR, COOKIE_SECURE, DISPLAY_TZ, PUBLIC_URL, SCHEDULER_ENABLED

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")
STATIC = BASE_DIR / "app" / "static"
DOCS = BASE_DIR / "app" / "docs"
TZ = ZoneInfo(DISPLAY_TZ)
VERSION = "1.0.0"


def clean(x):
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if np is not None:
        if isinstance(x, np.bool_):
            return bool(x)
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            x = float(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


class J(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(clean(content), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, default_response_class=J)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.on_event("startup")
def _startup():
    db.init()
    auth.ensure_env_user()
    engine.startup()
    if SCHEDULER_ENABLED:
        scheduler.start()
    else:
        log.warning("SCHEDULER_ENABLED=0: no data refresh, no orders and no LINE from this copy")


@app.on_event("shutdown")
def _shutdown():
    scheduler.stop()


# ---------------------------------------------------------------- auth
def _ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()


def user(request: Request):
    s = auth.session_from_cookie(request.cookies.get(auth.COOKIE))
    if not s:
        raise HTTPException(401, "Please sign in")
    return s


async def body(request: Request) -> dict:
    try:
        b = await request.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


def mode_of(m: Optional[str]) -> str:
    m = (m or "paper").lower()
    if m not in brokers.MODES:
        raise HTTPException(400, "Unknown mode")
    return m


def _err(e: Exception):
    raise HTTPException(400, str(e))


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def index(request: Request):
    if not auth.session_from_cookie(request.cookies.get(auth.COOKIE)):
        return RedirectResponse("/login")
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.api_route("/login", methods=["GET", "HEAD"], include_in_schema=False)
def login_page():
    return FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return J({"name": APP_NAME, "short_name": "Webull Bot", "start_url": "/", "display": "standalone", "background_color": "#0A0F0C",
              "theme_color": "#0A0F0C", "icons": [{"src": "/static/icons/icon-192.png?v=4", "sizes": "192x192", "type": "image/png"},
                        {"src": "/static/icons/icon-512.png?v=4", "sizes": "512x512", "type": "image/png"},
                        {"src": "/static/icons/favicon.svg?v=4", "sizes": "any", "type": "image/svg+xml"}]})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "icons" / "favicon.ico", media_type="image/x-icon", headers={"Cache-Control": "public, max-age=86400"})


def _same_computer(request: Request) -> bool:
    """True when the browser runs on the bot's own computer (http://127.0.0.1). Behind Caddy/Docker the real
    visitor address is used, so a stranger who finds the server before you cannot create the login."""
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


@app.get("/api/auth")
def auth_state(request: Request):
    s = auth.session_from_cookie(request.cookies.get(auth.COOKIE))
    return {"signed_in": bool(s), "username": s["username"] if s else None, "needs_setup": auth.needs_setup(),
            "setup_allowed": _same_computer(request), "app": APP_NAME}


@app.post("/api/setup")
async def setup(request: Request):
    if not auth.needs_setup():
        raise HTTPException(403, "Already set up")
    if not _same_computer(request):
        raise HTTPException(403, "The first login can only be created on the bot's own computer "
                                 "(or with APP_USERNAME / APP_PASSWORD in .env on a server)")
    b = await body(request)
    try:
        auth.create_user(str(b.get("username", "")), str(b.get("password", "")))
    except ValueError as e:
        _err(e)
    return await _do_login(request, b)


@app.post("/api/login")
async def login(request: Request):
    return await _do_login(request, await body(request))


async def _do_login(request: Request, b: dict):
    try:
        val, age = auth.login(str(b.get("username", "")), str(b.get("password", "")), _ip(request),
                              request.headers.get("user-agent", ""), bool(b.get("remember", True)))
    except PermissionError as e:
        raise HTTPException(429, str(e))
    except ValueError as e:
        time.sleep(0.8)
        raise HTTPException(401, str(e))
    r = J({"ok": True})
    r.set_cookie(auth.COOKIE, val, max_age=age, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return r


@app.post("/api/logout")
def logout(request: Request):
    auth.logout(request.cookies.get(auth.COOKIE))
    r = J({"ok": True})
    r.delete_cookie(auth.COOKIE)
    return r


@app.api_route("/api/health", methods=["GET", "HEAD"])
def public_health():
    lt = db.get_state("last_tick") or {}
    return {"ok": True, "version": VERSION, "last_tick": lt.get("at"), "scheduler": SCHEDULER_ENABLED}


# ---------------------------------------------------------------- pages
@app.get("/api/topbar")
def topbar(u=Depends(user)):
    return {**views.topbar(), "username": u["username"], "version": VERSION}


@app.get("/api/dashboard")
def dashboard(mode: str = "paper", u=Depends(user)):
    return views.dashboard(mode_of(mode))


@app.get("/api/strategies")
def strategies(mode: str = "paper", u=Depends(user)):
    return views.strategies_list(mode_of(mode))


@app.get("/api/strategy-types")
def strategy_types(u=Depends(user)):
    return {"types": S.types_public()}


@app.get("/api/strategies/{sid}")
def strategy(sid: str, mode: str = "paper", u=Depends(user)):
    d = views.strategy_detail(mode_of(mode), sid)
    if not d:
        raise HTTPException(404, "No such strategy")
    return d


@app.get("/api/next-orders")
def next_orders(mode: str = "paper", sid: str = "", u=Depends(user)):
    """Orders waiting for the next US open (or running now), per strategy: sells exact, buys estimated."""
    return preview.next_orders(mode_of(mode), sid or None)


@app.get("/api/strategies/{sid}/daily")
def strategy_daily(sid: str, mode: str = "paper", u=Depends(user)):
    """Real profit/loss of one strategy per US trading day (money added or withdrawn left out)."""
    if not S.row(sid):
        raise HTTPException(404, "No such strategy")
    m = mode_of(mode)
    return {**perf.daily(m, sid), "today": perf.today_pnl(m, sid), "mode": m}


@app.get("/api/strategies/{sid}/daily.csv")
def strategy_daily_csv(sid: str, mode: str = "paper", u=Depends(user)):
    if not S.row(sid):
        raise HTTPException(404, "No such strategy")
    m = mode_of(mode)
    name = f"{sid}-{m}-daily-pnl-{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(perf.daily_csv(m, sid), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/strategies/{sid}/risk")
async def strategy_risk(sid: str, mode: str = "paper", u=Depends(user)):
    """Falls to expect: worst falls and time underwater in the backtest, in the real values, and in the research."""
    if not S.row(sid):
        raise HTTPException(404, "No such strategy")
    return await asyncio.to_thread(perf.strategy_risk, sid, mode_of(mode))


@app.get("/api/strategies/{sid}/chart")
def strategy_chart(sid: str, range: str = "1M", u=Depends(user)):
    s = S.get(sid)
    if not s:
        raise HTTPException(404, "No such strategy")
    try:
        return s.chart(md.now_utc(), range)
    except Exception as e:
        return {"charts": [], "error": str(e)}


@app.post("/api/strategies/preview")
async def strategy_preview(request: Request, u=Depends(user)):
    b = await body(request)
    S.load_plugins()
    cls = S.TYPES.get(b.get("type"))
    if not cls:
        raise HTTPException(400, "Unknown type")
    try:
        inst = cls({"id": "_preview", "name": b.get("name") or "Preview", "params": cls.merge_params(b.get("params") or {})})
        for sym, tf in inst.data_needs():
            if not md.last_update(sym, tf):
                (engine.metals.update(sym) if tf == "1h" else md.update(sym, tf))
        ev = inst.evaluate(md.now_utc())
        changes = len([h for h in ev.get("history", []) if h["t"] > time.time() - 365 * 86400]) if ev.get("ok") else None
        return {"ok": ev.get("ok"), "error": ev.get("error"), "label": ev.get("label"), "checks": ev.get("checks"),
                "target": ev.get("target"), "changes_12m": changes, "describe": inst.describe()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/strategies")
async def strategy_create(request: Request, u=Depends(user)):
    b = await body(request)
    try:
        sid = S.create(b.get("type"), str(b.get("name") or ""), b.get("color"), b.get("params") or {}, b.get("exec") or {})
    except ValueError as e:
        _err(e)
    s = S.get(sid)
    db.add_event("info", "strategy", f"Strategy added: {s.name}", json.dumps(s.params), strategy=sid)
    notify.send("system", f"New strategy added: {s.name} ({s.type}). It starts with $0; give it money on the Money page.")
    amt = float(b.get("paper_money") or 0)
    if amt > 0 and "paper" in brokers.enabled_modes():
        try:
            if ledger.pool_cash("paper") < amt:
                moneyops.to_bot("paper", amt - ledger.pool_cash("paper"), "for a new strategy")
            moneyops.add("paper", sid, amt, b.get("invest"), "Start money")
        except ValueError as e:
            db.add_event("warn", "money", "Could not give paper money", str(e), strategy=sid)
    return {"id": sid}


@app.patch("/api/strategies/{sid}")
async def strategy_update(sid: str, request: Request, u=Depends(user)):
    b = await body(request)
    try:
        S.update(sid, name=b.get("name"), color=b.get("color"), params=b.get("params"), exec=b.get("exec"),
                 line_on=(1 if b["line_on"] else 0) if "line_on" in b else None)
    except (ValueError, KeyError) as e:
        _err(e)
    db.add_event("info", "strategy", f"Strategy updated: {sid}", json.dumps({k: v for k, v in b.items()}), strategy=sid)
    if b.get("params") is not None and md.source() != "csv":
        expected.recheck_if_stale()
    return {"ok": True}


@app.post("/api/strategies/{sid}/control")
async def strategy_control(sid: str, request: Request, u=Depends(user)):
    b = await body(request)
    c = b.get("control")
    if c not in ("active", "paused", "stopping"):
        raise HTTPException(400, "control must be active, paused or stopping")
    r = S.row(sid)
    if not r:
        raise HTTPException(404, "No such strategy")
    S.update(sid, control=c)
    words = {"active": "Active: follows every signal", "paused": "Paused: no new buys, exits still run",
             "stopping": "Stop & sell: everything is sold with a split plan"}
    db.add_event("warn" if c != "active" else "info", "strategy", f"{r['name']}: {words[c]}", "", strategy=sid)
    notify.send("system", f"{r['name']}: {words[c]}.", strategy=sid)
    return {"ok": True}


@app.post("/api/strategies/{sid}/archive")
async def strategy_archive(sid: str, request: Request, u=Depends(user)):
    b = await body(request)
    archive = bool(b.get("archive", True))
    if archive:
        for m in brokers.MODES:
            v = ledger.value(m, sid)
            if v["positions"] or v["cash"] > 1:
                raise HTTPException(400, f"{brokers.MODE_LABEL[m]}: stop & sell and withdraw its money first")
    S.update(sid, archived=1 if archive else 0)
    return {"ok": True}


# ---------------------------------------------------------------- money
@app.get("/api/money")
def money(mode: str = "paper", u=Depends(user)):
    return views.money(mode_of(mode))


@app.post("/api/money/{action}")
async def money_action(action: str, request: Request, u=Depends(user)):
    b = await body(request)
    mode = mode_of(b.get("mode"))
    try:
        if action == "add":
            return moneyops.add(mode, b.get("strategy"), b.get("amount"), b.get("invest"), b.get("note", ""))
        if action == "withdraw":
            return moneyops.withdraw(mode, b.get("strategy"), b.get("amount"), b.get("note", ""), everything=bool(b.get("all")))
        if action == "move":
            return moneyops.move(mode, b.get("strategy"), b.get("other"), b.get("amount"), b.get("note", ""), b.get("invest"),
                                 everything=bool(b.get("all")))
        if action == "topup":
            return idle.topup_now(mode, str(b.get("strategy") or ""))
        if action == "protect":
            amt = round(float(b.get("amount") or 0), 2)
            if amt < 0:
                raise ValueError("Enter 0 or more")
            db.set_settings({f"protect_floor_{mode}": str(amt)})
            db.add_event("info", "money", f"Protected cash set to ${amt:,.2f}", brokers.MODE_LABEL[mode], mode=mode)
            return {"ok": True, "floor": amt}
        if action == "to-bot":
            return moneyops.to_bot(mode, b.get("amount"), b.get("note", ""))
        if action == "to-webull":
            return moneyops.to_webull(mode, b.get("amount"), b.get("note", ""))
        if action == "invest-now":
            return moneyops.invest_now(mode, b.get("strategy"))
        if action == "split":
            alloc = b.get("allocations")
            if b.get("equal"):
                total = b.get("total") if b.get("total") not in (None, "") else ledger.pool_cash(mode)
                alloc = moneyops.equal_split(total, list(b.get("strategies") or []))
            return moneyops.split(mode, alloc or {}, b.get("invest"), b.get("note", ""))
    except (ValueError, TypeError) as e:
        _err(e)
    raise HTTPException(404, "Unknown action")


# ---------------------------------------------------------------- orders
@app.get("/api/plans")
def plans(mode: str = "paper", status: Optional[str] = None, limit: int = 30, u=Depends(user)):
    m = mode_of(mode)
    allp = execution.plans_view(m, limit=200)
    counts = {"queued": sum(p["state"] == "queued" for p in allp), "running": sum(p["state"] == "running" for p in allp),
              "done_today": sum(p["status"] in ("done", "cancelled") and (p["finished_at"] or 0) > time.time() - 86400 for p in allp)}
    sel = [p for p in allp if (status in (None, "", "all") or (status == "done" and p["status"] in ("done", "cancelled"))
                               or p["state"] == status)][:limit]
    try:                                                   # estimated buys, the signal behind each plan, money in the strategy
        from . import preview
        nx = preview.next_orders(m)
        est = {r["plan"]: {k: r[k] for k in ("items", "why", "value", "cash", "after")} for r in nx["rows"]}
        nxt = {"next_start": nx["next_start"], "buys": nx["buys"], "sells": nx["sells"], "warnings": nx["warnings"]}
    except Exception as e:
        log.warning("plans estimate: %s", e)
        est, nxt = {}, None
    for p in sel:
        p["est"] = est.get(p["id"])
    return {"plans": sel, "counts": counts, "blocked": execution.blocked_symbols(m), "next": nxt,
            "rule_code": brokers.SINGLE_STOCK_LEV_CODE, "single_stock": sorted(execution.single_stock_etfs())}


@app.post("/api/orders/unblock")
async def orders_unblock(request: Request, u=Depends(user)):
    b = await body(request)
    m = mode_of(b.get("mode"))
    execution.unblock_symbols(m)
    db.add_event("info", "orders", "Refused symbols cleared: the bot will try them again", "", mode=m)
    return {"ok": True}


@app.post("/api/plans/{pid}/{action}")
def plan_action(pid: int, action: str, u=Depends(user)):
    if action == "start-now":
        return {"ok": execution.start_now(pid)}
    if action == "cancel":
        return {"ok": execution.cancel_plan(pid, "cancelled by you")}
    raise HTTPException(404, "Unknown action")


@app.get("/api/weekly")
def weekly_get(mode: str = "live", u=Depends(user)):
    m = mode_of(mode)
    first = db.one("SELECT MIN(submitted_at) t FROM orders WHERE mode=? AND applied_qty>0", (m,))
    fl = weekly.fills(m, int(first["t"])) if first and first["t"] else []
    by = {}
    for f in fl:
        by.setdefault(f["strategy"], []).append(f)
    return {"mode": m, "reports": weekly.stored(m), "costs": weekly.cost_summary(fl),
            "by_strategy": sorted(({"id": k, "name": (S.get(k).name if S.get(k) else k), **weekly.cost_summary(v)} for k, v in by.items()),
                                  key=lambda r: -r["traded"]),
            "fills": fl[-40:][::-1], "since": fl[0]["day"] if fl else None}


@app.post("/api/weekly/send")
async def weekly_send(request: Request, u=Depends(user)):
    b = await body(request)
    r = await asyncio.to_thread(weekly.send, mode_of(b.get("mode")), None, bool(b.get("line", True)))
    return {"ok": True, "text": r["text"]}


@app.get("/api/portfolio")
def portfolio_get(mode: str = "paper", u=Depends(user)):
    return portfolio.view(mode_of(mode))


@app.get("/api/settings/execution")
def exec_settings(u=Depends(user)):
    return views.execution_settings()


@app.post("/api/settings/execution")
async def exec_settings_save(request: Request, u=Depends(user)):
    b = await body(request)
    d = b.get("defaults") or {}
    allowed = {"exec_lots", "exec_interval_min", "exec_start_mode", "exec_start_time", "exec_exit_mode", "exec_session",
               "exec_limit_offset_pct", "exec_retries", "exec_min_lot_usd", "exec_min_trade_usd", "exec_max_order_usd", "new_money_start",
               "exec_fractional_paper", "exec_fractional_test", "exec_fractional_live"}
    upd = {k: str(v) for k, v in d.items() if k in allowed}
    try:
        if "exec_lots" in upd and not (1 <= int(upd["exec_lots"]) <= 60):
            raise ValueError("Lots: 1 to 60")
        if "exec_interval_min" in upd and not (0.5 <= float(upd["exec_interval_min"]) <= 120):
            raise ValueError("Minutes between lots: 0.5 to 120")
        if "exec_start_time" in upd:
            datetime.strptime(upd["exec_start_time"], "%H:%M")
        if "exec_limit_offset_pct" in upd and not (0 <= float(upd["exec_limit_offset_pct"]) <= 2):
            raise ValueError("Limit offset: 0 to 2%")
        if "new_money_start" in upd and upd["new_money_start"] not in ("now", "buy"):
            raise ValueError("New money: 'now' or 'buy'")
        for m in ("paper", "test", "live"):
            if upd.get(f"exec_fractional_{m}") not in (None, "", "1", "0"):
                raise ValueError("Fractional shares: on, off or automatic")
    except ValueError as e:
        _err(e)
    db.set_settings(upd)
    for m in b.get("reset_fractions") or []:
        if m in ("paper", "test", "live"):
            execution.reset_fraction_refusals(m)
    for sid, ov in (b.get("overrides") or {}).items():
        clean_ov = {k: v for k, v in (ov or {}).items() if k in ("lots", "interval_min", "start_mode", "start_time", "exit_mode") and v not in ("", None)}
        S.update(sid, exec=clean_ov)
    db.add_event("info", "settings", "Execution settings saved", json.dumps(b))
    return {"ok": True}


@app.get("/api/fills")
def fills(mode: str = "paper", strategy: Optional[str] = None, side: Optional[str] = None, limit: int = 50, offset: int = 0,
          days: Optional[float] = None, u=Depends(user)):
    m = mode_of(mode)
    since = time.time() - days * 86400 if days else None
    out = execution.fills_view(m, strategy or None, side, limit, offset, since)
    st = db.one("SELECT COUNT(*) n, COALESCE(SUM(filled_qty*avg_price),0) v FROM orders WHERE mode=? AND filled_qty>0", (m,))
    closed = db.rows("SELECT summary FROM plans WHERE mode=? AND status='done'", (m,))
    out["stats"] = {"fills": st["n"], "traded": st["v"], "plans_done": len(closed)}
    return out


@app.get("/api/fills.csv")
def fills_csv(mode: str = "paper", u=Depends(user)):
    rows = execution.fills_view(mode_of(mode), limit=100000)["rows"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time_bangkok", "strategy", "side", "symbol", "qty", "avg_price_usd", "value_usd", "lot", "plan", "reason"])
    for r in rows:
        w.writerow([datetime.fromtimestamp(r["updated_at"], TZ).strftime("%Y-%m-%d %H:%M:%S"), r["name"], r["side"], r["symbol"],
                    r["filled_qty"], r["avg_price"], round(r["value"], 2), f"{r['lot']}/{r['lots']}", r["plan_id"], r["reason"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="fills-{mode}-{datetime.now(TZ):%Y%m%d}.csv"'})


@app.get("/api/positions")
def positions(mode: str = "paper", u=Depends(user)):
    return views.positions(mode_of(mode))


# ---------------------------------------------------------------- health + logs
@app.get("/api/health/report")
def health_report(u=Depends(user)):
    return {"latest": health.latest(), "history": health.history()}


@app.post("/api/health/run")
def health_run(u=Depends(user)):
    return health.run(send=False)


@app.get("/api/orders/{oid}/raw")
def order_raw(oid: int, u=Depends(user)):
    """Webull's own answer for one order (for checking a lot that does not fill)."""
    o = db.one("SELECT * FROM orders WHERE id=?", (oid,))
    if not o or not o["client_order_id"]:
        raise HTTPException(404, "No such order")
    b = brokers.get(o["mode"])
    fn = getattr(b, "order_raw", None)
    try:
        return {"order": o, "webull": fn(o["client_order_id"]) if fn else b.order(o["client_order_id"])}
    except brokers.BrokerError as e:
        return {"order": o, "error": str(e)}


@app.get("/api/health/indicators")
def health_indicators(strategy: str, u=Depends(user)):
    s = S.get(strategy)
    if not s:
        raise HTTPException(404, "No such strategy")
    try:
        return health.indicator_table(s, rows=12)
    except Exception as e:
        return {"rows": [], "cols": [], "error": str(e)}


@app.get("/api/backtest/{sid}")
def backtest_get(sid: str, u=Depends(user)):
    if not S.row(sid):
        raise HTTPException(404, "No such strategy")
    return backtest.run(sid)


@app.get("/api/backtest/{sid}/chart")
async def backtest_symbol_chart(sid: str, sym: str = "", u=Depends(user)):
    """Candles of one symbol the strategy trades, with the backtest's buys/sells and the bot's own fills."""
    try:
        return await asyncio.to_thread(symcharts.build, sid, sym or None)
    except symcharts.ChartError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/backtest/{sid}")
async def backtest_try(sid: str, request: Request, u=Depends(user)):
    """Backtest other settings without saving them."""
    b = await body(request)
    row = S.row(sid)
    if not row:
        raise HTTPException(404, "No such strategy")
    params = b.get("params") or {}
    try:
        S.instance({**row, "params": {**row["params"], **params}})          # validates the values
        return await asyncio.to_thread(backtest.run, sid, params)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/expected")
async def expected_get(mode: str = "paper", u=Depends(user)):
    """Expected return of the money in the strategies (research − haircut), its range and real vs expected."""
    return await asyncio.to_thread(expected.view, mode_of(mode))


@app.post("/api/expected/haircut")
async def expected_haircut(request: Request, u=Depends(user)):
    b = await body(request)
    try:
        expected.set_haircut(b.get("pct"))
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e) or "Enter a number")
    db.add_event("info", "settings", f"Planning haircut for expected returns: {float(b.get('pct')):.0f}%", "")
    return {"ok": True, "haircut_pct": expected.haircut() * 100}


@app.post("/api/expected/plan")
async def expected_plan(request: Request, u=Depends(user)):
    """Save (or clear, with an empty pct) the ratio planned in the Expected return panel. Nothing is traded."""
    b = await body(request)
    try:
        plan = expected.set_plan(b.get("pct"), b.get("total"))
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e) or "Check the ratios")
    db.add_event("info", "settings", "Planned ratio saved" if plan else "Planned ratio cleared",
                 ", ".join(f"{k} {v:g}%" for k, v in (plan or {}).get("pct", {}).items()))
    return {"ok": True, "plan": plan}


@app.post("/api/expected/check")
def expected_check(u=Depends(user)):
    """Re-run every strategy's backtest for the expected-return ranges (takes about a minute)."""
    return expected.start_check("manual", send_line=True)


@app.get("/api/etf2x/{sid}")
def etf2x_get(sid: str, u=Depends(user)):
    """The weekly 2x ETF search for a C2-7 2x strategy: what each large stock is held as, and any ETF found."""
    return etf2x.view(sid)


@app.post("/api/etf2x/{sid}/{action}")
async def etf2x_action(sid: str, action: str, request: Request, u=Depends(user)):
    b = await body(request)
    try:
        if action == "scan":
            return etf2x.start_scan(sid)
        if action == "add":
            return etf2x.add(sid, b.get("stock"), b.get("etf"))
        if action == "dismiss":
            return etf2x.dismiss(sid, b.get("stock"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    raise HTTPException(404, "Unknown action")


@app.get("/api/testtrade")
def testtrade_get(mode: str = "test", u=Depends(user)):
    m = mode_of(mode)
    try:
        testtrade.tick(m)
    except Exception as e:
        log.warning("test trade tick: %s", e)
    return testtrade.view(m)


@app.post("/api/testtrade/{action}")
async def testtrade_action(action: str, request: Request, u=Depends(user)):
    b = await body(request)
    try:
        if action == "start":
            m = mode_of(b.get("mode"))
            testtrade.start(m, b.get("symbols") or [], b.get("qty", 1), fractional=bool(b.get("fractional")),
                            order_type=b.get("order_type") or "LIMIT")
        elif action in ("sell", "closed"):
            t = db.one("SELECT mode FROM test_trades WHERE id=?", (int(b.get("id") or 0),))
            if not t:
                raise HTTPException(404, "Unknown test")
            m = t["mode"]
            (testtrade.sell_again if action == "sell" else testtrade.forget)(int(b["id"]))
        else:
            raise HTTPException(404, "Unknown action")
    except testtrade.TestTradeError as e:
        raise HTTPException(400, str(e))
    return testtrade.view(m)


@app.get("/api/golive")
def golive_get(mode: str = "test", u=Depends(user)):
    return golive.report(mode_of(mode))


@app.post("/api/golive/{action}")
async def golive_action(action: str, request: Request, u=Depends(user)):
    b = await body(request)
    try:
        if action == "tick":
            golive.set_manual(str(b.get("key")), bool(b.get("done")), b.get("note", ""))
        elif action == "restart":
            golive.restart(mode_of(b.get("mode")))
        else:
            raise HTTPException(404, "Unknown action")
    except ValueError as e:
        _err(e)
    return golive.report(mode_of(b.get("mode")))


@app.get("/api/events")
def events(level: Optional[str] = None, source: Optional[str] = None, q: Optional[str] = None, limit: int = 100, before: Optional[int] = None,
           u=Depends(user)):
    sql, args = "SELECT * FROM events WHERE 1=1", []
    if level and level != "all":
        sql += " AND level=?"
        args.append(level)
    if source and source != "all":
        sql += " AND source=?"
        args.append(source)
    if q:
        sql += " AND (title LIKE ? OR message LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if before:
        sql += " AND id<?"
        args.append(before)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(min(500, limit))
    counts = {r["level"]: r["n"] for r in db.rows("SELECT level, COUNT(*) n FROM events WHERE t>? GROUP BY level", (int(time.time()) - 86400,))}
    sources = [r["source"] for r in db.rows("SELECT DISTINCT source FROM events ORDER BY source")]
    return {"events": db.rows(sql, tuple(args)), "counts_24h": counts, "sources": sources}


@app.get("/api/events.log")
def events_log(days: int = 1, u=Depends(user)):
    rows = db.rows("SELECT * FROM events WHERE t>=? ORDER BY id", (int(time.time()) - days * 86400,))
    txt = "\n".join(f"{datetime.fromtimestamp(r['t'], TZ):%Y-%m-%d %H:%M:%S} {r['level'].upper():5} {r['source']:9} "
                    f"{r['title']} | {r['message'] or ''}".rstrip(" |") for r in rows)
    return Response(txt + "\n", media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="bot-log-{datetime.now(TZ):%Y%m%d}.log"'})


# ---------------------------------------------------------------- LINE
@app.get("/api/line")
def line_get(u=Depends(user)):
    return {"settings": notify.settings_public(), "summary": notify.summary(), "recent": notify.recent(),
            "preview": notify.preview(), "strategies": [{"id": r["id"], "name": r["name"], "color": r["color"], "line_on": bool(r["line_on"])}
                                                        for r in S.rows()]}


@app.post("/api/line")
async def line_save(request: Request, u=Depends(user)):
    b = await body(request)
    try:
        notify.save_settings(b)
        for sid, on in (b.get("strategies") or {}).items():
            S.update(sid, line_on=1 if on else 0)
    except (ValueError, KeyError) as e:
        _err(e)
    return {"ok": True}


@app.post("/api/line/test")
def line_test(u=Depends(user)):
    ok, err = notify.test_message()
    if not ok:
        raise HTTPException(400, err or "Not sent")
    db.add_event("info", "line", "Test message sent", "")
    return {"ok": True}


@app.post("/api/line/quota")
def line_quota(u=Depends(user)):
    return notify.quota(force=True)


# ---------------------------------------------------------------- Webull
def _webull_public():
    s = db.get_settings()
    out = {"region": s.get("webull_region"), "modes": brokers.enabled_modes(s)}
    for env in ("test", "live"):
        b = brokers.WebullBroker(s, env=env)
        st = b.status()
        k = b.key
        st["key_hint"] = (k[:4] + "…" + k[-4:]) if len(k) > 8 else ("set" if k else "")
        st["account_id"] = b.account_id
        st["endpoint"] = b.endpoint
        out[env] = st
    pb = brokers.PaperBroker(s)
    out["paper"] = {"connected": True, "start_cash": float(s.get("paper_start_cash") or 0), "cash": pb._acct()["cash"]}
    return out


@app.get("/api/webull")
def webull_get(u=Depends(user)):
    return _webull_public()


@app.post("/api/webull/{env}/{action}")
async def webull_action(env: str, action: str, request: Request, u=Depends(user)):
    if env not in ("test", "live"):
        raise HTTPException(400, "env must be test or live")
    b = await body(request)
    p = "webull_test_" if env == "test" else "webull_"
    if action == "keys":
        upd = {}
        if env == "test" and b.get("shared"):
            try:
                acc = brokers.SHARED_TEST_ACCOUNTS[int(b["shared"]) - 1]
            except (ValueError, IndexError):
                raise HTTPException(400, "Shared test account 1, 2 or 3")
            b = {**b, **acc, "endpoint": brokers.WebullBroker.TEST_HOST}
        if b.get("app_key"):
            upd[p + "app_key"] = str(b["app_key"]).strip()
        if b.get("app_secret"):
            upd[p + "app_secret"] = str(b["app_secret"]).strip()
        if "account_id" in b:
            upd[p + "account_id"] = str(b.get("account_id") or "").strip()
        if env == "test" and "endpoint" in b:
            upd["webull_test_endpoint"] = str(b.get("endpoint") or "").strip()
        db.set_settings(upd)
        return _webull_public()
    if action == "connect":
        def go():
            try:
                brokers.WebullBroker(env=env).connect()
                db.add_event("info", "webull", f"Webull {env} connected", "")
            except Exception as e:
                db.add_event("error", "webull", f"Webull {env} connection failed", str(e))
        threading.Thread(target=go, daemon=True).start()
        time.sleep(1.0)
        return _webull_public()
    if action == "disconnect":
        brokers.WebullBroker(env=env).disconnect()
        db.add_event("warn", "webull", f"Webull {env} disconnected", "")
        return _webull_public()
    if action == "test":
        t0 = time.time()
        try:
            a = brokers.WebullBroker(env=env).account()
        except brokers.BrokerError as e:
            raise HTTPException(400, str(e))
        db.set_state(f"acct_cache:{env}", {**a, "_at": int(time.time())})
        return {"ok": True, "ms": int((time.time() - t0) * 1000), "account": a}
    raise HTTPException(404, "Unknown action")


# ---------------------------------------------------------------- settings
@app.get("/api/settings")
def settings_get(request: Request, u=Depends(user)):
    s = db.get_settings()
    sess = db.rows("SELECT id, created_at, last_seen, ip, ua, expires_at FROM sessions WHERE user_id=? AND revoked=0 AND expires_at>? "
                   "ORDER BY last_seen DESC", (u["user_id"], int(time.time())))
    for x in sess:
        x["device"] = auth.device_name(x.pop("ua") or "")
        x["current"] = x["id"] == u["id"]
        x["id"] = x["id"][:8]
    from .config import BACKUP_DIR
    files = sorted(BACKUP_DIR.glob("bot-*.db")) if BACKUP_DIR.exists() else []
    usr = db.one("SELECT username, pw_changed_at FROM users WHERE id=?", (u["user_id"],))
    return {"user": usr, "sessions": sess,
            "modes": {m: s.get(f"mode_{m}") == "1" for m in brokers.MODES},
            "display": {"show_thb": s.get("show_thb") == "1", "theme": s.get("theme"), "tz": DISPLAY_TZ},
            "data": {"source": md.source(), "metals_source": s.get("metals_source"),
                     "rolls": db.rows("SELECT * FROM rolls ORDER BY t DESC LIMIT 30"), "status": db.get_state("data_status") or {}},
            "server": {"scheduler": SCHEDULER_ENABLED, "version": VERSION, "public_url": PUBLIC_URL,
                       "backups": [{"name": f.name, "size": f.stat().st_size, "t": int(f.stat().st_mtime)} for f in files[-5:]],
                       "started": (db.get_state("heartbeat") or {}).get("since")},
            "paper": {"start_cash": s.get("paper_start_cash"), "strategy_cash": s.get("paper_strategy_cash"),
                      "spread_pct": s.get("paper_spread_pct"), "fee_pct": s.get("paper_fee_pct")},
            "fees": {"backtest_pct": s.get("backtest_cost_pct"), "paper_pct": s.get("paper_fee_pct"),
                     "paper_spread_pct": s.get("paper_spread_pct"), "webull_pct": 0.107},
            "paused": s.get("trading_paused") == "1", "follow_current_signal": s.get("follow_current_signal") == "1"}


@app.post("/api/settings")
async def settings_save(request: Request, u=Depends(user)):
    b = await body(request)
    upd = {}
    for m, on in (b.get("modes") or {}).items():
        if m not in brokers.MODES:
            continue
        if m == "live" and on and db.get_setting("mode_live") != "1" and b.get("confirm") != "LIVE":
            raise HTTPException(400, "Type LIVE to switch on real-money trading")
        upd[f"mode_{m}"] = "1" if on else "0"
    if "show_thb" in b:
        upd["show_thb"] = "1" if b["show_thb"] else "0"
    if "theme" in b and b["theme"] in ("dark", "light", "auto"):
        upd["theme"] = b["theme"]
    if "follow_current_signal" in b:
        upd["follow_current_signal"] = "1" if b["follow_current_signal"] else "0"
    for k, hi in (("paper_spread_pct", 1.0), ("paper_fee_pct", 1.0), ("backtest_cost_pct", 2.0)):
        if k in b:
            try:
                v = float(b[k])
            except (TypeError, ValueError):
                raise HTTPException(400, f"{k}: enter a number")
            if not 0 <= v <= hi:
                raise HTTPException(400, f"{k}: between 0 and {hi}%")
            upd[k] = str(round(v, 4))
    db.set_settings(upd)
    if upd:
        db.add_event("info", "settings", "Settings saved", json.dumps(upd))
    if "backtest_cost_pct" in upd and md.source() != "csv":
        expected.recheck_if_stale()                     # the Expected return panel follows the new fee
    return {"ok": True}


@app.post("/api/settings/password")
async def settings_password(request: Request, u=Depends(user)):
    b = await body(request)
    try:
        auth.change_password(u["user_id"], str(b.get("old", "")), str(b.get("new", "")), keep_session=u["id"])
    except ValueError as e:
        _err(e)
    db.add_event("info", "login", "Password changed", "Other devices were signed out")
    notify.send("login", "Your bot password was changed. Other devices were signed out.", critical=True)
    return {"ok": True}


@app.post("/api/sessions/{short}/revoke")
def session_revoke(short: str, u=Depends(user)):
    r = db.one("SELECT id FROM sessions WHERE user_id=? AND id LIKE ? AND revoked=0", (u["user_id"], short + "%"))
    if not r:
        raise HTTPException(404, "No such session")
    db.run("UPDATE sessions SET revoked=1 WHERE id=?", (r["id"],))
    return {"ok": True}


@app.post("/api/pause")
async def pause(request: Request, u=Depends(user)):
    b = await body(request)
    on = bool(b.get("paused"))
    db.set_settings({"trading_paused": "1" if on else "0"})
    msg = "ALL TRADING PAUSED: no order lots are sent until you resume." if on else "Trading resumed."
    db.add_event("warn" if on else "info", "orders", msg, "")
    notify.send("system", msg, critical=on)
    return {"ok": True, "paused": on}


@app.post("/api/reset-paper")
async def reset_paper(request: Request, u=Depends(user)):
    b = await body(request)
    if b.get("confirm") != "RESET":
        raise HTTPException(400, "Type RESET to confirm")
    cash = float(b.get("start_cash") or db.get_setting("paper_start_cash") or 150000)
    per = float(b.get("strategy_cash") or db.get_setting("paper_strategy_cash") or 10000)
    with execution._LOCK:
        ledger.reset_mode("paper")
        brokers.PaperBroker.reset(cash)
        db.set_settings({"paper_start_cash": str(cash), "paper_strategy_cash": str(per)})
        db.set_state("paper_seeded", None)
        moneyops.seed_paper()
    db.add_event("warn", "settings", "Paper account reset", f"${cash:,.0f} account, ${per:,.0f} per strategy")
    return {"ok": True}


@app.post("/api/stop-all")
async def stop_all(request: Request, u=Depends(user)):
    b = await body(request)
    if b.get("confirm") != "STOP":
        raise HTTPException(400, "Type STOP to confirm")
    for r in S.rows():
        S.update(r["id"], control="stopping")
    db.add_event("warn", "strategy", "All strategies: Stop & sell", "")
    notify.send("system", "All strategies set to Stop & sell.", critical=True)
    return {"ok": True}


@app.get("/api/backup")
def backup_download(u=Depends(user)):
    p = engine.backup()
    return FileResponse(p, filename=p.name, media_type="application/octet-stream")


@app.post("/api/run-now")
def run_now(u=Depends(user)):
    scheduler.run_now()
    return {"ok": True}


@app.post("/api/data/refresh")
def data_refresh(u=Depends(user)):
    threading.Thread(target=lambda: engine.refresh_data(md.now_utc(), force=True), daemon=True).start()
    return {"ok": True}


# ---------------------------------------------------------------- docs
DOC_ORDER = ["overview", "quick-start-mac", "first-day", "modes", "dashboard", "strategies", "backtest", "money", "portfolio", "orders", "line", "health", "golive",
             "strategy-compare", "strategy-timeframes", "strategy-dips", "expected-returns", "strategy-gold1", "strategy-gold2", "strategy-silver1", "strategy-silver2", "strategy-qld", "strategy-semis",
             "strategy-qld-tbd", "strategy-qld-ibs", "strategy-usd-ibs", "strategy-rom-tbd", "strategy-c27",
             "deploy", "update", "backups", "plugins", "layout", "tests", "troubleshooting", "glossary", "decisions"]


@app.get("/api/docs")
def docs_index(u=Depends(user)):
    out = []
    for name in DOC_ORDER:
        p = DOCS / f"{name}.md"
        if p.exists():
            first = p.read_text(encoding="utf-8").splitlines()
            meta = json.loads(first[0][4:-3]) if first and first[0].startswith("<!--") else {}
            out.append({"name": name, "title": meta.get("title", name), "group": meta.get("group", "Help")})
    return {"docs": out}


@app.get("/api/docs/{name}")
def doc(name: str, u=Depends(user)):
    p = DOCS / f"{Path(name).name}.md"
    if not p.exists():
        raise HTTPException(404, "No such page")
    txt = p.read_text(encoding="utf-8")
    meta = {}
    if txt.startswith("<!--"):
        head, txt = txt.split("\n", 1)
        meta = json.loads(head[4:-3])
    if "<!--expected:" in txt:
        txt = expected.fill_doc(txt)
    return {"name": name, "meta": meta, "markdown": txt, "updated": int(p.stat().st_mtime)}
