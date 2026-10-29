"""Go-live checklist: how close the bot is to being ready for real money, measured from its own records.

Three groups (all counted in one mode, normally "Webull test", since the counting start date):
  1. Daily operations   automatic: sessions run, plans finished, lots filled, clean Health checks, errors …
  2. Planned tests      automatic: detected from what happened (a withdrawal that sold, a restart during a plan …)
  3. Your checks        ticked by you (things only you can see, e.g. Webull's own order history)
Readiness = items passed / items counted. Target: 90 % or more, with every "must" item passed.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import brokers, db, markethours as mh, notify, testtrade
from .config import BACKUP_DIR

NY = ZoneInfo("America/New_York")
SESSIONS_NEEDED = 10
CLEAN_DAYS_NEEDED = 8

MANUAL = [
    ("m_fills", "Compared the bot's Trades with Webull's own order history on 3 different days",
     "Webull app → Orders → Filled. Same symbol, side, shares and price as the bot's Trades page.", True),
    ("m_tv", "Checked indicator values against TradingView",
     "Health check → Indicator cross-check: Supertrend/ADX (gold), Donchian (silver), SMA/RSI (QQQ). Same within rounding.", True),
    ("m_line", "LINE alerts arrive on my phone at the right times", "Signals, plan done, the 08:00 / 21:00 digest, the morning Health check.", True),
    ("m_key", "Live API key: Market data + Trading, IP whitelist 165.245.188.124, 2FA on", "webull.co.th → Developer Tool → API Keys Management.", True),
    ("m_margin", "Checked whether my Webull account can borrow (margin). Cash account preferred",
     "A cash account cannot borrow, so even a mistake cannot spend more than the cash.", False),
    ("m_small", "Plan: start Live with 2–3 strategies and small amounts, then add more after 2 good weeks",
     "Fractional shares are on in Live, so small amounts work; still start with a few strategies and add after 2 good weeks.", True),
]


def _manual():
    return db.get_state("golive_manual") or {}


def set_manual(key, done, note=""):
    if key not in {k for k, *_ in MANUAL}:
        raise ValueError("Unknown checklist item")
    m = _manual()
    m[key] = {"done": bool(done), "at": int(time.time()), "note": str(note or "")[:200]}
    db.set_state("golive_manual", m)
    db.add_event("info", "golive", f"Checklist: {'ticked' if done else 'unticked'} {key}", note or "")


def start_of(mode):
    st = db.get_state(f"golive_start:{mode}")
    if st:
        return int(st)
    r = db.one("SELECT MIN(t) t FROM (SELECT MIN(submitted_at) t FROM orders WHERE mode=? AND submitted_at IS NOT NULL "
               "UNION ALL SELECT MIN(t) FROM money WHERE mode=?)", (mode, mode))
    return int(r["t"]) if r and r["t"] else int(time.time())


def restart(mode):
    db.set_state(f"golive_start:{mode}", int(time.time()))
    db.add_event("info", "golive", f"Go-live checklist restarted for {brokers.MODE_LABEL.get(mode, mode)}", "")


def _ny(t):
    return datetime.fromtimestamp(t, NY)


def _item(out, key, title, ok, value, detail="", how="", link="", must=False, warn=False, at=None):
    out.append({"key": key, "title": title, "status": "ok" if ok else ("warn" if warn else "todo"), "value": value,
                "detail": detail, "how": how, "link": link, "must": must, "at": at})


def _explained(mode, e) -> str | None:
    """Errors that already have their answer: Webull's single-stock 2x ETF rule (the bot holds the stocks instead), and a
    failed Test trade of an ETF that passed a later Test trade."""
    from . import execution
    title = e["title"] or ""
    if title.startswith("Webull refuses "):
        sym = title.split()[2] if len(title.split()) > 2 else ""
        if sym in execution.single_stock_etfs() and execution.single_stock_refused(mode):
            return "single-stock 2x ETFs need 50M THB at Webull TH (C2-7 2x holds the stocks)"
    if title.startswith("Test trade ") and title.endswith(" failed"):
        sym = title[len("Test trade "):-len(" failed")].split()[0]
        if sym in execution.single_stock_etfs() and execution.single_stock_refused(mode):
            return "single-stock 2x ETFs need 50M THB at Webull TH (C2-7 2x holds the stocks)"
        ok = db.one("SELECT finished_at t FROM test_trades WHERE mode=? AND symbol=? AND status='ok' AND qty>=1 AND finished_at>=? "
                    "ORDER BY finished_at LIMIT 1", (mode, sym, e["t"]))
        if ok:
            return f"{sym} test trade passed later ({_ny(ok['t']).strftime('%d %b')})"
    return None


def report(mode="test"):
    t0 = start_of(mode)
    now = int(time.time())
    ops, tests, mine = [], [], []

    # ---------------------------------------------------------------- 1. daily operations
    days = set()
    for r in db.rows("SELECT DISTINCT t FROM equity WHERE mode=? AND strategy='*' AND t>=?", (mode, t0)):
        d = _ny(r["t"])
        b = mh.session_bounds(d.date(), "CORE")
        if b and b[0] <= d <= b[1]:
            days.add(d.date())
    _item(ops, "sessions", "US trading sessions run in this mode", len(days) >= SESSIONS_NEEDED, f"{len(days)} / {SESSIONS_NEEDED}",
          "Days the bot was running during US market hours with this mode switched on.",
          "Leave the server running with the mode on; each US trading day counts once.", "#/dashboard", must=True)

    p = db.one("SELECT SUM(status='done') done, SUM(status='cancelled') canc, COUNT(*) n FROM plans WHERE mode=? AND created_at>=?",
               (mode, t0))
    stuck = db.one("SELECT COUNT(*) n FROM plans WHERE mode=? AND status='active' AND created_at < ?", (mode, now - 2 * 86400))["n"]
    done = p["done"] or 0
    _item(ops, "plans", "Order plans finish", done >= 5 and not stuck, f"{done} done · {p['canc'] or 0} cancelled · {stuck} stuck",
          "A plan is finished when all its lots are filled, failed after retries, or skipped.",
          "Wait for signals, or use Add / Withdraw to create plans.", "#/orders", must=True)

    o = db.one("SELECT COUNT(*) n, SUM(filled_qty>0) filled, SUM(retry>0) retried FROM orders WHERE mode=? AND submitted_at>=?", (mode, t0))
    failed = db.one("SELECT COUNT(*) n FROM events WHERE mode=? AND t>=? AND title LIKE 'Lot failed%'", (mode, t0))["n"]
    n = o["n"] or 0
    fill_rate = (o["filled"] or 0) / n if n else 0
    _item(ops, "lots", "Lots fill (with retries if needed)", n >= 20 and failed == 0,
          f"{n} sent · {fill_rate * 100:.0f}% filled · {o['retried'] or 0} retried · {failed} failed",
          "A failed lot means Webull refused or never filled it after all retries.",
          "If lots fail, open Orders: the error says why (price moved, market closed, rejected).", "#/orders", must=True)

    clean, checked = set(), set()
    for r in db.rows("SELECT t, report FROM health_runs WHERE t>=? ORDER BY t", (t0,)):
        rep = json.loads(r["report"] or "{}")
        d = _ny(r["t"]).date()
        checked.add(d)
        bad = [i for i in rep.get("items", []) if i["status"] == "error" and
               (i["id"].endswith("_" + mode) or i["id"] in ("evaluate", "indicators", "heartbeat"))]
        if not bad:
            clean.add(d)
    dirty = sorted(checked - clean)
    _item(ops, "health", "Health check clean (books = account, cash adds up, indicators …)", len(clean) >= CLEAN_DAYS_NEEDED,
          f"{len(clean)} clean day(s) of {len(checked)}", ("Days with a problem: " + ", ".join(d.strftime("%d %b") for d in dirty[-5:]))
          if dirty else "Runs every trading day at 16:45 New York.",
          "Open Health check; with Webull's shared test account other users' trades can cause 'books ≠ account'.",
          "#/health", must=True, warn=bool(dirty) and len(clean) >= CLEAN_DAYS_NEEDED // 2)

    sig = db.one("SELECT COUNT(*) n FROM signals WHERE source='live' AND t>=?", (t0,))["n"]
    _item(ops, "signals", "At least one new signal handled", sig >= 1, f"{sig} live signal(s)",
          "A BUY/SELL or regime change that the bot turned into orders.", "Signals come on their own; gold and silver trade most often.",
          "#/strategies")

    errs, explained = [], []
    for e in db.rows("SELECT t, title FROM events WHERE level='error' AND (mode=? OR mode IS NULL) AND t>=? "
                     "AND title NOT LIKE 'Buy blocked%' ORDER BY t DESC LIMIT 50", (mode, now - 3 * 86400)):
        why = _explained(mode, e)
        (explained if why else errs).append((e, why))
    detail = "; ".join(f"{_ny(e['t']).strftime('%d %b')}: {e['title']}" for e, _ in errs[:3])
    if explained:
        seen = []
        for _, w in explained:
            if w not in seen:
                seen.append(w)
        detail = (detail + " · " if detail else "") + "explained: " + "; ".join(seen[:3])
    _item(ops, "errors", "No errors in the last 3 days", not errs, f"{len(errs)} error(s)" if errs else
          ("none" if not explained else f"none open · {len(explained)} explained"), detail,
          "Open Logs → Errors. Each one needs an explanation before going live.", "#/logs", must=True)

    if mode in ("test", "live"):
        st = brokers.WebullBroker(env=mode).status()
        lap = st.get("lapses_at")
        okc = bool(st.get("connected")) and (not lap or lap - now > 3 * 86400)
        _item(ops, "webull", "Webull connected, token valid", okc,
              ("connected" if st.get("connected") else "not connected") + (f" · token until {_ny(lap).strftime('%d %b')}" if lap else ""),
              "", "Webull page → Connect / Reconnect.", "#/webull", must=True)
    ln = notify.summary()
    _item(ops, "line", "LINE alerts set up and delivered", ln["configured"] and not ln["failed_24h"],
          f"{ln['sent_24h']} sent · {ln['failed_24h']} failed (24 h)" if ln["configured"] else "not set up", "",
          "LINE alerts page → token, recipient, Send test message.", "#/line", must=True)
    files = sorted(BACKUP_DIR.glob("bot-*.db")) if BACKUP_DIR.exists() else []
    _item(ops, "backup", "Nightly backup made", bool(files) and now - files[-1].stat().st_mtime < 36 * 3600,
          files[-1].name if files else "none", "", "Made at 03:30 Bangkok while the bot runs.", "#/settings")

    # ---------------------------------------------------------------- 2. planned tests
    def first(sql, args):
        r = db.one(sql, args)
        return r and (r.get("t") or None)

    def test(key, title, at, how, link, must=True):
        _item(tests, key, title, bool(at), _ny(at).strftime("done %d %b %H:%M") if at else "not yet", "", how, link, must, at=at)

    tt = testtrade.status_for_golive(mode)
    okk = [s for s, v in tt.items() if v == "ok"]
    perm = [s for s, v in tt.items() if v == "permission"]
    bad = [s for s, v in tt.items() if v in ("refused", "failed")]
    todo = [s for s, v in tt.items() if v is None]
    det = " · ".join(x for x in (
        ("OK: " + ", ".join(okk)) if okk else "",
        ("needs Leveraged ETF permission: " + ", ".join(perm)) if perm else "",
        ("refused / not filled: " + ", ".join(bad)) if bad else "",
        ("not tested: " + ", ".join(todo)) if todo else "") if x)
    last = db.one("SELECT MAX(finished_at) t FROM test_trades WHERE mode=? AND status='ok'", (mode,))
    _item(tests, "t_symbols", "Every ETF the strategies use: bought and sold once (Test trade below)",
          bool(tt) and len(okk) == len(tt), f"{len(okk)} / {len(tt)} OK", det,
          "Use the Test trade box on this page: it buys 1 share and sells it back, paid from bot unassigned. Only strategies "
          "with money in this mode count; test a strategy's ETFs before you give it money."
          + (" The shared test accounts refuse leveraged ETFs: those pass only in Live (or your own test account)." if mode == "test" else ""),
          "#/golive", must=(mode == "live"), warn=bool(okk) and not bad and not todo, at=last and last["t"])
    test("t_withdraw", "Withdraw from a strategy that holds ETFs (it sells evenly)",
         first("SELECT MIN(t) t FROM money WHERE mode=? AND kind='withdraw' AND plan_id IS NOT NULL AND status='done' AND t>=?", (mode, t0)),
         "Money → − Withdraw on a strategy with shares, more than its cash. The sale goes back to bot unassigned.", "#/money")
    test("t_move", "Move money between two strategies",
         first("SELECT MIN(t) t FROM money WHERE mode=? AND kind='move' AND status='done' AND t>=?", (mode, t0)),
         "Money → Move between strategies.", "#/money")
    test("t_stop", "Stop & sell a strategy",
         first("SELECT MIN(finished_at) t FROM plans WHERE mode=? AND reason='stop' AND status='done' AND created_at>=?", (mode, t0)),
         "Strategy page → Stop & sell. Afterwards set it back to Active.", "#/strategies")
    paused = first("SELECT MIN(t) t FROM events WHERE source='orders' AND title LIKE 'ALL TRADING PAUSED%' AND t>=?", (t0,))
    resumed = paused and first("SELECT MIN(t) t FROM events WHERE source='orders' AND title='Trading resumed.' AND t>?", (paused,))
    test("t_pause", "Pause all trading during a plan, then resume", resumed,
         "Top right → Pause all trading while lots are going out; check nothing is sent; then Resume.", "#/orders")
    rst = None
    for r in db.rows("SELECT t FROM events WHERE source='server' AND title='Bot started' AND t>=? ORDER BY t", (t0,)):
        hit = db.one("SELECT finished_at t FROM plans WHERE mode=? AND created_at<? AND finished_at>? AND status='done' LIMIT 1",
                     (mode, r["t"], r["t"]))
        if hit:
            rst = r["t"]
            break
    test("t_restart", "Restart the server while a plan is running (no double orders)", rst,
         "Server console: systemctl restart th-strategy-bot while lots are going out. The plan must finish normally.", "#/orders")
    disc = first("SELECT MIN(t) t FROM events WHERE source='webull' AND title=? AND t>=?", (f"Webull {mode} disconnected", t0))
    recon = disc and first("SELECT MIN(t) t FROM events WHERE source='webull' AND title=? AND t>?", (f"Webull {mode} connected", disc))
    if mode in ("test", "live"):
        test("t_reconnect", "Disconnect and reconnect Webull", recon, "Webull page → Disconnect, then Connect (approve in the app).",
             "#/webull", must=False)
    test("t_guard", "Money guard blocks a buy (protected floor test)",
         first("SELECT MIN(t) t FROM events WHERE mode=? AND title LIKE 'Buy blocked%' AND t>=?", (mode, t0)),
         "Money → 🛡 Set the floor above your free cash, wait for the next buy lot, see it blocked + LINE alert; set it back.",
         "#/money")
    test("t_return", "Return money from the bot to Webull",
         first("SELECT MIN(t) t FROM money WHERE mode=? AND kind='to_webull' AND COALESCE(ccy,'USD')='USD' AND t>=?", (mode, t0)),
         "Money → Return to Webull.", "#/money", must=False)

    # ---------------------------------------------------------------- 3. your checks
    man = _manual()
    for key, title, how, must in MANUAL:
        m = man.get(key) or {}
        _item(mine, key, title, bool(m.get("done")), _ny(m["at"]).strftime("ticked %d %b") if m.get("done") else "not yet",
              m.get("note", ""), how, "", must, at=m.get("at") if m.get("done") else None)
    floor = float(db.get_setting("protect_floor_live") or 0)
    _item(mine, "m_floor", "Protected cash floor set for Live", floor > 0, f"${floor:,.0f}" if floor else "not set",
          "Set it after connecting the Live key: Live mode → Money → 🛡 Set.", "", "#/money", must=False)

    allitems = ops + tests + mine
    passed = sum(1 for i in allitems if i["status"] == "ok")
    musts = [i for i in allitems if i["must"]]
    must_ok = sum(1 for i in musts if i["status"] == "ok")
    pct = passed / len(allitems) if allitems else 0
    ready = pct >= 0.9 and must_ok == len(musts)
    return {"mode": mode, "since": t0, "pct": pct, "passed": passed, "total": len(allitems), "must_ok": must_ok,
            "must_total": len(musts), "ready": ready,
            "sections": [{"id": "ops", "title": "Daily operations", "sub": "measured automatically", "items": ops},
                         {"id": "tests", "title": "Planned tests", "sub": "detected automatically when you do them", "items": tests},
                         {"id": "mine", "title": "Your checks", "sub": "tick when done", "items": mine}]}
