"""The bot's loop (every 30 seconds): refresh prices → evaluate every strategy → record new signals and
alert them → let each trading mode follow the targets → send due order lots → LINE → daily jobs."""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import brokers, db, execution, ledger, marketdata as md, markethours as mh, metals, notify
from . import strategies as S
from .config import BACKUP_DIR, DB_PATH, DISPLAY_TZ

log = logging.getLogger("engine")
NY = ZoneInfo("America/New_York")
TZ = ZoneInfo(DISPLAY_TZ)
_lock = threading.Lock()
STALE_S = {"signal": 3 * 3600, "regime": 4 * 86400}


# ---------------------------------------------------------------- data
def _needs():
    out = set()
    for s in S.all_instances():
        for x in s.data_needs():
            out.add(x)
    return sorted(out)


RETRY_MAX_S = 30 * 60          # after failures: retry after 1, 2, 4 … minutes, at most every 30 minutes
ALERT_AFTER_S = 30 * 60        # only tell LINE when a feed has been failing this long while it matters


def _matters(sym, tf, now):
    """Is fresh data needed right now? 1h futures: COMEX open. Daily ETFs: a US trading day."""
    if tf == "1h":
        return metals.last_close(now) is None
    return mh.is_trading_day(now.astimezone(NY).date())


def refresh_data(now, force=False):
    status = db.get_state("data_status") or {}
    errors, alerts, fixed = [], [], []
    for sym, tf in _needs():
        key = f"{sym}:{tf}"
        last = md.last_update(sym, tf) or 0
        prev = status.get(key) or {}
        fails = int(prev.get("fails") or 0) if not prev.get("ok", True) else 0
        if fails and not force and time.time() - (prev.get("at") or 0) < min(RETRY_MAX_S, 60 * 2 ** (fails - 1)):
            continue                                  # back off: Yahoo is having a bad moment
        try:
            if tf == "1h":
                if force or metals.due(sym, now):
                    n = metals.update(sym)
                    status[key] = {"ok": True, "at": int(time.time()), "bars": n}
            else:
                if force or _daily_due(sym, now, last):
                    n = md.update(sym, "1d")
                    status[key] = {"ok": True, "at": int(time.time()), "bars": n}
        except Exception as e:
            log.warning("data %s: %s", key, e)
            since = prev.get("since") if fails else int(time.time())
            status[key] = {"ok": False, "at": int(time.time()), "error": str(e)[:300], "fails": fails + 1, "since": since,
                           "alerted": prev.get("alerted") if fails else None, "last_ok": prev.get("last_ok") or last}
            errors.append(f"{key}: {e}")
            if time.time() - since >= ALERT_AFTER_S and _matters(sym, tf, now) and not status[key]["alerted"]:
                status[key]["alerted"] = int(time.time())
                alerts.append(f"{key}: failing for {int((time.time() - since) // 60)} min ({e})")
        else:
            if prev.get("alerted"):
                fixed.append(key)
            if key in status and status[key].get("ok"):
                status[key]["last_ok"] = int(time.time())
    db.set_state("data_status", status)
    if errors:
        db.add_event("warn", "data", "Price data problem (retrying)", "\n".join(errors[:10]))
    if alerts:
        notify.send("data", "Price data problem — the bot keeps retrying and does not trade on old prices:\n" + "\n".join(alerts[:6]))
        db.set_state("data_alert_at", int(time.time()))
    if fixed:
        notify.send("data", "Price data OK again: " + ", ".join(fixed))
        db.add_event("info", "data", "Price data OK again", ", ".join(fixed))
    return errors


def _daily_due(sym, now, last):
    if md.source() == "csv":
        return time.time() - last > 60
    ny = now.astimezone(NY)
    after_close = datetime.combine(ny.date(), datetime.strptime("16:07", "%H:%M").time(), NY)
    if ny >= after_close and last < after_close.timestamp() and mh.is_trading_day(ny.date()):
        return True                                   # the closing bar
    return time.time() - last > 30 * 60               # charts during the day


# ---------------------------------------------------------------- evaluation + signals
def _signal_text(s, h):
    if hasattr(s, "signal_message"):
        return s.signal_message(h)
    if h["kind"] == "STATE":
        tgt = s.target_for(h["to"]) if hasattr(s, "target_for") else {}
        pos = " + ".join(f"{w * 100:.0f}% {k}" for k, w in sorted(tgt.items(), key=lambda x: -x[1]))
        return f"REGIME · {s.name}: {h['from']} → {h['to']}\n{h['text']}\nNew target: {pos}"
    word = "BUY" if h["kind"] == "BUY" else "SELL"
    tgt = s.params.get("etf") if word == "BUY" else (s.params.get("cash_etf") or "cash")
    return f"{word} · {s.name}\n{h['text']}\nMoves to {tgt}"


def evaluate_all(now):
    out = {}
    for s in S.all_instances():
        prev = db.one("SELECT * FROM strategy_state WHERE strategy=?", (s.id,))
        try:
            ev = s.evaluate(now)
        except Exception as e:
            ev = {"ok": False, "error": str(e)[:300]}
        ev["computed_at"] = int(time.time())
        if ev.get("ok"):
            first = prev is None or not prev.get("bar_time")
            last_bar = (prev or {}).get("bar_time") or 0
            for h in ev.get("history", []):
                live = (not first) and h["t"] > last_bar
                cur = db.run("INSERT OR IGNORE INTO signals(strategy,t,kind,from_state,to_state,price,text,source,created_at) "
                             "VALUES(?,?,?,?,?,?,?,?,?)", (s.id, h["t"], h["kind"], h["from"], h["to"], h["price"], h["text"],
                                                           "live" if live else "history", int(time.time())))
                if live and cur.rowcount:
                    late = time.time() - h["t"] > 8 * 3600
                    txt = ("LATE · " if late else "") + _signal_text(s, h)
                    notify.send("regime" if h["kind"] == "STATE" else "signal", txt, strategy=s.id)
                    db.add_event("info", "signal", f"{s.name}: {h['kind'].lower()} {h['from']} → {h['to']}", h["text"], strategy=s.id)
            db.run("INSERT INTO strategy_state(strategy,computed_at,bar_time,state,label,target,signal_time,ok,error,detail) "
                   "VALUES(?,?,?,?,?,?,?,1,NULL,?) ON CONFLICT(strategy) DO UPDATE SET computed_at=excluded.computed_at, "
                   "bar_time=excluded.bar_time, state=excluded.state, label=excluded.label, target=excluded.target, "
                   "signal_time=excluded.signal_time, ok=1, error=NULL, detail=excluded.detail",
                   (s.id, ev["computed_at"], ev["bar_time"], ev["state"], ev["label"], json.dumps(ev["target"]), ev.get("signal_time"),
                    json.dumps({"checks": ev.get("checks"), "price": ev.get("price"), "next_check": ev.get("next_check"),
                                **(ev.get("detail") or {})})))
        else:
            db.run("INSERT INTO strategy_state(strategy,computed_at,ok,error) VALUES(?,?,0,?) ON CONFLICT(strategy) DO UPDATE SET "
                   "computed_at=excluded.computed_at, ok=0, error=excluded.error", (s.id, ev["computed_at"], ev.get("error")))
        out[s.id] = (s, ev)
    return out


def fresh(s, ev, now) -> bool:
    """Only trade on a signal whose bar is recent enough (a data outage must not trade on old signals)."""
    if not ev.get("ok"):
        return False
    age = now.timestamp() - (ev.get("bar_time") or 0)
    return age <= STALE_S.get(s.family, 3 * 3600) or md.source() == "csv"


# ---------------------------------------------------------------- daily jobs
def _once(key: str, day: str) -> bool:
    done = db.get_state(f"job:{key}")
    if done == day:
        return False
    db.set_state(f"job:{key}", day)
    return True


def daily_jobs(now):
    ny = now.astimezone(NY)
    day = ny.strftime("%Y-%m-%d")
    hh = ny.strftime("%H:%M")
    if mh.is_trading_day(ny.date()) and hh >= "16:40" and _once("report", day):
        queue_reports(now)
    if mh.is_trading_day(ny.date()) and hh >= "17:30" and _once("preview", day):
        from . import preview                               # LINE: orders waiting for the next open
        try:
            preview.send_preview(now)
        except Exception as e:
            log.warning("next-open preview: %s", e)
    htime = db.get_setting("health_time_ny") or "16:45"
    if hh >= htime and _once("health", day):
        from . import health
        try:
            health.run(now)
        except Exception as e:
            log.exception("health")
            db.add_event("error", "health", "Health check crashed", str(e))
    # dip zones: each strategy's underwater percentile, after the close (and once on start when none is stored yet)
    if md.source() != "csv":
        from . import dip
        if (mh.is_trading_day(ny.date()) and hh >= "16:50" and _once("dip", day)) or (dip.missing() and _once("dip_first", day)):
            try:
                dip.refresh_all(now)
            except Exception as e:
                log.warning("dip zones: %s", e)
    local = now.astimezone(TZ)
    # Webull login reminders (5, 3, 1 days before the token ends, and when it has ended): checked every 30 minutes
    if _once("tokenwatch", local.strftime("%Y-%m-%d %H:") + str(local.minute // 30)):
        from . import tokenwatch
        try:
            tokenwatch.check()
        except Exception as e:
            log.warning("token reminders: %s", e)
    if local.strftime("%H:%M") >= "03:30" and _once("backup", local.strftime("%Y-%m-%d")):
        try:
            backup()
        except Exception as e:
            db.add_event("error", "server", "Backup failed", str(e))
    # weekly Live report: Saturday from 09:00 Bangkok, after Friday's US close (real prices only)
    if md.source() != "csv" and local.weekday() == 5 and local.strftime("%H:%M") >= "09:00" and _once("weekly", local.strftime("%G-%V")):
        from . import weekly
        weekly.job(now)
    if _once("prune", local.strftime("%Y-%W")):
        db.prune()
    # expected returns: first / yearly backtest check and the review reminder (real prices only)
    if md.source() != "csv" and _once("expected", local.strftime("%Y-%m-%d")):
        from . import expected
        try:
            expected.daily(now)
        except Exception as e:
            log.warning("expected returns: %s", e)
    # the stored backtest check follows the fee and the strategies' settings (checked every 10 minutes)
    if md.source() != "csv" and _once("expected_fp", local.strftime("%Y-%m-%d %H:") + str(local.minute // 10)):
        from . import expected
        try:
            expected.recheck_if_stale()
        except Exception as e:
            log.warning("expected returns re-check: %s", e)
    # weekly Nasdaq-100 ranking for the momentum baskets, after the Friday close
    if (ny.weekday() == 5 or (ny.weekday() == 4 and hh >= "17:30") or ny.weekday() == 6) and \
            any(s.type == "momentum_basket" for s in S.all_instances()):
        fri = (ny.date() - timedelta(days=(ny.weekday() - 4) % 7)).isoformat()
        if time.time() >= (db.get_state("c27rank_retry_at") or 0) and _once("c27rank", fri):
            threading.Thread(target=_rank_job, daemon=True).start()


def _rank_job():
    from . import basket
    try:
        basket.update_live()
        from . import etf2x
        etf2x.scan_all()                                     # suggest 2x ETFs for this week's largest stocks (never adds)
    except Exception as e:
        log.warning("nasdaq-100 ranking: %s", e)
        db.set_state("job:c27rank", None)                    # try again in an hour
        db.set_state("c27rank_retry_at", int(time.time()) + 3600)
        db.add_event("warn", "data", "Nasdaq-100 ranking failed (retrying in 1 h)", str(e)[:300])


def queue_reports(now):
    for mode in brokers.enabled_modes():
        for s in S.all_instances():
            v = ledger.value(mode, s.id)
            if (v["net_in"] or 0) <= 0 and not v["positions"]:
                continue
            st = db.one("SELECT label FROM strategy_state WHERE strategy=?", (s.id,)) or {}
            since = int((now - timedelta(hours=24)).timestamp())
            fills = db.rows("SELECT side, symbol, SUM(filled_qty) q, SUM(filled_qty*avg_price) v FROM orders WHERE mode=? AND strategy=? "
                            "AND filled_qty>0 AND updated_at>=? GROUP BY side, symbol", (mode, s.id, since))
            hold = ", ".join(f"{brokers.qty_text(round(p['qty'], 4))} {k}" for k, p in v["positions"].items()) or "cash only"
            ret = f"{v['ret'] * 100:+.1f}%" if v["ret"] is not None else "—"
            lines = [f"{s.name} · {brokers.MODE_LABEL[mode]}", f"${v['value']:,.0f} ({ret} on ${v['net_in']:,.0f}) · {st.get('label', '—')}",
                     f"Holds {hold}"]
            try:
                from . import perf
                tp = perf.today_pnl(mode, s.id, v["value"], v["net_in"] or 0)
                if tp:
                    lines.insert(2, f"Today {'+' if tp['pnl'] >= 0 else '−'}${abs(tp['pnl']):,.0f}"
                                    + (f" ({tp['pct'] * 100:+.2f}%)" if tp["pct"] is not None else ""))
            except Exception as e:
                log.warning("today pnl %s: %s", s.id, e)
            if fills:
                lines.append("Trades: " + "; ".join(f"{f['side'].lower()} {brokers.qty_text(round(f['q'], 4))} {f['symbol']}" for f in fills))
            notify.send("report", "\n".join(lines), strategy=s.id)


def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = BACKUP_DIR / f"bot-{datetime.now(TZ).strftime('%Y-%m-%d')}.db"
    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(str(name))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    keep = int(db.get_setting("backup_keep_days") or 30)
    files = sorted(BACKUP_DIR.glob("bot-*.db"))
    for f in files[:-keep]:
        f.unlink(missing_ok=True)
    db.add_event("info", "server", "Database backup", f"{name.name} · {name.stat().st_size / 1e6:.1f} MB")
    _ = shutil
    return name


# ---------------------------------------------------------------- the tick
def heartbeat():
    now = int(time.time())
    hb = db.get_state("heartbeat") or {}
    last = hb.get("last")
    gaps = [g for g in hb.get("gaps", []) if now - g[0] < 3 * 86400]
    if last and now - last > 600:
        gaps.append([last, now])
    db.set_state("heartbeat", {"last": now, "since": hb.get("since") or now, "gaps": gaps[-50:], "ticks": (hb.get("ticks") or 0) + 1})


def tick(now=None):
    if not _lock.acquire(blocking=False):
        return {"busy": True}
    started = time.time()
    try:
        now = now or md.now_utc()
        heartbeat()
        errors = refresh_data(now)
        evs = evaluate_all(now)
        settings = db.get_settings()
        for mode in brokers.enabled_modes(settings):
            try:
                broker = brokers.get(mode, settings)
            except Exception as e:
                log.warning("broker %s: %s", mode, e)
                continue
            for sid, (s, ev) in evs.items():
                if not fresh(s, ev, now):
                    continue
                try:
                    execution.reconcile(mode, s, ev, now, broker, settings)
                except Exception as e:
                    log.exception("reconcile %s %s", mode, sid)
                    db.add_event("error", "orders", f"{s.name}: could not plan orders", str(e), strategy=sid, mode=mode)
        execution.process(now, settings)
        try:
            execution.finish_stops()
        except Exception:
            log.exception("finish stops")
        try:
            notify.dispatch()
        except Exception as e:
            log.exception("line dispatch")
            db.add_event("error", "line", "LINE dispatcher error", str(e))
        daily_jobs(now)
        db.set_state("last_tick", {"at": int(time.time()), "took": round(time.time() - started, 2), "errors": errors})
        return {"ok": True, "errors": errors}
    finally:
        _lock.release()


def startup():
    """Called once when the app starts."""
    S.load_plugins()
    new = S.seed()
    from . import moneyops
    moneyops.seed_paper()
    for sid in new:
        moneyops.seed_new_paper(sid)
        db.add_event("info", "strategy", f"New default strategy added: {sid}", "Created by the update", strategy=sid)
    _single_stock_rule_from_tests()
    db.add_event("info", "server", "Bot started", f"data source: {md.source()}")
    notify.send("system", "Bot started.")


def _single_stock_rule_from_tests():
    """A Test trade refused with Webull's single-stock leveraged-ETF rule (before this version treated it as one ETF only):
    apply the account rule now, so no strategy keeps trying those ETFs."""
    try:
        like = f"%{brokers.SINGLE_STOCK_LEV_CODE}%"
        rows = db.rows("SELECT mode, symbol, error, result FROM test_trades WHERE code=? OR error LIKE ? OR result LIKE ? ORDER BY id",
                       (brokers.SINGLE_STOCK_LEV_CODE, like, like))
    except Exception:
        return
    for r in rows:
        if not execution.single_stock_refused(r["mode"]):
            execution.block_symbol(r["mode"], r["symbol"], brokers.SINGLE_STOCK_LEV_CODE,
                                   r["result"] or r["error"] or brokers.SINGLE_STOCK_LEV_CODE)
