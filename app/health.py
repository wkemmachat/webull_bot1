"""Nightly error cross-check (and the "Run check now" button). It only READS: it never places, changes or
cancels an order. Each line is ok / warn / error with what to do."""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from zoneinfo import ZoneInfo

from . import brokers, db, ledger, marketdata as md, markethours as mh, metals, notify
from . import strategies as S
from .bars import market_open_ny
from .config import BACKUP_DIR

NY = ZoneInfo("America/New_York")


def _item(items, gid, group, title, status, detail="", fix="", link=""):
    items.append({"n": len(items) + 1, "id": gid, "group": group, "title": title, "status": status, "detail": detail,
                  "fix": fix, "link": link})


# ---------------------------------------------------------------- independent indicator implementations
def ref_supertrend(h, l, c, period, mult):
    """Plain-loop Supertrend written separately from app.indicators (TradingView definition)."""
    n = len(c)
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    atr = [math.nan] * n
    if n >= period:
        atr[period - 1] = sum(tr[:period]) / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    line, up = [math.nan] * n, [False] * n
    fu = fl = None
    trend = 1
    for i in range(n):
        if math.isnan(atr[i]):
            continue
        mid = (h[i] + l[i]) / 2
        bu, bl = mid + mult * atr[i], mid - mult * atr[i]
        if fu is None:
            nfu, nfl = bu, bl
            trend = 1
        else:
            nfl = bl if (bl > fl or c[i - 1] < fl) else fl
            nfu = bu if (bu < fu or c[i - 1] > fu) else fu
            if line[i - 1] == fu:
                trend = -1 if c[i] > nfu else 1
            else:
                trend = 1 if c[i] < nfl else -1
        fu, fl = nfu, nfl
        line[i] = fl if trend == -1 else fu
        up[i] = trend == -1
    return line, up


def ref_adx(h, l, c, n):
    N = len(c)
    pdm, mdm, tr = [math.nan] * N, [math.nan] * N, [math.nan] * N
    for i in range(1, N):
        u, d = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm[i] = u if (u > d and u > 0) else 0.0
        mdm[i] = d if (d > u and d > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))

    def wilder(x, start):
        out = [math.nan] * N
        if start + n > N:
            return out
        out[start + n - 1] = sum(x[start:start + n]) / n
        for i in range(start + n, N):
            out[i] = (out[i - 1] * (n - 1) + x[i]) / n
        return out
    T, P, M = wilder(tr, 1), wilder(pdm, 1), wilder(mdm, 1)
    dx = [math.nan] * N
    for i in range(N):
        if not math.isnan(T[i]) and T[i] > 0:
            p, m = 100 * P[i] / T[i], 100 * M[i] / T[i]
            dx[i] = abs(p - m) / (p + m) if p + m else 0.0
    first = next((i for i, v in enumerate(dx) if not math.isnan(v)), N)
    a = wilder(dx, first)
    return [100 * v if not math.isnan(v) else math.nan for v in a]


def indicator_table(s, now=None, rows=12):
    """Bot values vs an independent recompute (and room for TradingView values typed in the page)."""
    now = now or md.now_utc()
    out = {"strategy": s.id, "name": s.name, "rows": [], "cols": [], "max_diff": 0.0}
    if s.family == "signal":
        se = metals.series(s.sym, now)
        adj4, raw4, f = se["adj4"], se["raw4"], se["factor4"].values
        res = s.compute(adj4)
        h, l, c = (adj4[k].values.astype(float).tolist() for k in ("h", "l", "c"))
        ends = pd.to_datetime(raw4["end"], utc=True)
        if s.type == "supertrend":
            line, up = ref_supertrend(h, l, c, s.params["atr"], s.params["mult"])
            adx = ref_adx(h, l, c, s.params["adx_len"])
            out["cols"] = ["Close", "Supertrend · bot", "Supertrend · check", "ADX · bot", "ADX · check"]
            for i in range(len(c) - rows, len(c)):
                a, b = res["st_line"].iloc[i] / f[i], line[i] / f[i]
                d1, d2 = float(res["adx"].iloc[i]), adx[i]
                diff = max(abs(a - b) / max(abs(a), 1e-9), abs(d1 - d2) / 100 if not (math.isnan(d1) or math.isnan(d2)) else 0)
                out["max_diff"] = max(out["max_diff"], diff)
                out["rows"].append({"t": int(ends.iloc[i].timestamp()), "vals": [float(raw4["c"].iloc[i]), a, b, d1, d2],
                                    "ok": diff < 1e-6})
        else:
            ne, nx = s.params["entry"], s.params["exit"]
            out["cols"] = ["Close", f"{ne}-bar high · bot", f"{ne}-bar high · check", f"{nx}-bar low · bot", f"{nx}-bar low · check"]
            for i in range(len(c) - rows, len(c)):
                hb, lb = res["hh"].iloc[i] / f[i], res["ll"].iloc[i] / f[i]
                hc, lc = max(h[i - ne:i]) / f[i], min(l[i - nx:i]) / f[i]
                diff = max(abs(hb - hc), abs(lb - lc)) / max(hb, 1e-9)
                out["max_diff"] = max(out["max_diff"], diff)
                out["rows"].append({"t": int(ends.iloc[i].timestamp()), "vals": [float(raw4["c"].iloc[i]), hb, hc, lb, lc], "ok": diff < 1e-9})
    elif hasattr(s, "check_table"):
        out["cols"], out["rows"], out["max_diff"] = s.check_table(now, rows)
    else:
        p = s.params
        fr = s.frame(now)
        closes = fr["c"].values.tolist()
        out["cols"] = ["Close", f"SMA{p['ma_days']} · bot", f"SMA{p['ma_days']} · check", "Vol · bot", "Vol · check", "State"]
        for i in range(len(closes) - rows, len(closes)):
            sl = sum(closes[i - p["ma_days"] + 1:i + 1]) / p["ma_days"]
            rets = [math.log(closes[k] / closes[k - 1]) for k in range(i - p["vol_days"] + 1, i + 1)]
            m = sum(rets) / len(rets)
            vol = math.sqrt(sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252)
            a, v = float(fr["sma_long"].iloc[i]), float(fr["vol"].iloc[i])
            diff = max(abs(a - sl) / sl, abs(v - vol))
            out["max_diff"] = max(out["max_diff"], diff)
            out["rows"].append({"t": int(pd.Timestamp(fr.index[i]).timestamp()), "vals": [closes[i], a, sl, v * 100, vol * 100, fr["state"].iloc[i]],
                                "ok": diff < 1e-9})
    out["rows"].reverse()
    return out


# ---------------------------------------------------------------- the check
def run(now=None, send=True):
    now = now or md.now_utc()
    items = []
    settings = db.get_settings()
    t0 = time.time()

    hb = db.get_state("heartbeat") or {}
    age = time.time() - (hb.get("last") or 0)
    gaps = [g for g in hb.get("gaps", []) if time.time() - g[1] < 86400]
    if age > 300:
        _item(items, "heartbeat", "Bot ran", "Scheduler heartbeat", "error", f"Last tick {age / 60:.0f} min ago.",
              "Check that the server is running (docker compose ps) and SCHEDULER_ENABLED=1 on exactly one copy.", "#/logs")
    elif gaps:
        _item(items, "heartbeat", "Bot ran", "Scheduler heartbeat", "warn", f"{len(gaps)} pause(s) longer than 10 min in the last 24 h.",
              "Usually a restart or a sleeping Mac. Nothing to do if it was planned.", "#/logs")
    else:
        _item(items, "heartbeat", "Bot ran", "Scheduler heartbeat", "ok", "Ticked without gaps in the last 24 h.", link="#/logs")

    bad = []
    for r in db.rows("SELECT ss.*, s.name FROM strategy_state ss JOIN strategies s ON s.id=ss.strategy WHERE s.archived=0"):
        if not r["ok"] or time.time() - (r["computed_at"] or 0) > 900:
            bad.append(f"{r['name']}: {r['error'] or 'not evaluated recently'}")
    _item(items, "evaluate", "Bot ran", "Every strategy evaluated", "error" if bad else "ok",
          "; ".join(bad) if bad else f"{len(S.rows())} strategies evaluated in the last 15 minutes.",
          "Open Logs and the strategy page for the error." if bad else "", "#/strategies")

    ds = db.get_state("data_status") or {}
    stale = []
    for key, st in ds.items():
        if not st.get("ok"):
            stale.append(f"{key}: {st.get('error', 'failed')}")
    for s in S.all_instances():
        r = db.one("SELECT bar_time FROM strategy_state WHERE strategy=?", (s.id,))
        if r and r["bar_time"]:
            lim = 8 * 3600 if s.family == "signal" else 4 * 86400
            open_mkt = True
            if s.family == "signal":
                open_mkt = all(market_open_ny((now - timedelta(hours=k)).astimezone(NY)) for k in range(1, 9))
            else:
                open_mkt = mh.is_trading_day((now - timedelta(days=1)).astimezone(NY).date())
            if now.timestamp() - r["bar_time"] > lim and open_mkt and md.source() != "csv":
                stale.append(f"{s.name}: last bar {datetime.fromtimestamp(r['bar_time']).strftime('%d %b %H:%M')}")
    _item(items, "data", "Data", "Prices are fresh", "warn" if stale else "ok", "; ".join(stale[:5]) if stale else
          "Futures and ETF bars updated on time.", "Yahoo sometimes fails for a while; the bot retries every tick." if stale else "",
          "#/settings")

    worst, names = 0.0, []
    for s in S.all_instances():
        try:
            tbl = indicator_table(s, now, rows=30)
            worst = max(worst, tbl["max_diff"])
            if tbl["max_diff"] > 1e-6:
                names.append(s.name)
        except Exception as e:
            names.append(f"{s.name} ({e})")
    _item(items, "indicators", "Data", "Indicators match an independent recompute", "error" if names else "ok",
          ("Differences: " + ", ".join(names)) if names else f"All strategies · last 30 bars · largest gap {worst:.1e}.",
          "Send the Health report to the developer." if names else "", "#/health")

    for mode in brokers.enabled_modes(settings):
        label = brokers.MODE_LABEL[mode]
        try:
            b = brokers.get(mode, settings)
            ok, why = b.ready()
            if not ok:
                _item(items, f"conn_{mode}", label, f"{label}: connection", "error" if mode == "live" else "warn", why,
                      "Open the Webull page and press Connect.", "#/webull")
                continue
            acct = b.account()
        except Exception as e:
            _item(items, f"conn_{mode}", label, f"{label}: account", "error", str(e)[:200], "Open the Webull page.", "#/webull")
            continue
        books = {}
        for r in db.rows("SELECT symbol, SUM(qty) q FROM holdings WHERE mode=? AND qty>1e-9 GROUP BY symbol", (mode,)):
            books[r["symbol"]] = r["q"]
        diffs = []
        for sym, q in books.items():
            have = ((acct.get("positions") or {}).get(sym) or {}).get("qty", 0.0)
            if q > have + 1e-6:
                diffs.append(f"{sym}: bot {q:.0f} vs account {have:.0f}")
        _item(items, f"books_{mode}", label, f"{label}: bot books = account positions", "error" if diffs else "ok",
              "; ".join(diffs) if diffs else f"{len(books)} symbol(s), all present in the account.",
              "Something was sold by hand or an order filled without the bot seeing it. Check Positions." if diffs else "", "#/positions")
        s_cash, p_cash = ledger.strategies_cash(mode), ledger.pool_cash(mode)
        cash_need = s_cash + p_cash
        cash = acct.get("cash") or 0.0
        st = "error" if cash_need > cash + 1 else "ok"
        _item(items, f"cash_{mode}", label, f"{label}: cash adds up", st,
              f"Account cash ${cash:,.2f} · bot's cash ${cash_need:,.2f} (strategies ${s_cash:,.2f} + bot unassigned ${p_cash:,.2f}) · "
              f"not for the bot ${cash - cash_need:,.2f}",
              "The bot's books have more cash than the account (money left Webull?). Return money to Webull or withdraw from a strategy."
              if st == "error" else "", "#/money")
        neg = db.rows("SELECT strategy, cash FROM ledger WHERE mode=? AND cash < -1", (mode,))
        _item(items, f"neg_{mode}", label, f"{label}: no strategy below $0, no shorts", "error" if neg else "ok",
              "; ".join(f"{r['strategy']} ${r['cash']:,.2f}" for r in neg) if neg else "All strategies have cash ≥ 0 and long positions only.")
        since = int(time.time()) - 86400
        rej = db.rows("SELECT symbol, side, error FROM orders WHERE mode=? AND status='failed' AND updated_at>=?", (mode, since))
        n_sent = db.one("SELECT COUNT(*) n FROM orders WHERE mode=? AND submitted_at>=?", (mode, since))["n"]
        _item(items, f"rejected_{mode}", label, f"{label}: no order refused", "warn" if rej else "ok",
              "; ".join(f"{r['side']} {r['symbol']}: {r['error']}" for r in rej[:4]) if rej else f"{n_sent} order(s) sent in 24 h, 0 refused.",
              "Open Orders to see the plan; the bot retried automatically." if rej else "", "#/orders")
        ret = db.rows("SELECT o.strategy, o.symbol, o.side, o.lot, o.retry FROM orders o WHERE o.mode=? AND o.retry>0 AND o.updated_at>=?",
                      (mode, since))
        _item(items, f"retries_{mode}", label, f"{label}: lots filled without retries", "warn" if ret else "ok",
              (f"{len(ret)} lot(s) needed a retry, e.g. {ret[0]['side']} {ret[0]['symbol']} lot {ret[0]['lot']}" if ret else "Every lot filled first time."),
              "Nothing urgent. If it repeats, use fewer, larger lots or a wider limit offset in Execution." if ret else "", "#/orders")
        stuck = db.rows("SELECT id, symbol FROM orders WHERE mode=? AND status IN ('sending','submitted','unknown') AND submitted_at < ?",
                        (mode, int(time.time()) - 45 * 60))
        _item(items, f"stuck_{mode}", label, f"{label}: no stuck orders", "error" if stuck else "ok",
              f"{len(stuck)} order(s) waiting more than 45 min" if stuck else "Nothing left 'sending' or 'unknown' for more than 45 min.",
              "Check the order in the Webull app, then cancel the plan in Orders." if stuck else "", "#/orders")
        if mode in ("test", "live"):
            stt = b.status()
            lap = stt.get("lapses_at")
            if lap and lap - time.time() < 3 * 86400:
                _item(items, f"token_{mode}", label, f"{label}: login valid", "warn",
                      f"Webull's token ends {datetime.fromtimestamp(lap).strftime('%d %b %H:%M')}.",
                      "Press Reconnect on the Webull page and approve the SMS code in the Webull app.", "#/webull")
            else:
                _item(items, f"token_{mode}", label, f"{label}: login valid", "ok",
                      (f"Token valid until {datetime.fromtimestamp(lap).strftime('%d %b %Y')}." if lap else "Token in use."), link="#/webull")

    line = notify.summary()
    if not line["configured"]:
        _item(items, "line", "Alerts", "LINE alerts set up", "warn", "No channel token or recipient yet.", "Open LINE alerts and add them.", "#/line")
    elif line["failed_24h"]:
        _item(items, "line", "Alerts", "LINE messages delivered", "warn", f"{line['failed_24h']} message(s) failed in 24 h.",
              "Open LINE alerts → Recently sent for the error.", "#/line")
    else:
        q = line.get("quota") or {}
        _item(items, "line", "Alerts", "LINE messages delivered", "ok", f"{line['sent_24h']} sent in 24 h" +
              (f" · quota {q.get('used')} / {q.get('limit')}" if q.get("limit") else ""), link="#/line")

    files = sorted(BACKUP_DIR.glob("bot-*.db")) if BACKUP_DIR.exists() else []
    if files and time.time() - files[-1].stat().st_mtime < 36 * 3600:
        _item(items, "backup", "Server", "Last night's database backup", "ok", f"{files[-1].name} · {files[-1].stat().st_size / 1e6:.1f} MB",
              link="#/settings")
    else:
        _item(items, "backup", "Server", "Last night's database backup", "warn", "No backup in the last 36 h.",
              "Backups run at 03:30 Bangkok while the bot runs. Settings → Download backup makes one now.", "#/settings")

    counts = {k: sum(1 for i in items if i["status"] == k) for k in ("ok", "warn", "error")}
    rep = {"t": int(time.time()), "took": round(time.time() - t0, 2), "items": items, "counts": counts}
    db.run("INSERT INTO health_runs(t,ok,warn,err,report) VALUES(?,?,?,?,?)",
           (rep["t"], counts["ok"], counts["warn"], counts["error"], json.dumps(rep)))
    db.add_event("warn" if counts["error"] or counts["warn"] else "info", "health",
                 f"Health check: {counts['ok']} ok, {counts['warn']} warning(s), {counts['error']} problem(s)", "")
    if send:
        probs = [i for i in items if i["status"] == "error"]
        warns = [i for i in items if i["status"] == "warn"]
        if probs:
            notify.send("health_problem", "Health check found a problem:\n" + "\n".join(f"• {i['title']}: {i['detail']}" for i in probs),
                        critical=True)
        if warns:
            notify.send("health_warning", "Health check: " + "; ".join(f"{i['title']} ({i['detail']})" for i in warns))
    return rep


def latest():
    r = db.one("SELECT report FROM health_runs ORDER BY id DESC LIMIT 1")
    return json.loads(r["report"]) if r else None


def history(days=20):
    return db.rows("SELECT id, t, ok, warn, err FROM health_runs WHERE t>=? ORDER BY id", (int(time.time()) - days * 86400 * 2,))


_ = (np, timedelta, mh)
