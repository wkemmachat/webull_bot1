"""Trend + bear-dip: hold a leveraged ETF while the index is above its long average; below it, only buy short,
sharp RSI(2) dips and sell them on the first bounce. Research: "ETF Strategy Lab 2026-10-23" (QLD + Trend + bear-dip,
code/choose.py `tbd_pos` / `run_tbd`): signal QQQ, trade QLD, T-bills when out; signal on the close, fill next open.

After each US close, from the signal index's daily closes:
  trend   close > SMA(ma_days)                                   → in (100% ETF)
  dip     a dip trade opens when close ≤ SMA(ma_days) and RSI(rsi_len) < rsi_buy,
          and closes on the first close above SMA(exit_ma)        → in while open
  out     neither                                                 → cash ETF (BIL)
Optional volatility filter (vol_gate_q > 0, "Trend + bear-dip + Vol", ETF Strategy Lab v3 30 Oct 2026, code/v3_tbdvol.py):
the trend counts only while the index is calm, i.e. its 20-day standard deviation of daily changes is below the
vol_gate_q-th percentile of the same number over the last 252 days (today included). Above the average but jumpy
→ "volatile" (out, unless a dip trade is still open). Dip trades are not filtered.
Orders go out from the next market open, split into lots (like the regimes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "volatile": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"trend": "above the long average", "dip": "bear-market dip trade", "volatile": "above the average but jumpy · out",
              "out": "out · in T-bills"}


def vol_gate(close, q_pct=80.0, days=20, lookback=252):
    """(calm flags, today's volatility, its threshold). calm = the `days`-day standard deviation of daily changes is below
    the q_pct-th percentile of that number over the last `lookback` days (today included; pandas' linear percentile).
    Days before enough history: NaN volatility, not calm."""
    c = pd.Series(np.asarray(close, dtype=float))
    v = c.pct_change().rolling(days).std()
    thr = v.rolling(lookback).quantile(q_pct / 100.0)
    calm = (v < thr).values
    return calm, v.values, thr.values


def positions(close, ma=200, rsi_len=2, rsi_buy=5.0, exit_ma=5, vol_q=0.0, vol_days=20):
    """The research rule, bar by bar. Returns (state array, sma_long, sma_exit, rsi, vol, vol threshold).
    vol_q = 0: no volatility filter (the original Trend + bear-dip)."""
    c = np.asarray(close, dtype=float)
    sl, se, r = I.sma(c, ma), I.sma(c, exit_ma), I.rsi(c, rsi_len)
    if vol_q and vol_q > 0:
        calm, vol, thr = vol_gate(c, vol_q, vol_days)
    else:
        calm, vol, thr = np.ones(len(c), dtype=bool), np.full(len(c), np.nan), np.full(len(c), np.nan)
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
        elif up and calm[i]:
            st[i] = "trend"
        elif dip_on:
            st[i] = "dip"
        else:
            st[i] = "volatile" if up else "out"
    return st, sl, se, r, vol, thr


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
        {"key": "gold_share_pct", "label": "Gold share when out (%)", "kind": "float", "default": 0.0, "min": 0, "max": 100,
         "group": "Symbols",
         "help": "Part of the parked money held in the gold ETF instead (50 = half gold, half T-bills; 0 = all T-bills, as before)"},
        {"key": "gold_symbol", "label": "Gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols",
         "help": "Used only when the gold share is above 0"},
        {"key": "ma_days", "label": "Trend average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Rules"},
        {"key": "rsi_len", "label": "RSI length (dips)", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "Rules"},
        {"key": "rsi_buy", "label": "Buy a dip when RSI is below", "kind": "float", "default": 5.0, "min": 1, "max": 30, "group": "Rules"},
        {"key": "exit_ma", "label": "Sell the dip on a close above SMA (days)", "kind": "int", "default": 5, "min": 2, "max": 50,
         "group": "Rules"},
        {"key": "vol_gate_q", "label": "Volatility filter: percentile (0 = off)", "kind": "float", "default": 0.0, "min": 0, "max": 99,
         "group": "Rules",
         "help": "Hold the trend only while the index's volatility is below this percentile of its last year (80 = the research's "
                 "Trend + bear-dip + Vol). Dip trades are not filtered."},
        {"key": "vol_days", "label": "Volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Rules",
         "help": "Standard deviation of this many daily changes"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    def trade_symbols(self):
        p = self.params
        return [s for s in (p["trade"], p["cash_symbol"], self.gold_sym()) if s]

    def gold_share(self):
        try:
            return min(max(float(self.params.get("gold_share_pct") or 0), 0.0), 100.0) / 100.0
        except (TypeError, ValueError):
            return 0.0

    def gold_sym(self):
        return (self.params.get("gold_symbol") or "GLD") if self.gold_share() > 0 else ""

    def park_text(self):
        """What the strategy holds when out, e.g. '50% GLD + 50% BIL'."""
        p, g = self.params, self.gold_share()
        cash = p["cash_symbol"] or "cash"
        if g <= 0:
            return cash
        if g >= 1:
            return self.gold_sym()
        return f"{g * 100:g}% {self.gold_sym()} + {(1 - g) * 100:g}% {cash}"

    def frame(self, now) -> pd.DataFrame:
        p = self.params
        df = md.daily_closed(p["signal"], now)
        if len(df) < p["ma_days"] + 2:
            raise md.DataError(f"Need {p['ma_days'] + 2} daily closes of {p['signal']}, have {len(df)}")
        c = df["c"].astype(float)
        st, sl, se, r, vol, thr = positions(c.values, p["ma_days"], p["rsi_len"], p["rsi_buy"], p["exit_ma"],
                                            self.vol_q(), int(p.get("vol_days") or 20))
        out = pd.DataFrame(index=df.index)
        out["o"], out["h"], out["l"], out["c"] = df["o"], df["h"], df["l"], c
        out["sma_long"], out["sma_exit"], out["rsi"], out["state"] = sl, se, r, st
        out["vol"], out["vol_thr"] = vol * 100, thr * 100          # % per day
        out["weight"] = [self.weight(s) for s in st]
        return out

    def vol_q(self):
        try:
            return float(self.params.get("vol_gate_q") or 0)
        except (TypeError, ValueError):
            return 0.0

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state):
        p, buf = self.params, self.buffer()
        if state in ("trend", "dip"):
            return {p["trade"]: round(1 - buf, 4)}
        g, out = self.gold_share(), {}
        if g > 0:
            out[self.gold_sym()] = round((1 - buf) * g, 4)
        if p["cash_symbol"] and g < 1:
            out[p["cash_symbol"]] = round((1 - buf) * (1 - g), 4)
        return out

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        word = "BUY" if h["kind"] == "BUY" else "SELL"
        to = self.params["trade"] if word == "BUY" else self.park_text()
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
        if self.vol_q() > 0:
            vv, vt = float(last["vol"]), float(last["vol_thr"])
            calm = vv < vt
            checks.insert(1, {"k": f"Volatility {int(p.get('vol_days') or 20)}d", "v": f"{vv:.2f}% vs {vt:.2f}% · {'calm' if calm else 'jumpy'}",
                              "cls": "up" if calm else "warn",
                              "h": f"The trend counts only while daily volatility is below the {self.vol_q():g}th percentile of the "
                                   f"last year ({vt:.2f}%)"})
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
                             "vol": float(r["vol"]) if r["vol"] == r["vol"] else None,
                             "vol_thr": float(r["vol_thr"]) if r["vol_thr"] == r["vol_thr"] else None,
                             "changed": bool(i > 0 and inpos[i] != inpos[i - 1]), "from": sts[i - 1] if i > 0 else None})
        target = self.target_for(state)
        tiles = [{"k": "trend", "title": "In · trend", "text": f"{p['signal']} above SMA{p['ma_days']}", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip trade", "text": f"Below SMA{p['ma_days']}, bought on RSI({p['rsi_len']}) < {p['rsi_buy']:g}; "
                  f"sold on a close above SMA{p['exit_ma']}", "hold": f"100% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "out", "title": "Out", "text": f"Below SMA{p['ma_days']}, no dip trade open", "hold": self.park_text() if self.gold_share() > 0 else f"100% {p['cash_symbol'] or 'cash'}",
                  "color": STATE_COLOR["out"]}]
        log_cols = [{"k": "close", "label": p["signal"], "fmt": "n2"}, {"k": "sma_long", "label": f"SMA{p['ma_days']}", "fmt": "n2"},
                    {"k": "sma_exit", "label": f"SMA{p['exit_ma']}", "fmt": "n2"}, {"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"}]
        if self.vol_q() > 0:
            tiles[0]["text"] = f"{p['signal']} above SMA{p['ma_days']} and calm (volatility below its {self.vol_q():g}th percentile)"
            tiles.insert(2, {"k": "volatile", "title": "Out · jumpy", "text": f"Above SMA{p['ma_days']} but volatility above its "
                             f"{self.vol_q():g}th percentile of the last year", "hold": self.park_text() if self.gold_share() > 0 else f"100% {p['cash_symbol'] or 'cash'}",
                             "color": STATE_COLOR["volatile"]})
            log_cols += [{"k": "vol", "label": "Vol %", "fmt": "n2"}, {"k": "vol_thr", "label": f"Vol p{self.vol_q():g} %", "fmt": "n2"}]
        label = {"trend": f"IN · {p['trade']} (trend)", "dip": f"IN · {p['trade']} (dip trade)",
                 "volatile": f"OUT · {self.park_text()} (jumpy)", "out": f"OUT · {self.park_text()}"}[state]
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
            if self.vol_q() > 0 and a == "volatile":
                return f"Calm again: {p['signal']} volatility {fr['vol'].iloc[i]:.2f}% < {fr['vol_thr'].iloc[i]:.2f}%, above SMA{p['ma_days']}"
            return f"{p['signal']} closed above SMA{p['ma_days']} ({c:,.2f} > {sl:,.2f})" + (
                " and calm" if self.vol_q() > 0 else "")
        if z == "volatile":
            return (f"Jumpy: {p['signal']} volatility {fr['vol'].iloc[i]:.2f}% ≥ {fr['vol_thr'].iloc[i]:.2f}% "
                    f"(its {self.vol_q():g}th percentile of the last year)")
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
                          "hlines": [{"value": p["rsi_buy"], "label": f"dip buy < {p['rsi_buy']:g}"}]}]
               + ([{"id": "vol", "title": f"Volatility {int(p.get('vol_days') or 20)}d (% a day)", "height": 110,
                    "lines": [{"name": "Volatility", "color": "#8E6BBF", "width": 2, "data": ln("vol", 3)},
                              {"name": f"{self.vol_q():g}th percentile (1 year)", "color": "#FF9800", "width": 1, "data": ln("vol_thr", 3)}],
                    "hlines": []}] if self.vol_q() > 0 else []),
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
            f"Trend: close > SMA{p['ma_days']} → 100% {p['trade']}." if self.vol_q() <= 0 else
            f"Trend: close > SMA{p['ma_days']} AND calm ({int(p.get('vol_days') or 20)}-day volatility below its {self.vol_q():g}th "
            f"percentile of the last 252 days) → 100% {p['trade']}; above the average but jumpy → out.",
            f"Below SMA{p['ma_days']}: buy a dip when RSI({p['rsi_len']}) < {p['rsi_buy']:g}; sell it on the first close above "
            f"SMA{p['exit_ma']}.",
            (f"Otherwise → {self.park_text()}." if self.gold_share() > 0 else
             f"Otherwise → {p['cash_symbol'] or 'cash'}" + (" (T-bills)." if p['cash_symbol'] else ".")),
            "Orders start at the next market open, split into lots."],
            "flow": f"{p['signal']} daily → {p['trade']} · {' · '.join(x for x in (self.gold_sym(), p['cash_symbol'] or 'cash') if x)}",
            "tv": f'"Moving Average" lengths {p["ma_days"]} and {p["exit_ma"]}, "Relative Strength Index" length {p["rsi_len"]} '
                  f'on {p["signal"]} daily' + (f'; volatility: "Historical Volatility" is annualised, so compare the bot\'s '
                                               f'Volatility pane instead' if self.vol_q() > 0 else ''),
            "rule": f"{p['signal']} > SMA{p['ma_days']}" + (" and calm" if self.vol_q() > 0 else "") +
                    f", or RSI({p['rsi_len']}) < {p['rsi_buy']:g} dips below it (exit > SMA{p['exit_ma']}) "
                    f"→ {p['trade']}, else {self.park_text()}"}

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
        # volatility filter, the long way: sample standard deviation of the last vd daily changes, and its q-th percentile
        # (linear between the two nearest ranks) over the last 252 values, today included
        vq, vd = self.vol_q(), int(p.get("vol_days") or 20)
        calm = [True] * len(c)
        if vq > 0:
            chg = [float("nan")] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
            sd = [float("nan")] * len(c)
            for i in range(vd, len(c)):
                w = chg[i - vd + 1:i + 1]
                m = sum(w) / vd
                sd[i] = (sum((x - m) ** 2 for x in w) / (vd - 1)) ** 0.5
            for i in range(len(c)):
                win = sd[i - 251:i + 1] if i >= 251 else []
                if len(win) < 252 or any(x != x for x in win):
                    calm[i] = False
                    continue
                srt = sorted(win)
                pos = (len(srt) - 1) * vq / 100.0
                lo = int(pos)
                hi = min(lo + 1, len(srt) - 1)
                thr = srt[lo] + (srt[hi] - srt[lo]) * (pos - lo)
                calm[i] = sd[i] < thr
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
            state.append("trend" if (up and calm[i]) else ("dip" if dip else ("volatile" if up else "out")))
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
