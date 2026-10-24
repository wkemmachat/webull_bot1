"""Backtest: run a strategy's own code over past prices and simulate what the bot would have held.

The signals come from exactly the code that trades (strategy.frame / strategy.compute), on the same bars the bot uses.
What is simulated (money starts at $10,000):
  * Daily strategies (QLD regime, 2x Semis, QLD + Trend + bear-dip): decided on the US close, traded at the NEXT
    open (like the research and the bot), rebalanced when a holding drifts more than the rebalance band.
  * 4H metals strategies: the signal is known when a 4H futures bar closes (+ Yahoo's delay); the trade happens at the
    bot's real start time (entries not before the Execution start time, e.g. 22:00 Bangkok; exits as soon as the US
    market is open), spread over the strategy's lots, priced from hourly ETF bars.
  * Prices are total return (dividends included), so T-bill ETFs earn their interest. 0.05% cost per side.
  * Not simulated: partial fills, the money guard, add/withdraw. Leveraged ETFs exist only since 2006-2008.
Results are cached in memory until the data or the settings change.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import db, marketdata as md, markethours as mh, metals
from . import strategies as S

log = logging.getLogger("backtest")
NY = ZoneInfo("America/New_York")
COST = 0.0005
START_CASH = 10_000.0
REFRESH_S = 12 * 3600
RANGES = [("1Y", 1), ("3Y", 3), ("5Y", 5), ("10Y", 10), ("MAX", None)]
INDEX_FOR_METAL = {"GC": "GLD", "SI": "SLV"}
RF_SYMBOL = "BIL"
_cache: dict = {}
_lock = threading.Lock()

# Headline numbers of the research behind each default strategy (Docs → The strategies).
RESEARCH = {
    "gold_sta": {"source": "Gold & Silver research · 10-year ETF test", "period": "Apr 2016 – Oct 2026", "cagr": 10.3, "maxdd": -13.2},
    "gold_st30": {"source": "Gold & Silver research · 10-year ETF test", "period": "Apr 2016 – Oct 2026", "cagr": 11.5, "maxdd": -13.4},
    "silver_dc": {"source": "Gold & Silver research · 10-year ETF test", "period": "Apr 2016 – Oct 2026", "cagr": 15.5, "maxdd": -33.9},
    "silver_st": {"source": "Gold & Silver research · 10-year ETF test", "period": "Apr 2016 – Oct 2026", "cagr": 17.2, "maxdd": -34.3},
    "qld_regime": {"source": "Strategy to beat QQQ · strategy F (next-open fills)", "period": "2016 – 2026", "cagr": 39.7},
    "semis_regime": {"source": "Strategy to beat QQQ · strategy U", "period": "2007 – 2026", "maxdd": -46.0},
    "qld_tbd": {"source": "ETF Strategy Lab, 23 Oct 2026", "period": "Oct 2007 – Oct 2026", "cagr": 32.9, "maxdd": -42.5, "sharpe": 0.95,
                "bench": "QQQ held: 15.1% a year, worst fall −53.3%"},
}


class BacktestError(Exception):
    pass


# ---------------------------------------------------------------- data
def _yf():
    import yfinance as yf
    return yf


def _store(sym, tf, df, replace):
    rows = [(sym, tf, int(t.timestamp()), float(r.o), float(r.h), float(r.l), float(r.c), float(r.v or 0)) for t, r in df.iterrows()]
    with db.tx() as c:
        if replace:
            c.execute("DELETE FROM bars WHERE symbol=? AND tf=?", (sym, tf))
        c.executemany("INSERT INTO bars(symbol,tf,t,o,h,l,c,v) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(symbol,tf,t) DO UPDATE "
                      "SET o=excluded.o,h=excluded.h,l=excluded.l,c=excluded.c,v=excluded.v", rows)
    db.set_state(f"bt_upd:{sym}:{tf}", int(time.time()))


def _fresh(sym, tf):
    return time.time() - (db.get_state(f"bt_upd:{sym}:{tf}") or 0) < REFRESH_S


def _norm(h, daily):
    h = h.rename(columns={"Open": "o", "High": "h", "Low": "l", "Close": "c", "Volume": "v"})
    if daily:
        h.index = pd.to_datetime([d.strftime("%Y-%m-%d") for d in h.index]).tz_localize("UTC")
    else:
        idx = h.index if h.index.tz is not None else h.index.tz_localize("America/New_York")
        h.index = idx.tz_convert("UTC")
    h = h[["o", "h", "l", "c", "v"]].astype(float)
    return h[(h.c > 0)].dropna(subset=["o", "c"])


def daily_tr(sym) -> pd.DataFrame:
    """Daily bars adjusted for splits AND dividends (total return). Downloaded in full (dividends rescale the past)."""
    if md.source() == "csv":
        try:
            return md._csv(sym, "1d")
        except Exception:
            return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    if not _fresh(sym, "1dtr"):
        try:
            h = _yf().Ticker(md.yahoo_ticker(sym)).history(period="max", interval="1d", auto_adjust=True, actions=False)
            if h is not None and not h.empty:
                _store(sym, "1dtr", _norm(h, True), replace=True)
        except Exception as e:
            log.warning("backtest daily %s: %s", sym, e)
    return md.load(sym, "1dtr")


def hourly_etf(sym) -> pd.DataFrame:
    """Hourly ETF bars of the last ~2 years (Yahoo's limit), for the intraday fill prices of the metals strategies."""
    if md.source() == "csv":
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    if not _fresh(sym, "1h"):
        try:
            h = _yf().Ticker(sym).history(period="729d", interval="1h", auto_adjust=False, prepost=False, actions=False)
            if h is not None and not h.empty:
                _store(sym, "1h", _norm(h, False), replace=False)
        except Exception as e:
            log.warning("backtest hourly %s: %s", sym, e)
    return md.load(sym, "1h")


def ensure_signal_history(sym):
    """The daily signal index needs a long history (the bot itself keeps ~6 years): download it all once a day."""
    if md.source() == "csv" or _fresh(sym, "1dmax"):
        return
    try:
        h = _yf().Ticker(md.yahoo_ticker(sym)).history(period="max", interval="1d", auto_adjust=False, actions=False)
        if h is not None and not h.empty:
            _store(sym, "1d", _norm(h, True), replace=False)
            db.set_state(f"bt_upd:{sym}:1dmax", int(time.time()))
    except Exception as e:
        log.warning("backtest signal history %s: %s", sym, e)


# ---------------------------------------------------------------- prices during a day
class Prices:
    """Daily total-return bars per symbol + optional hourly bars for prices at a given moment of a US session."""

    def __init__(self, daily: dict, hourly: dict | None = None):
        self.d = {}
        for s, df in daily.items():
            if df is None or df.empty:
                continue
            self.d[s] = {pd.Timestamp(t).date(): (float(r.o), float(r.c)) for t, r in df.iterrows()}
        self.h = {}
        for s, df in (hourly or {}).items():
            if df is None or df.empty:
                continue
            g = {}
            ny = df.index.tz_convert(NY)
            for t, tn, r in zip(df.index, ny, df.itertuples()):
                g.setdefault(tn.date(), []).append((t, float(r.o), float(r.c)))
            self.h[s] = g

    def has(self, s, day):
        return s in self.d and day in self.d[s]

    def open(self, s, day):
        return self.d[s][day][0]

    def close(self, s, day):
        return self.d[s][day][1]

    def at(self, s, t):
        """Price (on the total-return scale) at moment t of a US session."""
        tn = pd.Timestamp(t).tz_convert(NY)
        day = tn.date()
        o, c = self.d[s][day]
        bars = self.h.get(s, {}).get(day)
        if bars:
            last_raw = bars[-1][2]
            pick = bars[0]
            for b in bars:
                if b[0] <= t:
                    pick = b
            frac = min(1.0, max(0.0, (pd.Timestamp(t) - pick[0]).total_seconds() / 3600))
            raw = pick[1] + (pick[2] - pick[1]) * frac
            return c * raw / last_raw if last_raw else c
        b = mh.session_bounds(day, "CORE")
        if not b:
            return c
        f = min(1.0, max(0.0, (pd.Timestamp(t) - pd.Timestamp(b[0])).total_seconds() / (pd.Timestamp(b[1]) - pd.Timestamp(b[0])).total_seconds()))
        return o + (c - o) * f


# ---------------------------------------------------------------- the account being simulated
class Book:
    def __init__(self, cost=COST):
        self.cash, self.sh, self.cost, self.trades, self.fees = START_CASH, {}, cost, [], 0.0

    def value(self, px):
        return self.cash + sum(q * px[s] for s, q in self.sh.items() if q)

    def weights(self, px):
        v = self.value(px)
        return {s: q * px[s] / v for s, q in self.sh.items() if q} if v > 0 else {}

    def rebalance(self, target, px, t, why, kind):
        v = self.value(px)
        before = {s: round(w, 4) for s, w in self.weights(px).items() if w > 0.0005}
        traded = 0.0
        for s in set(self.sh) | set(target):
            want = target.get(s, 0.0) * v / px[s]
            dq = want - self.sh.get(s, 0.0)
            if abs(dq * px[s]) < 0.01:
                continue
            traded += abs(dq * px[s])
            self.cash -= dq * px[s]
            self.sh[s] = want
        fee = traded * self.cost
        self.cash -= fee
        self.fees += fee
        self.sh = {s: q for s, q in self.sh.items() if abs(q) > 1e-12}
        self.trades.append({"t": int(pd.Timestamp(t).timestamp()), "kind": kind, "why": why, "from": before,
                            "to": {s: round(w, 4) for s, w in target.items() if w > 0.0005},
                            "prices": {s: round(px[s], 4) for s in set(before) | set(target) if s in px}, "value": round(v - fee, 2)})


# ---------------------------------------------------------------- daily strategies
def _run_daily(strat, now, cost):
    p = strat.params
    sig = p["signal"]
    ensure_signal_history(sig)
    fr = strat.frame(now)
    fr = fr[fr["state"] != ""]
    syms = [s for s in strat.trade_symbols() if s]
    daily = {s: daily_tr(s) for s in set(syms) | {sig, RF_SYMBOL}}
    for s in syms:
        if daily[s] is None or daily[s].empty:
            raise BacktestError(f"No price history for {s}")
    P = Prices(daily)
    trade = p["trade"]
    days = [pd.Timestamp(t).date() for t in daily[trade].index]
    first = max(min(P.d[s]) for s in syms)
    states = {pd.Timestamp(t).date(): s for t, s in zip(fr.index, fr["state"].values)}
    days = [d for d in days if d >= first and d in states and all(P.has(s, d) for s in syms)]
    if len(days) < 30:
        raise BacktestError("Not enough overlapping history yet")
    band = strat.rebalance_band()
    B = Book(cost)
    eq, expo, held_state = [], [], []
    pending, last_state, last_target = None, None, None
    for i, d in enumerate(days):
        if pending is not None:
            px = {s: P.open(s, d) for s in syms}
            B.rebalance(pending[0], px, datetime.combine(d, datetime.min.time(), NY).replace(hour=9, minute=30), pending[1], pending[2])
            pending = None
        pxc = {s: P.close(s, d) for s in syms}
        v = B.value(pxc)
        eq.append(v)
        w = B.weights(pxc)
        expo.append(w.get(trade, 0.0))
        st = states[d]
        held_state.append(st)
        target = strat.target_for(st)
        if target != last_target:                    # like the bot: a plan only when the target changes (trend ↔ dip: no trade)
            kind = "START" if last_target is None else ("BUY" if target.get(trade, 0) > last_target.get(trade, 0) else "SELL")
            why = f"{sig} close {fr.loc[pd.Timestamp(d).tz_localize('UTC'), 'c']:,.2f}: state {last_state or 'start'} → {st}"
            if last_state is not None:
                try:
                    why = strat.why(fr, fr.index.get_loc(pd.Timestamp(d).tz_localize("UTC")))
                except Exception:
                    pass
            pending = (target, why, kind)
            last_target = target
        last_state = st
        if pending is not None and pending[2] != "REBALANCE":
            continue
        if w and max(abs(w.get(k, 0.0) - target.get(k, 0.0)) for k in set(w) | set(target)) > band:
            pending = (target, f"rebalance: a holding drifted more than {band * 100:g}% from its target", "REBALANCE")
    return {"days": days, "eq": eq, "expo": expo, "trades": B.trades, "fees": B.fees, "state": held_state,
            "bench": {trade: daily[trade], sig: daily[sig]}, "rf": daily.get(RF_SYMBOL), "main": trade, "index": sig,
            "data_from": str(days[0]), "data_note": f"{sig} daily closes (signal) · {', '.join(syms)} daily total-return prices"}


# ---------------------------------------------------------------- 4H metals strategies
def _exec_start(want, avail, cfg):
    sess = cfg.get("session") or "CORE"
    if want:
        return mh.start_time(avail, cfg["start_mode"], cfg["start_time"], sess)
    if cfg.get("exit_mode", "asap") == "asap":
        return mh.next_open(avail, sess)
    return mh.start_time(avail, cfg["start_mode"], cfg["start_time"], sess)


def _run_metals(strat, now, cost, cfg):
    p = strat.params
    se = metals.series(strat.sym, now)
    adj4, raw4 = se["adj4"], se["raw4"]
    if len(adj4) < strat.warmup() + 20:
        raise BacktestError(f"Not enough 4H bars yet ({len(adj4)})")
    res = strat.compute(adj4)
    want = res["want"].values
    ends = pd.to_datetime(raw4["end"], utc=True)
    delay = timedelta(minutes=metals.delay_min() + 2)
    etf, cash = p["etf"], p["cash_etf"]
    syms = [s for s in (etf, cash) if s]
    idx_sym = INDEX_FOR_METAL.get(strat.sym)
    daily = {s: daily_tr(s) for s in set(syms) | {RF_SYMBOL, idx_sym} if s}
    for s in syms:
        if daily[s] is None or daily[s].empty:
            raise BacktestError(f"No price history for {s}")
    hourly = {s: hourly_etf(s) for s in syms}
    P = Prices({s: daily[s] for s in syms}, hourly)
    w0 = strat.warmup()
    t0 = ends.iloc[w0]
    target_long = {etf: round(1 - strat.buffer(), 4)}
    target_flat = strat.cash_target()
    lots, interval = int(cfg.get("lots") or 10), float(cfg.get("interval_min") or 10)
    # decisions: when each new signal can be acted on
    dec = []
    for i in range(w0, len(want)):
        if i == w0 or want[i] != want[i - 1]:
            dec.append((ends.iloc[i] + delay, int(want[i]), i))
    B = Book(cost)
    held = None
    fills = []
    k = 0
    while k < len(dec):
        avail, w, i = dec[k]
        if held is not None and w == held:
            k += 1
            continue
        start = _exec_start(w, avail, cfg)
        j = k
        while j + 1 < len(dec) and dec[j + 1][0] <= start:        # a newer signal arrived before the orders went out
            j += 1
        if j != k:
            k = j
            continue
        times = mh.spread_lots(start, lots, interval, cfg.get("session") or "CORE")
        if times[-1] > pd.Timestamp(now):
            break
        fills.append((start, times, w, i))
        held = w
        k += 1
    # walk the trading days, applying fills in time order
    first_day = pd.Timestamp(t0).tz_convert(NY).date()
    days = [pd.Timestamp(t).date() for t in daily[etf].index]
    days = [d for d in days if d >= first_day and all(P.has(s, d) for s in syms)]
    if len(days) < 20:
        raise BacktestError("Not enough overlapping ETF history yet")
    eq, expo, st = [], [], []
    fi = 0
    cur = None
    for d in days:
        while fi < len(fills) and pd.Timestamp(fills[fi][0]).tz_convert(NY).date() <= d:
            start, times, w, i = fills[fi]
            fd = pd.Timestamp(start).tz_convert(NY).date()
            if fd == d:
                ok_times = [t for t in times if pd.Timestamp(t).tz_convert(NY).date() == d] or [start]
                px = {s: float(np.mean([P.at(s, t) for t in ok_times])) for s in syms}
            else:                                   # the start day is missing from the ETF data: use this day's open
                px = {s: P.open(s, d) for s in syms}
            if True:
                if all(s in px for s in syms):
                    why = strat.reason(res, i, float(se["factor4"].iloc[i]), raw4)
                    B.rebalance(target_long if w else target_flat, px, start, why, "BUY" if w else ("SELL" if cur is not None else "START"))
                    cur = w
            fi += 1
        pxc = {s: P.close(s, d) for s in syms}
        eq.append(B.value(pxc))
        expo.append(B.weights(pxc).get(etf, 0.0))
        st.append("long" if cur else "flat")
    bench = {etf: daily[etf]}
    if idx_sym and daily.get(idx_sym) is not None and not daily[idx_sym].empty:
        bench[idx_sym] = daily[idx_sym]
    return {"days": days, "eq": eq, "expo": expo, "trades": B.trades, "fees": B.fees, "state": st, "bench": bench,
            "rf": daily.get(RF_SYMBOL), "main": etf, "index": idx_sym if idx_sym in bench else None,
            "data_from": str(days[0]),
            "data_note": f"{strat.sym}=F hourly futures → 4H bars (Yahoo keeps about 2 years) · {', '.join(syms)} hourly + daily total-return prices"}


# ---------------------------------------------------------------- statistics
def _stats(t, v, rf=None, expo=None):
    v = np.asarray(v, dtype=float)
    if len(v) < 2 or v[0] <= 0:
        return None
    r = v[1:] / v[:-1] - 1
    yrs = max((t[-1] - t[0]).days / 365.25, 1 / 365.25)
    total = v[-1] / v[0] - 1
    cagr = (v[-1] / v[0]) ** (1 / yrs) - 1 if v[-1] > 0 else -1.0
    peak = np.maximum.accumulate(v)
    dd = v / peak - 1
    k = int(np.argmin(dd))
    pk = int(np.argmax(v[:k + 1])) if k > 0 else 0
    rec = None
    if dd[k] < 0:
        after = np.where(v[k:] >= v[pk])[0]
        rec = t[k + after[0]] if len(after) else None
    ex = r - (rf if rf is not None and len(rf) == len(r) else 0)
    sd = float(np.std(r, ddof=1)) if len(r) > 2 else 0.0
    sharpe = float(np.mean(ex) / np.std(ex, ddof=1) * math.sqrt(252)) if len(r) > 2 and np.std(ex, ddof=1) > 0 else None
    out = {"from": str(t[0]), "to": str(t[-1]), "years": round(yrs, 2), "total": round(total * 100, 2), "cagr": round(cagr * 100, 2),
           "vol": round(sd * math.sqrt(252) * 100, 2), "sharpe": round(sharpe, 2) if sharpe is not None else None,
           "maxdd": round(float(dd[k]) * 100, 2), "dd_peak": str(t[pk]), "dd_trough": str(t[k]), "dd_recovered": str(rec) if rec else None,
           "end_value": round(float(v[-1] / v[0] * START_CASH), 2)}
    if expo is not None:
        out["exposure"] = round(float(np.mean(np.asarray(expo) > 0.005)) * 100, 1)
    return out


def _round_trips(trades, main):
    """In → out pairs of the main (leveraged) ETF with the result of each."""
    out, entry = [], None
    for tr in trades:
        was, now_ = tr["from"].get(main, 0) > 0.005, tr["to"].get(main, 0) > 0.005
        if not was and now_:
            entry = tr
        elif was and not now_ and entry:
            out.append({"in": entry["t"], "out": tr["t"], "ret": round((tr["value"] / entry["value"] - 1) * 100, 2),
                        "days": round((tr["t"] - entry["t"]) / 86400, 1)})
            entry = None
    return out


def _series_on(days, df):
    m = {pd.Timestamp(t).date(): float(c) for t, c in zip(df.index, df["c"].values)}
    out, last = [], None
    for d in days:
        last = m.get(d, last)
        out.append(last)
    first = next((x for x in out if x), None)
    return [None if x is None else x / first * START_CASH for x in out] if first else [None] * len(days)


def _build(strat, now, cost):
    from . import execution
    cfg = execution.exec_cfg(strat)
    r = _run_daily(strat, now, cost) if strat.family == "regime" else _run_metals(strat, now, cost, cfg)
    days, eq = r["days"], r["eq"]
    t = [int(datetime.combine(d, datetime.min.time(), timezone.utc).timestamp()) for d in days]
    strat_v = [x / eq[0] * START_CASH for x in eq]
    bench = {s: _series_on(days, df) for s, df in r["bench"].items()}
    rf = None
    if r.get("rf") is not None and not r["rf"].empty:
        rv = _series_on(days, r["rf"])
        if all(x is not None for x in rv):
            rf = np.asarray(rv[1:]) / np.asarray(rv[:-1]) - 1
    # per range
    stats, last = {}, days[-1]
    for key, yrs in RANGES:
        if yrs is None:
            i0 = 0
        else:
            cut = (pd.Timestamp(last) - pd.DateOffset(years=yrs)).date()
            if days[0] > cut + timedelta(days=20):
                continue
            i0 = next(i for i, d in enumerate(days) if d >= cut)
        dd_ = days[i0:]
        st = {"strategy": _stats(dd_, strat_v[i0:], rf[i0:] if rf is not None else None, r["expo"][i0:])}
        for s, v in bench.items():
            vv = v[i0:]
            if all(x is not None for x in vv):
                st[s] = _stats(dd_, vv, rf[i0:] if rf is not None else None)
        t0 = t[i0]
        trs = [x for x in r["trades"] if x["t"] >= t0 and x["kind"] != "START"]
        rts = [x for x in _round_trips(r["trades"], r["main"]) if x["in"] >= t0]
        st["strategy"]["trades"] = len(trs)
        st["strategy"]["per_year"] = round(len(trs) / max(st["strategy"]["years"], 0.1), 1)
        st["strategy"]["round_trips"] = len(rts)
        st["strategy"]["win_rate"] = round(sum(1 for x in rts if x["ret"] > 0) / len(rts) * 100, 1) if rts else None
        st["strategy"]["avg_trip"] = round(float(np.mean([x["ret"] for x in rts])), 2) if rts else None
        stats[key] = st
    # calendar years
    years = []
    yset = sorted({d.year for d in days})
    for y in yset:
        ix = [i for i, d in enumerate(days) if d.year == y]
        i0 = ix[0] - 1 if ix[0] > 0 else ix[0]
        row = {"year": y, "partial": ix[0] == 0 or y == days[-1].year}
        row["strategy"] = round((strat_v[ix[-1]] / strat_v[i0] - 1) * 100, 2)
        for s, v in bench.items():
            if v[ix[-1]] is not None and v[i0] is not None:
                row[s] = round((v[ix[-1]] / v[i0] - 1) * 100, 2)
        years.append(row)
    peak = np.maximum.accumulate(np.asarray(strat_v))
    dd = (np.asarray(strat_v) / peak - 1) * 100
    return {"ok": True, "strategy": strat.id, "name": strat.name, "family": strat.family, "main": r["main"], "index": r["index"],
            "series": {"t": t, "strategy": [round(x, 2) for x in strat_v], "dd": [round(float(x), 2) for x in dd],
                       "expo": [round(float(x), 3) for x in r["expo"]],
                       "bench": {s: [None if x is None else round(x, 2) for x in v] for s, v in bench.items()}},
            "stats": stats, "ranges": [k for k, _ in RANGES if k in stats], "years": years,
            "trades": [x for x in r["trades"]][-400:], "round_trips": _round_trips(r["trades"], r["main"])[-200:],
            "fees": round(r["fees"], 2), "cost_pct": cost * 100, "data": {"from": r["data_from"], "to": str(days[-1]), "note": r["data_note"],
                                                                          "source": md.source()},
            "exec": {k: cfg.get(k) for k in ("lots", "interval_min", "start_mode", "start_time", "exit_mode")},
            "generated_at": int(time.time())}


def _research(strat):
    r = RESEARCH.get(strat.id)
    if not r:
        return None
    from .strategies import DEFAULTS
    seed = next((d for d in DEFAULTS if d[0] == strat.id), None)
    same = bool(seed) and type(strat).merge_params(seed[4]) == strat.params and strat.row.get("type") == seed[1]
    return {**r, "same_settings": same}


def _key(strat, cost):
    from . import execution
    stamp = []
    for tf in ("1d", "1dtr", "1h"):
        x = db.one("SELECT COUNT(*) n, MAX(t) mx FROM bars WHERE tf=?", (tf,))
        stamp.append((tf, x["n"], x["mx"]))
    raw = json.dumps([strat.id, strat.row.get("type"), strat.params, execution.exec_cfg(strat), cost, stamp,
                      int(time.time() // 3600)], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()


def run(sid=None, params=None, now=None, cost=COST, strat=None):
    """Backtest a saved strategy, optionally with other settings (`params`, not saved)."""
    if strat is None:
        row = S.row(sid)
        if not row:
            raise BacktestError("No such strategy")
        if params:
            row = dict(row)
            row["params"] = {**row["params"], **params}
        strat = S.instance(row)
    now = now or md.now_utc()
    key = _key(strat, cost)
    with _lock:
        hit = _cache.get(key)
        if hit:
            return hit
    t0 = time.time()
    try:
        out = _build(strat, now, cost)
    except (BacktestError, md.DataError) as e:
        out = {"ok": False, "strategy": strat.id, "name": strat.name, "error": str(e)}
    out["research"] = _research(strat)
    out["custom"] = bool(params)
    out["ms"] = int((time.time() - t0) * 1000)
    with _lock:
        if len(_cache) > 40:
            _cache.clear()
        _cache[key] = out
    return out
