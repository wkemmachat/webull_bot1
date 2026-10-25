"""C2-7 Momentum: the 7 strongest of the 12 largest Nasdaq-100 stocks, only while the QQQ signal is on.
Research: "Research on single Stock Nasdaq" (C2-7 Momentum with 50/50 parking; 2x = each stock through its 2x ETF).

Daily after the US close (QQQ daily bars):
  trend   Supertrend(ATR 14, x4) up AND QQQ close > SMA200
  dip     opens when RSI(2) < 5, closes on the first close above SMA5
  signal  trend OR dip                                   → in;  otherwise out
Every Friday after the close: rank the Nasdaq-100 by market cap; of the 12 largest, the 7 with the best 6-month
(126 trading days) total return are the buy list for the next week.
Next open: out → sell everything, park 50% gold ETF + 50% T-bill ETF.  In → sell names no longer on the list, buy the
missing names with equity / 7 each (largest first, limited to the cash), park what is left. No top-ups or trims.
2x: each stock is held through its 2x single-stock ETF when one exists (NVDL, AAPU, …), else the stock itself.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from .. import basket
from .. import indicators as I
from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "out": "#4A5263"}
ETF_2X = ("NVDA:NVDL, AAPL:AAPU, GOOGL:GGLL, MSFT:MSFU, AMZN:AMZU, META:METU, AVGO:AVGX, TSLA:TSLL, MU:MUU, AMD:AMUU, "
          "NFLX:NFXL, PLTR:PLTU, ORCL:ORCX")


def signal_states(o, h, l, c, atr=14, mult=4.0, ma=200, rsi_len=2, rsi_buy=5.0, exit_ma=5):
    """The research's QQQ signal bar by bar. Returns (state array 'trend'|'dip'|'out'|'', supertrend dict, sma, sma_exit, rsi)."""
    c = np.asarray(c, dtype=float)
    st = I.supertrend(h, l, c, atr, mult)
    sl, se, r = I.sma(c, ma), I.sma(c, exit_ma), I.rsi(c, rsi_len)
    out = np.array([""] * len(c), dtype=object)
    dip = False
    for i in range(len(c)):
        if not np.isnan(se[i]) and dip and c[i] > se[i]:
            dip = False
        elif not dip and not np.isnan(r[i]) and r[i] < rsi_buy:
            dip = True
        if np.isnan(sl[i]) or np.isnan(st["atr"][i]):
            continue
        trend = bool(st["up"][i]) and c[i] > sl[i]
        out[i] = "trend" if trend else ("dip" if dip else "out")
    return out, st, sl, se, r


@register
class MomentumBasket(RegimeStrategy):
    type = "momentum_basket"
    label = "Momentum basket (strongest of the largest Nasdaq-100 stocks, QQQ on/off)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily QQQ on/off signal; weekly the strongest N of the largest Nasdaq-100 stocks by 6-month return, "
                   "equal money each, optionally through 2x single-stock ETFs. Gold + T-bills when off.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the on/off signal from", "kind": "symbol", "default": "QQQ", "group": "Signal"},
        {"key": "st_atr", "label": "Supertrend ATR length", "kind": "int", "default": 14, "min": 2, "max": 100, "group": "Signal"},
        {"key": "st_mult", "label": "Supertrend multiplier", "kind": "float", "default": 4.0, "min": 0.5, "max": 10, "group": "Signal"},
        {"key": "ma_days", "label": "Trend average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Signal"},
        {"key": "rsi_len", "label": "RSI length (dips)", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "Signal"},
        {"key": "rsi_buy", "label": "Dip trade when RSI is below", "kind": "float", "default": 5.0, "min": 1, "max": 30, "group": "Signal"},
        {"key": "exit_ma", "label": "Dip ends on a close above SMA (days)", "kind": "int", "default": 5, "min": 2, "max": 50, "group": "Signal"},
        {"key": "pool", "label": "Pick from the largest (stocks)", "kind": "int", "default": 12, "min": 3, "max": 20, "group": "Rules",
         "help": "Weekly Nasdaq-100 market-cap ranking"},
        {"key": "hold", "label": "Hold the strongest (stocks)", "kind": "int", "default": 7, "min": 1, "max": 20, "group": "Rules"},
        {"key": "lookback", "label": "Momentum lookback (trading days)", "kind": "int", "default": 126, "min": 20, "max": 260, "group": "Rules",
         "help": "126 ≈ 6 months (the research: 3 or 12 months were weaker)"},
        {"key": "leverage", "label": "Leverage", "kind": "select", "default": "1x", "options": ["1x", "2x"], "group": "Rules",
         "help": "2x: hold each stock through its 2x single-stock ETF when one exists"},
        {"key": "etf_map", "label": "2x ETFs (stock:ETF, …)", "kind": "text", "default": ETF_2X, "group": "Symbols",
         "help": "Stocks not listed are held 1x. Webull must allow each ETF (Go-live → Test trade)"},
        {"key": "gold_etf", "label": "Off: gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols"},
        {"key": "cash_symbol", "label": "Off: T-bill ETF", "kind": "symbol", "default": "SGOV", "group": "Symbols"},
        {"key": "gold_pct", "label": "Off: share in gold %", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Symbols",
         "help": "The rest goes to the T-bill ETF"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
    ]

    # ---------------------------------------------------------------- symbols
    def etf_map(self) -> dict:
        out = {}
        for part in str(self.params.get("etf_map") or "").replace(";", ",").split(","):
            if ":" in part:
                a, b = (x.strip().upper() for x in part.split(":", 1))
                if a and b:
                    out[a] = b
        return out

    def inst(self, stock):
        return self.etf_map().get(stock, stock) if self.params["leverage"] == "2x" else stock

    def fallback_for(self, sym):
        rev = {v: k for k, v in self.etf_map().items()}
        return rev.get(sym)

    def parking(self) -> dict:
        p, buf = self.params, self.buffer()
        g = max(0.0, min(1.0, p["gold_pct"] / 100))
        out = {}
        if g > 0 and p["gold_etf"]:
            out[p["gold_etf"]] = round((1 - buf) * g, 4)
        if g < 1 and p["cash_symbol"]:
            out[p["cash_symbol"]] = round((1 - buf) * (1 - g), 4)
        return out

    def cash_target(self):
        return self.parking()

    def current_list(self, now=None):
        day = (now or md.now_utc()).astimezone(NY).date()
        p = self.params
        key = f"mlist:{day}:{p['pool']}:{p['hold']}:{p['lookback']}"
        return basket._cached(key, lambda: basket.momentum_list(day, p["pool"], p["hold"], p["lookback"]), ttl=3 * 3600)

    def data_needs(self):
        return [(self.params["signal"], "1d")]

    def trade_symbols(self):
        try:
            _, picks, _ = self.current_list()
        except Exception:
            picks = []
        return [self.inst(s) for s in picks] + list(self.parking())

    def benchmark_symbol(self):
        return "QLD" if self.params["leverage"] == "2x" else self.params["signal"]

    def rebalance_band(self):
        return 9.99                                  # never trim or top up (research rule); trades only on list/signal changes

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state, picks=None):
        if state in ("trend", "dip") and picks:
            w = round((1 - self.buffer()) / max(1, self.params["hold"]), 4)
            t = {}
            for s in picks:
                t[self.inst(s)] = round(t.get(self.inst(s), 0) + w, 4)
            rest = round(1 - self.buffer() - sum(t.values()), 4)
            if rest > 0.0005:                         # fewer names than `hold` (data missing): park the rest
                for k, v in self.parking().items():
                    t[k] = round(t.get(k, 0) + v * rest / max(1e-9, 1 - self.buffer()), 4)
            return t
        return self.parking()

    def adjust_target(self, target, weights):
        """No top-ups: names already held keep their weight; missing names get equity / hold each (largest first, limited
        to what is left); the rest is parked. Weights are shares of the strategy's money."""
        park = self.parking()
        stocks = [s for s in target if s not in park]
        if not stocks:
            return target
        cap = 1 - self.buffer()
        out = {s: round(weights[s], 4) for s in stocks if weights.get(s, 0) > 0.0005}
        left = cap - sum(out.values())
        each = cap / max(1, self.params["hold"])
        for s in stocks:                               # target keeps the list order: largest first
            if s in out:
                continue
            w = min(each, max(0.0, left))
            if w > 0.0005:
                out[s] = round(w, 4)
                left -= w
        if left > 0.0005:
            tot = sum(park.values()) or 1
            for k, v in park.items():
                out[k] = round(out.get(k, 0) + left * v / tot, 4)
        return out

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        df = md.daily_closed(p["signal"], now)
        if len(df) < p["ma_days"] + 2:
            raise md.DataError(f"Need {p['ma_days'] + 2} daily closes of {p['signal']}, have {len(df)}")
        st, sup, sl, se, r = signal_states(df["o"].values, df["h"].values, df["l"].values, df["c"].values, p["st_atr"], p["st_mult"],
                                           p["ma_days"], p["rsi_len"], p["rsi_buy"], p["exit_ma"])
        out = pd.DataFrame(index=df.index)
        out["o"], out["h"], out["l"], out["c"] = df["o"], df["h"], df["l"], df["c"].astype(float)
        out["sma_long"], out["sma_exit"], out["rsi"], out["state"] = sl, se, r, st
        out["st_line"], out["st_up"] = sup["line"], sup["up"]
        out["weight"] = [self.weight(s) for s in st]
        return out

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        if h["kind"] == "LIST":
            return f"LIST · {self.name}\n{h['text']}"
        word = "BUY" if h["kind"] == "BUY" else "SELL"
        to = f"{self.params['hold']} stocks" + (" (2x ETFs)" if self.params["leverage"] == "2x" else "") if word == "BUY" else \
            " + ".join(self.parking())
        return f"{word} · {self.name}\n{h['text']}\nMoves to {to}"

    def why(self, fr, i):
        p = self.params
        a, z = fr["state"].iloc[i - 1], fr["state"].iloc[i]
        c, sl = fr["c"].iloc[i], fr["sma_long"].iloc[i]
        if z == "trend":
            return f"{p['signal']} trend on: Supertrend up and close {c:,.2f} > SMA{p['ma_days']} {sl:,.2f}"
        if z == "dip":
            return f"Dip trade: RSI({p['rsi_len']}) {fr['rsi'].iloc[i]:.1f} < {p['rsi_buy']:g}"
        if a == "dip":
            return f"Dip ended: close {c:,.2f} > SMA{p['exit_ma']} {fr['sma_exit'].iloc[i]:,.2f}, trend still off"
        return f"{p['signal']} trend off: " + ("Supertrend turned down" if not fr["st_up"].iloc[i] else f"close {c:,.2f} ≤ SMA{p['ma_days']} {sl:,.2f}")

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state = last["state"]
        day = pd.Timestamp(fr.index[-1]).date()
        week, picks, rows = basket.momentum_list(day, p["pool"], p["hold"], p["lookback"])
        if not picks:
            return {"ok": False, "error": "No Nasdaq-100 ranking or stock prices yet"}
        inpos = fr["weight"].values
        k = len(fr) - 1
        while k > 0 and inpos[k - 1] == inpos[k]:
            k -= 1
        hist = []
        sts = fr["state"].values
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if inpos[i] != inpos[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if inpos[i] > inpos[i - 1] else "SELL",
                             "from": sts[i - 1], "to": sts[i], "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        hist += basket._cached(f"mlisthist:{day}:{p['pool']}:{p['hold']}:{p['lookback']}", lambda: self._list_history(day), ttl=6 * 3600)
        hist.sort(key=lambda x: x["t"])
        target = self.target_for(state, picks)
        rsi_v = float(last["rsi"])
        checks = [
            {"k": f"{p['signal']} vs SMA{p['ma_days']}", "v": f"{last['c']:,.2f} vs {last['sma_long']:,.2f} · {(last['c'] / last['sma_long'] - 1) * 100:+.1f}%",
             "cls": "up" if last["c"] > last["sma_long"] else "dn", "h": "Trend needs the close above it"},
            {"k": f"Supertrend({p['st_atr']}, {p['st_mult']:g})", "v": f"{'up' if last['st_up'] else 'down'} · line {last['st_line']:,.2f}",
             "cls": "up" if last["st_up"] else "dn", "h": "Trend needs Supertrend up"},
            {"k": f"RSI({p['rsi_len']})", "v": f"{rsi_v:.1f} {'<' if rsi_v < p['rsi_buy'] else '≥'} {p['rsi_buy']:g}",
             "cls": "warn" if rsi_v < p["rsi_buy"] else "", "h": "A dip trade starts below " + f"{p['rsi_buy']:g}"},
            {"k": "This week's list", "v": ", ".join(picks), "h": f"Ranking of {week} · strongest {p['hold']} of the largest {p['pool']}"},
        ]
        tiles = [{"k": "trend", "title": "In · trend", "text": f"Supertrend up and {p['signal']} above SMA{p['ma_days']}",
                  "hold": f"{p['hold']} stocks" + (" via 2x ETFs" if p["leverage"] == "2x" else ""), "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip trade", "text": f"RSI({p['rsi_len']}) < {p['rsi_buy']:g}; ends on a close above SMA{p['exit_ma']}",
                  "hold": f"{p['hold']} stocks" + (" via 2x ETFs" if p["leverage"] == "2x" else ""), "color": STATE_COLOR["dip"]},
                 {"k": "out", "title": "Out", "text": "Trend off and no dip trade",
                  "hold": " + ".join(f"{v * 100:.0f}% {s}" for s, v in self.parking().items()), "color": STATE_COLOR["out"]}]
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "sma_long": float(r["sma_long"]),
                             "st_line": float(r["st_line"]), "rsi": float(r["rsi"]), "state": r["state"],
                             "changed": bool(i > 0 and inpos[i] != inpos[i - 1]), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["signal"], "fmt": "n2"}, {"k": "sma_long", "label": f"SMA{p['ma_days']}", "fmt": "n2"},
                    {"k": "st_line", "label": "Supertrend", "fmt": "n2"}, {"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"}]
        table = [{**r, "inst": self.inst(r["symbol"]) if r["picked"] else ""} for r in rows]
        lev = " (2x ETFs)" if p["leverage"] == "2x" else ""
        label = {"trend": f"IN · {len(picks)} stocks{lev}", "dip": f"IN · {len(picks)} stocks{lev} (dip trade)",
                 "out": "OUT · " + " + ".join(self.parking())}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(day), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "title": "Signal · decided after each US close", "basket": {"week": str(week), "rows": table,
                                                                                         "picks": picks, "leverage": p["leverage"]}}}

    def _list_history(self, day):
        p, out, prev = self.params, [], None
        for w in [x for x in basket.weeks() if x <= day][-27:]:
            _, pk, _ = basket.momentum_list(w, p["pool"], p["hold"], p["lookback"])
            if prev is not None and set(pk) != set(prev):
                gone, new = sorted(set(prev) - set(pk)), sorted(set(pk) - set(prev))
                t = int(pd.Timestamp(f"{w} 16:00", tz=NY).timestamp())
                out.append({"t": t, "kind": "LIST", "from": "list", "to": "list", "price": 0.0,
                            "text": f"Week of {w}: out {', '.join(gone) or '—'} · in {', '.join(new) or '—'}"})
            prev = pk
        return out

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, mask=None, digits=4):
            v = fr[col].values
            return [{"time": t[i], "value": round(float(v[i]), digits)} if not np.isnan(v[i]) and (mask is None or mask[i]) else {"time": t[i]}
                    for i in range(len(fr))]

        up = fr["st_up"].values.astype(bool)
        w, stv = fr["weight"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if stv[i - 1] and w[i] != w[i - 1]:
                b = w[i] > w[i - 1]
                markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                                "shape": "arrowUp" if b else "arrowDown", "text": ("In · dip" if stv[i] == "dip" else "In") if b else "Out"})
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — on/off is read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['ma_days']}", "color": "#FF9800", "width": 2, "data": ln("sma_long")},
                         {"name": f"Supertrend {p['st_atr']} {p['st_mult']:g} (up)", "color": "#26A69A", "width": 1, "data": ln("st_line", up)},
                         {"name": f"Supertrend {p['st_atr']} {p['st_mult']:g} (down)", "color": "#EF5350", "width": 1, "data": ln("st_line", ~up),
                          "legend": False}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": [{"id": "rsi", "title": f"RSI({p['rsi_len']})", "height": 110,
                          "lines": [{"name": "RSI", "color": "#B084F5", "width": 2, "data": ln("rsi", digits=2)}],
                          "hlines": [{"value": p["rsi_buy"], "label": f"dip < {p['rsi_buy']:g}"}]}],
               "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        return {"charts": [sig], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        lev = p["leverage"] == "2x"
        return {"rules": [
            f"Daily after the US close: {p['signal']} signal = (Supertrend({p['st_atr']}, {p['st_mult']:g}) up AND close > SMA{p['ma_days']}) "
            f"OR a dip trade (opens when RSI({p['rsi_len']}) < {p['rsi_buy']:g}, ends on a close above SMA{p['exit_ma']}).",
            f"Every Friday: rank the Nasdaq-100 by market cap; of the {p['pool']} largest, the {p['hold']} with the best "
            f"{p['lookback']}-day return are next week's list.",
            f"In: hold the list with equal money (1/{p['hold']} each){', each through its 2x ETF when one exists' if lev else ''}; "
            "sell a name when it leaves the list; buy new names with 1/" + str(p["hold"]) + " of the money; no top-ups.",
            "Out: sell everything; " + " + ".join(f"{v * 100:.0f}% {s}" for s, v in self.parking().items()) + ".",
            "Orders start at the next market open, split into lots."],
            "flow": f"{p['signal']} daily + Nasdaq-100 weekly → {p['hold']} of top {p['pool']}{' (2x)' if lev else ''} · {' / '.join(self.parking())}",
            "tv": f'"Supertrend" (ATR {p["st_atr"]}, factor {p["st_mult"]:g}), "Moving Average" {p["ma_days"]} and {p["exit_ma"]}, '
                  f'"Relative Strength Index" length {p["rsi_len"]} on {p["signal"]} daily',
            "rule": f"{p['hold']} strongest of the {p['pool']} largest Nasdaq-100 stocks{' via 2x ETFs' if lev else ''} while "
                    f"{p['signal']} trend (Supertrend + SMA{p['ma_days']}) or RSI dip is on; else gold + T-bills"}

    def params_key(self):
        return hashlib.sha1(json.dumps(self.params, sort_keys=True).encode()).hexdigest()[:10]
