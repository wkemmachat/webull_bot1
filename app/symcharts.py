"""Candle chart of each symbol a basket strategy trades, with the backtest's buys and sells (and the bot's own fills),
so every trade can be cross-checked against TradingView or Webull.

Candles: Yahoo daily, split-adjusted but NOT dividend-adjusted, so the prices match the charts you see elsewhere.
Markers sit on the day of the trade (the open after the signal). The backtest itself runs on total-return prices;
the % change of a round trip shown here is from the plain prices (dividends not included).
"""
from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import backtest, db, marketdata as md
from . import strategies as S
from .strategies.regime import TV, tv_url

NY = ZoneInfo("America/New_York")
HOLD_MIN = 0.03                  # a holding counts from 3% of the strategy's money (parking leftovers are smaller)
MODE_LABEL = {"paper": "Paper", "test": "Webull test", "live": "Live"}
_cache: dict = {}
_lock = threading.Lock()


class ChartError(Exception):
    pass


def raw_daily(sym) -> pd.DataFrame:
    if md.source() == "csv":
        try:
            return md._csv(sym, "1d")
        except Exception:
            return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    backtest.ensure_signal_history(sym)
    return md.load(sym, "1d")


def _day(t) -> str:
    return str(datetime.fromtimestamp(int(t), NY).date())


def _ts(day: str) -> int:
    return int(pd.Timestamp(day, tz="UTC").timestamp())


def _reason(side, kind, park):
    if kind == "START":
        return "Start of the backtest"
    if park:
        return "Signal off → money parked here" if side == "BUY" else "Signal on → sold to buy the stocks"
    if kind == "LIST":
        return "Joined this week's list" if side == "BUY" else "Left this week's list"
    if kind == "BUY":
        return "Signal on → bought"
    if kind == "SELL":
        return "Signal off → sold"
    return kind.title()


def _candles(sym):
    """(daily candles, fallback?) — Yahoo, else the research's daily open/close (no highs/lows)."""
    df = raw_daily(sym)
    if df is not None and not df.empty:
        return df, False
    from . import basket
    b = basket.prices(sym)
    if b is None or b.empty:
        return None, False
    df = pd.DataFrame({"o": b["o"].values, "c": b["c"].values}, index=pd.to_datetime([str(x) for x in b.index]).tz_localize("UTC"))
    df["h"], df["l"] = df[["o", "c"]].max(axis=1), df[["o", "c"]].min(axis=1)
    return df, True


def _events(trades, sym, park):
    """Buys and sells of `sym` in the backtest: the holding crosses HOLD_MIN of the money."""
    out = []
    for x in trades:
        wf, wt = x["from"].get(sym, 0.0), x["to"].get(sym, 0.0)
        side = "BUY" if wf < HOLD_MIN <= wt else "SELL" if wf >= HOLD_MIN > wt else None
        if not side:
            continue
        out.append({"day": _day(x["t"]), "side": side, "kind": x["kind"], "weight": round((wt if side == "BUY" else wf) * 100, 1),
                    "reason": _reason(side, x["kind"], park), "why": x.get("why") or ""})
    return out


def _symbols(res, strat):
    p = strat.params
    park = list(res.get("parking") or [])
    emap = strat.etf_map() if p.get("leverage") == "2x" else {}
    rev = {v: k for k, v in emap.items()}
    held = set(res.get("holding") or [])
    trades = res["trades"]
    last_to = trades[-1]["to"] if trades else {}
    seen = {}
    for x in trades:
        for s in set(x["from"]) | set(x["to"]):
            seen.setdefault(s, 0)
    for s in seen:
        seen[s] = sum(1 for e in _events(trades, s, s in park) if e["side"] == "BUY")
    rows = [{"sym": p["signal"], "kind": "signal", "label": f"{p['signal']} · signal",
             "buys": sum(1 for x in trades if x["kind"] == "BUY"), "held": False}]
    for s, n in seen.items():
        if n == 0:
            continue
        rows.append({"sym": s, "kind": "parking" if s in park else ("2x ETF" if s in rev else "stock"),
                     "under": rev.get(s), "buys": n, "held": s in held or last_to.get(s, 0) >= HOLD_MIN})
    order = {"signal": 0, "stock": 1, "2x ETF": 1, "parking": 2}
    rows.sort(key=lambda r: (order[r["kind"]], not r["held"], -r["buys"], r["sym"]))
    return rows


def _live_fills(sid, sym):
    rows = db.rows("SELECT mode, side, filled_qty, avg_price, submitted_at, updated_at FROM orders WHERE strategy=? AND symbol=? "
                   "AND filled_qty > 0 AND avg_price > 0 ORDER BY submitted_at", (sid, sym))
    agg = {}
    for r in rows:
        k = (r["mode"], _day(r["submitted_at"] or r["updated_at"]), (r["side"] or "").upper())
        a = agg.setdefault(k, [0.0, 0.0, 0])
        a[0] += r["filled_qty"]
        a[1] += r["filled_qty"] * r["avg_price"]
        a[2] += 1
    return [{"mode": m, "mode_label": MODE_LABEL.get(m, m), "day": d, "side": s, "qty": round(q, 4), "price": round(v / q, 4),
             "orders": n} for (m, d, s), (q, v, n) in sorted(agg.items(), key=lambda kv: kv[0][1])]


def _trips(evs, px, last_close):
    out, open_ = [], None
    for e in evs:
        if e["side"] == "BUY":
            open_ = e
        elif open_ is not None:
            a, b = open_.get("price"), e.get("price")
            out.append({"buy_day": open_["day"], "buy_price": a, "sell_day": e["day"], "sell_price": b,
                        "ret": round((b / a - 1) * 100, 2) if a and b else None,
                        "days": (pd.Timestamp(e["day"]) - pd.Timestamp(open_["day"])).days,
                        "in": open_["reason"], "out": e["reason"], "sim": bool(open_.get("sim"))})
            open_ = None
    if open_ is not None:
        a = open_.get("price")
        out.append({"buy_day": open_["day"], "buy_price": a, "sell_day": None, "sell_price": last_close,
                    "ret": round((last_close / a - 1) * 100, 2) if a and last_close else None,
                    "days": None, "in": open_["reason"], "out": "still held", "sim": bool(open_.get("sim"))})
    return list(reversed(out))


def build(sid, sym=None):
    row = S.row(sid)
    if not row:
        raise ChartError("No such strategy")
    strat = S.instance(row)
    if strat.type != "momentum_basket":
        raise ChartError("Charts by symbol are for the stock-basket strategies")
    res = backtest.run(sid)
    if not res.get("ok"):
        raise ChartError(res.get("error") or "Backtest not possible yet")
    syms = _symbols(res, strat)
    known = {r["sym"]: r for r in syms}
    p = strat.params
    emap = strat.etf_map() if p.get("leverage") == "2x" else {}
    if not sym:
        sym = next((r["sym"] for r in syms if r["held"]), syms[0]["sym"])
    sym = sym.upper()
    from . import basket
    if sym not in known and sym not in emap and sym not in basket.members():
        raise ChartError(f"{sym} is not traded by this strategy")
    key = (sid, sym, res.get("generated_at"), md.source())
    with _lock:
        hit = _cache.get(key)
    if hit:
        return {**hit, "symbols": syms}
    under = {v: k for k, v in emap.items()}.get(sym)
    df, fallback = _candles(sym)
    drawn_on = sym
    if (df is None or df.empty) and under:               # the 2x ETF has no prices yet: draw its (simulated) trades on the stock
        df, fallback = _candles(under)
        drawn_on = under
    if df is None or df.empty:
        raise ChartError(f"No daily prices for {sym} from Yahoo yet — try again in a minute")
    start = pd.Timestamp(res["data"]["from"], tz="UTC") - pd.Timedelta(days=45)
    df = df[df.index >= start]
    days = [str(pd.Timestamp(t).date()) for t in df.index]
    o = dict(zip(days, df["o"].astype(float)))
    c = dict(zip(days, df["c"].astype(float)))
    first = days[0] if days else None
    import bisect

    def snap(day):
        """The candle a trade day is drawn on: that day, else the next trading day with a candle."""
        i = bisect.bisect_left(days, day)
        return days[min(i, len(days) - 1)] if days else day
    park = set(res.get("parking") or [])
    info = known.get(sym) or {"sym": sym, "kind": "stock", "buys": 0, "held": False}
    notes, markers = [], []
    if fallback:
        notes.append(f"No Yahoo candles for {drawn_on}: drawn from the research's daily open/close (dividends included), no highs/lows.")
    if drawn_on != sym:
        notes.append(f"No prices for {sym} yet: its trades are drawn on {drawn_on} (the backtest used 2× {drawn_on}'s daily move).")
    trades = sorted(res["trades"], key=lambda x: x["t"])

    if info["kind"] == "signal":
        evs = []
        for x in trades:
            if x["kind"] not in ("BUY", "SELL"):
                continue
            fill = _day(x["t"])
            prior = [d for d in days if d < fill]
            sday = prior[-1] if prior else fill
            evs.append({"day": sday, "fill_day": fill, "side": "ON" if x["kind"] == "BUY" else "OFF", "price": c.get(sday),
                        "reason": "Signal on: buy the stocks next open" if x["kind"] == "BUY" else "Signal off: sell, park in " + " + ".join(sorted(park)),
                        "why": x.get("why") or ""})
        for e in evs:
            on = e["side"] == "ON"
            markers.append({"time": _ts(snap(e["day"])), "position": "belowBar" if on else "aboveBar", "color": "#2962FF" if on else "#E040FB",
                            "shape": "arrowUp" if on else "arrowDown", "text": "On" if on else "Off"})
        notes.append(f"Markers sit on the close where the {sym} signal changed; the stocks are traded at the next open.")
        trips = []
    else:
        evs = _events(trades, sym, sym in park)
        for e in evs:
            e["price"] = o.get(snap(e["day"]))
        if drawn_on != sym:
            for e in evs:
                e["sim"] = True
        elif under and first:
            early = [e for e in evs if e["day"] < first]
            if early:
                notes.append(f"{len(early)} earlier trade(s) were before {sym} existed: the backtest used 2× {under}'s daily move. "
                             f"They are shown on the {under} chart.")
            evs = [e for e in evs if e["day"] >= first]
        if sym in emap:                                   # the stock of a 2x strategy: the simulated trades before its ETF existed
            etf = emap[sym]
            edf, _ = _candles(etf)
            efirst = str(pd.Timestamp(edf.index[0]).date()) if edf is not None and not edf.empty else "9999-12-31"
            sim = [e for e in _events(trades, etf, False) if e["day"] < efirst]
            for e in sim:
                e["price"], e["sim"] = o.get(snap(e["day"])), True
                e["reason"] += f" (as 2× {sym}: {etf} did not exist yet)"
            evs = sim
            notes.append(f"This strategy holds {sym} through {etf}. Shown here: only the trades before {etf} existed "
                         f"(first {etf} price {efirst}), simulated as 2× {sym}.")
        for e in evs:
            b = e["side"] == "BUY"
            markers.append({"time": _ts(snap(e["day"])), "position": "belowBar" if b else "aboveBar", "color": "#26A69A" if b else "#EF5350",
                            "shape": "arrowUp" if b else "arrowDown", "text": ("Buy" if b else "Sell") + (" 2x sim" if e.get("sim") else "")})
        missing = [e for e in evs if e["day"] not in o]
        if missing:
            notes.append(f"{len(missing)} trade day(s) have no Yahoo candle (holiday or data gap): drawn on the next candle.")
        trips = _trips(evs, o, c.get(days[-1]) if days else None)
        if sym in park:
            notes.append("Parking: only moving in (signal off) and out (signal on) is marked; small leftovers parked between trades are not.")
    live = _live_fills(sid, sym)
    for f in live:
        b = f["side"] == "BUY"
        if days and f["day"] >= days[0]:
            markers.append({"time": _ts(snap(f["day"])), "position": "belowBar" if b else "aboveBar",
                            "color": "#2962FF" if b else "#FF9800", "shape": "circle", "text": f"Bot {'buy' if b else 'sell'} · {f['mode_label']}"})
    candles = [{"time": _ts(d), "open": round(float(r.o), 4), "high": round(float(r.h), 4), "low": round(float(r.l), 4),
                "close": round(float(r.c), 4)} for d, r in zip(days, df.itertuples())]
    out = {"ok": True, "sid": sid, "sym": sym, "info": info, "candles": candles, "markers": sorted(markers, key=lambda m: m["time"]),
           "events": list(reversed(evs)), "trips": trips, "live": list(reversed(live)), "notes": notes,
           "tv": tv_url(drawn_on), "tv_symbol": TV.get(drawn_on, drawn_on), "drawn_on": drawn_on, "first": first, "last": days[-1] if days else None,
           "backtest_from": res["data"]["from"], "source": md.source()}
    with _lock:
        if len(_cache) > 200:
            _cache.clear()
        _cache[key] = out
    return {**out, "symbols": syms}
