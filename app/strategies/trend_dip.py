"""Trend + bear-dip: hold a leveraged ETF while the index is above its long average; below it, only buy short,
sharp RSI(2) dips and sell them on the first bounce. Research: "ETF Strategy Lab 2026-10-23" (QLD + Trend + bear-dip,
code/choose.py `tbd_pos` / `run_tbd`): signal QQQ, trade QLD, T-bills when out; signal on the close, fill next open.

After each US close, from the signal index's daily closes:
  trend   close > SMA(ma_days)                                   → in (100% ETF)
  dip     a dip trade opens when close ≤ SMA(ma_days) and RSI(rsi_len) < rsi_buy,
          and closes on the first close above SMA(exit_ma)        → in while open
  out     neither                                                 → cash ETF (BIL)
Orders go out from the next market open, split into lots (like the regimes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "out": "#4A5263"}
STATE_TEXT = {"trend": "above the long average", "dip": "bear-market dip trade", "out": "out · in T-bills"}


def positions(close, ma=200, rsi_len=2, rsi_buy=5.0, exit_ma=5):
    """The research rule, bar by bar. Returns (state array, sma_long, sma_exit, rsi)."""
    c = np.asarray(close, dtype=float)
    sl, se, r = I.sma(c, ma), I.sma(c, exit_ma), I.rsi(c, rsi_len)
    st = np.array([""] * len(c), dtype=object)
    dip_on = False
    for i in range(len(c)):
        up = (not np.isnan(sl[i])) and c[i] > sl[i]
        # state machine: an open dip trade closes on a close above SMA(exit); one opens on RSI < buy level below the trend
        if dip_on and not np.isnan(se[i]) and c[i] > se[i]:
            dip_on = False
        elif not dip_on and not up and not np.isnan(r[i]) and not np.isnan(sl[i]) and r[i] < rsi_buy:
            dip_on = True
        if np.isnan(sl[i]):
            st[i] = ""
        else:
            st[i] = "trend" if up else ("dip" if dip_on else "out")
    return st, sl, se, r


@register
class TrendDipStrategy(RegimeStrategy):
    type = "trend_dip"
    label = "Trend + bear-dip (index trend → leveraged ETF, RSI dips below it)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a leveraged ETF while the index is above its SMA200; below it, buys only RSI(2) dips and sells "
                   "on the first close above the 5-day average. T-bills when out.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the trend from", "kind": "symbol", "default": "QQQ", "group": "Symbols",
         "help": "Index ETF, daily closes"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "QLD", "group": "Symbols",
         "help": "Leveraged ETF held while in"},
        {"key": "cash_symbol", "label": "When out, hold", "kind": "symbol", "default": "BIL", "group": "Symbols",
         "help": "T-bill ETF (the research earned T-bill interest when out)"},
        {"key": "ma_days", "label": "Trend average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Rules"},
        {"key": "rsi_len", "label": "RSI length (dips)", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "Rules"},
        {"key": "rsi_buy", "label": "Buy a dip when RSI is below", "kind": "float", "default": 5.0, "min": 1, "max": 30, "group": "Rules"},
        {"key": "exit_ma", "label": "Sell the dip on a close above SMA (days)", "kind": "int", "default": 5, "min": 2, "max": 50,
         "group": "Rules"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    def trade_symbols(self):
        p = self.params
        return [s for s in (p["trade"], p["cash_symbol"]) if s]

    def frame(self, now) -> pd.DataFrame:
        p = self.params
        df = md.daily_closed(p["signal"], now)
        if len(df) < p["ma_days"] + 2:
            raise md.DataError(f"Need {p['ma_days'] + 2} daily closes of {p['signal']}, have {len(df)}")
        c = df["c"].astype(float)
        st, sl, se, r = positions(c.values, p["ma_days"], p["rsi_len"], p["rsi_buy"], p["exit_ma"])
        out = pd.DataFrame(index=df.index)
        out["o"], out["h"], out["l"], out["c"] = df["o"], df["h"], df["l"], c
        out["sma_long"], out["sma_exit"], out["rsi"], out["state"] = sl, se, r, st
        out["weight"] = [self.weight(s) for s in st]
        return out

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state):
        p, buf = self.params, self.buffer()
        if state in ("trend", "dip"):
            return {p["trade"]: round(1 - buf, 4)}
        return {p["cash_symbol"]: round(1 - buf, 4)} if p["cash_symbol"] else {}

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        word = "BUY" if h["kind"] == "BUY" else "SELL"
        to = self.params["trade"] if word == "BUY" else self.params["cash_symbol"]
        return f"{word} · {self.name}\n{h['text']}\nMoves to {to}"

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state = last["state"]
        inpos = fr["weight"].values
        k = len(fr) - 1
        while k > 0 and inpos[k - 1] == inpos[k]:
            k -= 1
        pct = (last["c"] / last["sma_long"] - 1) * 100
        rv = float(last["rsi"])
        checks = [
            {"k": f"{p['signal']} vs SMA{p['ma_days']}", "v": f"{last['c']:,.2f} vs {last['sma_long']:,.2f} · {pct:+.1f}%",
             "cls": "up" if pct > 0 else "dn",
             "h": f"In the trend while {p['signal']} closes above {last['sma_long']:,.2f}"},
            {"k": f"RSI({p['rsi_len']})", "v": f"{rv:.1f} {'<' if rv < p['rsi_buy'] else '≥'} {p['rsi_buy']:g}",
             "cls": "warn" if rv < p["rsi_buy"] else "",
             "h": "A dip buy below the trend needs RSI below " + f"{p['rsi_buy']:g}"},
            {"k": f"{p['signal']} vs SMA{p['exit_ma']}", "v": f"{last['c']:,.2f} vs {last['sma_exit']:,.2f}",
             "cls": "up" if last["c"] > last["sma_exit"] else "dn",
             "h": "An open dip trade is sold on a close above this" if state == "dip" else "Exit line for dip trades"},
        ]
        hist = []
        sts = fr["state"].values
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if inpos[i] != inpos[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if inpos[i] > inpos[i - 1] else "SELL",
                             "from": sts[i - 1], "to": sts[i], "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "sma_long": float(r["sma_long"]),
                             "sma_exit": float(r["sma_exit"]), "rsi": float(r["rsi"]), "state": r["state"],
                             "changed": bool(i > 0 and inpos[i] != inpos[i - 1]), "from": sts[i - 1] if i > 0 else None})
        target = self.target_for(state)
        tiles = [{"k": "trend", "title": "In · trend", "text": f"{p['signal']} above SMA{p['ma_days']}", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip trade", "text": f"Below SMA{p['ma_days']}, bought on RSI({p['rsi_len']}) < {p['rsi_buy']:g}; "
                  f"sold on a close above SMA{p['exit_ma']}", "hold": f"100% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "out", "title": "Out", "text": f"Below SMA{p['ma_days']}, no dip trade open", "hold": f"100% {p['cash_symbol']}",
                  "color": STATE_COLOR["out"]}]
        log_cols = [{"k": "close", "label": p["signal"], "fmt": "n2"}, {"k": "sma_long", "label": f"SMA{p['ma_days']}", "fmt": "n2"},
                    {"k": "sma_exit", "label": f"SMA{p['exit_ma']}", "fmt": "n2"}, {"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"}]
        label = {"trend": f"IN · {p['trade']} (trend)", "dip": f"IN · {p['trade']} (dip trade)", "out": f"OUT · {p['cash_symbol']}"}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"close": float(last["c"]), "sma_long": float(last["sma_long"]), "sma_exit": float(last["sma_exit"]),
                           "rsi": rv, "state_text": STATE_TEXT[state], "log": log_rows, "date": str(fr.index[-1].date()),
                           "tiles": tiles, "log_cols": log_cols, "title": "Position · decided after each US close"}}

    def why(self, fr, i):
        p = self.params
        a, z = fr["state"].iloc[i - 1], fr["state"].iloc[i]
        c, sl = fr["c"].iloc[i], fr["sma_long"].iloc[i]
        if z == "trend":
            return f"{p['signal']} closed above SMA{p['ma_days']} ({c:,.2f} > {sl:,.2f})"
        if z == "dip":
            return f"Dip buy: {p['signal']} below SMA{p['ma_days']} and RSI({p['rsi_len']}) {fr['rsi'].iloc[i]:.1f} < {p['rsi_buy']:g}"
        if a == "dip":
            return f"Dip sold: {p['signal']} closed above SMA{p['exit_ma']} ({c:,.2f} > {fr['sma_exit'].iloc[i]:,.2f})"
        return f"{p['signal']} closed below SMA{p['ma_days']} ({c:,.2f} ≤ {sl:,.2f})"

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4):
            return [{"time": t[i], "value": round(float(v), digits)} if not np.isnan(v) else {"time": t[i]}
                    for i, v in enumerate(fr[col].values)]

        w, stv = fr["weight"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if stv[i - 1] and w[i] != w[i - 1]:
                up = w[i] > w[i - 1]
                markers.append({"time": t[i], "position": "belowBar" if up else "aboveBar", "color": "#2962FF" if up else "#E040FB",
                                "shape": "arrowUp" if up else "arrowDown",
                                "text": ("Buy · dip" if stv[i] == "dip" else "Buy · trend") if up else "Sell"})
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — trend and dips are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['ma_days']}", "color": "#FF9800", "width": 2, "data": ln("sma_long")},
                         {"name": f"SMA {p['exit_ma']} (dip exit)", "color": "#2962FF", "width": 1, "data": ln("sma_exit")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": [{"id": "rsi", "title": f"RSI({p['rsi_len']})", "height": 110,
                          "lines": [{"name": "RSI", "color": "#B084F5", "width": 2, "data": ln("rsi", 2)}],
                          "hlines": [{"value": p["rsi_buy"], "label": f"dip buy < {p['rsi_buy']:g}"}]}],
               "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        charts = [sig]
        tr = md.daily_closed(p["trade"], now)
        tr = tr[tr.index.isin(fr.index)]
        if len(tr):
            tt = [int(pd.Timestamp(x).timestamp()) for x in tr.index]
            tw = fr["weight"].reindex(tr.index).values
            tm = [dict(m) for m in markers if m["time"] in set(tt)]
            charts.append({"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — what the bot buys and sells",
                           "candles": [{"time": tt[i], "open": round(float(tr["o"].iloc[i]), 4), "high": round(float(tr["h"].iloc[i]), 4),
                                        "low": round(float(tr["l"].iloc[i]), 4), "close": round(float(tr["c"].iloc[i]), 4)} for i in range(len(tr))],
                           "lines": [], "markers": tm,
                           "panes": [{"id": "weight", "title": f"Money in {p['trade']} (%)", "height": 90, "step": True,
                                      "lines": [{"name": f"% in {p['trade']}", "color": self.color, "width": 2, "area": True,
                                                 "data": [{"time": tt[i], "value": round(float(tw[i]) * 100, 1)} for i in range(len(tr))]}],
                                      "hlines": []}],
                           "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close, read {p['signal']}'s daily close, SMA{p['ma_days']}, SMA{p['exit_ma']} and RSI({p['rsi_len']}).",
            f"Trend: close > SMA{p['ma_days']} → 100% {p['trade']}.",
            f"Below SMA{p['ma_days']}: buy a dip when RSI({p['rsi_len']}) < {p['rsi_buy']:g}; sell it on the first close above "
            f"SMA{p['exit_ma']}.",
            f"Otherwise → {p['cash_symbol']} (T-bills).",
            "Orders start at the next market open, split into lots."],
            "flow": f"{p['signal']} daily → {p['trade']} · {p['cash_symbol']}",
            "tv": f'"Moving Average" lengths {p["ma_days"]} and {p["exit_ma"]}, "Relative Strength Index" length {p["rsi_len"]} '
                  f'on {p["signal"]} daily',
            "rule": f"{p['signal']} > SMA{p['ma_days']}, or RSI({p['rsi_len']}) < {p['rsi_buy']:g} dips below it (exit > SMA{p['exit_ma']}) "
                    f"→ {p['trade']}, else {p['cash_symbol']}"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        p = self.params
        fr = self.frame(now)
        c = fr["c"].values.astype(float).tolist()
        n, ma, ex, buy = p["rsi_len"], p["ma_days"], p["exit_ma"], p["rsi_buy"]
        # RSI written out the long way (Wilder averages seeded with a simple mean), separately from app.indicators
        gains = [0.0] + [max(c[i] - c[i - 1], 0.0) for i in range(1, len(c))]
        losses = [0.0] + [max(c[i - 1] - c[i], 0.0) for i in range(1, len(c))]
        rs = [float("nan")] * len(c)
        ag = sum(gains[1:n + 1]) / n
        al = sum(losses[1:n + 1]) / n
        for i in range(n, len(c)):
            if i > n:
                ag = (ag * (n - 1) + gains[i]) / n
                al = (al * (n - 1) + losses[i]) / n
            rs[i] = 50.0 if (al == 0 and ag == 0) else (100.0 if al == 0 else 100 - 100 / (1 + ag / al))
        # replay the position rule from the recomputed numbers
        state, dip = [], False
        for i in range(len(c)):
            if i < ma - 1:
                state.append("")
                continue
            sl = sum(c[i - ma + 1:i + 1]) / ma
            se = sum(c[i - ex + 1:i + 1]) / ex
            up = c[i] > sl
            if dip and c[i] > se:
                dip = False
            elif not dip and not up and rs[i] == rs[i] and rs[i] < buy:
                dip = True
            state.append("trend" if up else ("dip" if dip else "out"))
        cols = ["Close", f"SMA{ma} · bot", f"SMA{ma} · check", f"RSI({n}) · bot", f"RSI({n}) · check", "State bot / check"]
        out, worst = [], 0.0
        for i in range(len(c) - rows, len(c)):
            sl = sum(c[i - ma + 1:i + 1]) / ma
            a, r_b = float(fr["sma_long"].iloc[i]), float(fr["rsi"].iloc[i])
            diff = max(abs(a - sl) / sl, abs(r_b - rs[i]) / 100)
            same = fr["state"].iloc[i] == state[i]
            if not same:
                diff = max(diff, 1.0)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(fr.index[i]).timestamp()),
                        "vals": [c[i], a, sl, r_b, rs[i], f"{fr['state'].iloc[i]} / {state[i]}"], "ok": diff < 1e-6})
        return cols, out, worst
