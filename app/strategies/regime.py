"""Regime strategy: hold a leveraged ETF according to the STATE of an index, gold when the trend is off.
Research: "Strategy to beat QQQ" (F = QLD regime, U = 2x semis regime), AI x Alpaca bot/regime.py.

After each US close, from the signal index's daily closes:
  SMA_long, SMA_short  simple averages (default 200 / 50 days)
  vol                  standard deviation of the last N daily log returns, annualised (× √252)
  state "2x"   close > SMA_long, SMA_short > SMA_long, vol < gate   → calm_weight (100%) in the ETF
        "0.5x" close > SMA_long, SMA_short > SMA_long, vol ≥ gate   → jumpy_weight (25%) ETF, rest T-bills
        "1x"   close > SMA_long, SMA_short ≤ SMA_long               → unconfirmed_weight (50%) ETF, rest T-bills
        "off"  close ≤ SMA_long                                      → 100% gold ETF (GLD)
Orders go out from the next market open (the research filled at the next open), split into lots.
"""
from __future__ import annotations

import math
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import marketdata as md
from .. import markethours as mh
from .base import StrategyBase, register

NY = ZoneInfo("America/New_York")
STATE_TEXT = {"2x": "trend on, confirmed, calm", "0.5x": "trend on, confirmed, jumpy", "1x": "trend on, not confirmed",
              "off": "trend off"}
STATE_COLOR = {"2x": "#5B8DEF", "1x": "#34508A", "0.5x": "#F5C76B", "off": "#B9852C"}
RANGE_DAYS = {"3M": 63, "8M": 168, "1Y": 252, "2Y": 504, "ALL": 4000}
TV = {"QQQ": "NASDAQ:QQQ", "SMH": "NASDAQ:SMH", "QLD": "AMEX:QLD", "USD": "AMEX:USD", "TQQQ": "NASDAQ:TQQQ",
      "SOXL": "AMEX:SOXL", "SPY": "AMEX:SPY", "SSO": "AMEX:SSO", "UPRO": "AMEX:UPRO"}


def tv_url(sym):
    s = TV.get(sym, sym)
    return "https://www.tradingview.com/chart/?symbol=" + s.replace(":", "%3A")


@register
class RegimeStrategy(StrategyBase):
    type = "regime"
    label = "Regime (index state → leveraged ETF)"
    family = "regime"
    timeframe = "1D"
    description = "Daily: holds a leveraged ETF by the state of an index (SMA200, SMA50, volatility gate); gold when the trend is off."
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the state from", "kind": "symbol", "default": "QQQ", "group": "Symbols",
         "help": "Index ETF, daily closes (e.g. QQQ, SMH, SPY)"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "QLD", "group": "Symbols",
         "help": "Leveraged ETF held while the trend is on (e.g. QLD, USD, SSO)"},
        {"key": "off_symbol", "label": "When the trend is off, hold", "kind": "symbol", "default": "GLD", "group": "Symbols"},
        {"key": "cash_symbol", "label": "Cash part goes to", "kind": "symbol", "default": "BIL", "group": "Symbols"},
        {"key": "ma_days", "label": "Long average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Rules"},
        {"key": "confirm_days", "label": "Confirm average (days)", "kind": "int", "default": 50, "min": 5, "max": 200, "group": "Rules"},
        {"key": "vol_days", "label": "Volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 120, "group": "Rules"},
        {"key": "vol_gate_pct", "label": "Volatility gate %", "kind": "float", "default": 30.0, "min": 5, "max": 150, "group": "Rules"},
        {"key": "calm_weight", "label": "Calm weight % (2x)", "kind": "float", "default": 100.0, "min": 0, "max": 100, "group": "Weights"},
        {"key": "jumpy_weight", "label": "Jumpy weight % (0.5x)", "kind": "float", "default": 25.0, "min": 0, "max": 100, "group": "Weights"},
        {"key": "unconfirmed_weight", "label": "Unconfirmed weight % (1x)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Weights"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between state changes, trade only when a holding drifts this far from its target"},
    ]

    def data_needs(self):
        p = self.params
        return [(p["signal"], "1d"), (p["trade"], "1d")]

    def trade_symbols(self):
        p = self.params
        return [s for s in (p["trade"], p["cash_symbol"], p["off_symbol"]) if s]

    def benchmark_symbol(self):
        return self.params["trade"]

    def cash_target(self):
        c = self.params["cash_symbol"]
        return {c: round(1 - self.buffer(), 4)} if c else {}

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        df = md.daily_closed(p["signal"], now)
        if len(df) < p["ma_days"] + 2:
            raise md.DataError(f"Need {p['ma_days'] + 2} daily closes of {p['signal']}, have {len(df)}")
        c = df["c"].astype(float)
        out = pd.DataFrame(index=df.index)
        out["o"], out["h"], out["l"], out["c"] = df["o"], df["h"], df["l"], c
        out["sma_long"] = c.rolling(p["ma_days"]).mean()
        out["sma_short"] = c.rolling(p["confirm_days"]).mean()
        out["vol"] = np.log(c).diff().rolling(p["vol_days"]).std(ddof=1) * math.sqrt(252)
        gate = p["vol_gate_pct"] / 100
        st = []
        for cl, sl, ss, v in zip(c.values, out["sma_long"].values, out["sma_short"].values, out["vol"].values):
            if np.isnan(sl) or np.isnan(v):
                st.append("")
            elif cl <= sl:
                st.append("off")
            elif ss <= sl:
                st.append("1x")
            elif v < gate:
                st.append("2x")
            else:
                st.append("0.5x")
        out["state"] = st
        out["weight"] = [self.weight(s) for s in st]
        return out

    def weight(self, state):
        p = self.params
        return {"2x": p["calm_weight"], "0.5x": p["jumpy_weight"], "1x": p["unconfirmed_weight"], "off": 0.0}.get(state, 0.0) / 100

    def is_buy_signal(self, sig: dict) -> bool:
        """For a regime a buy is a state change that raises the leveraged ETF's weight (off → 1x, 0.5x → 2x …)."""
        if sig.get("kind") != "STATE" or not sig.get("from_state"):
            return False
        return self.weight(sig.get("to_state")) > self.weight(sig.get("from_state"))

    def target_for(self, state):
        p, buf = self.params, self.buffer()
        if state == "off":
            return {p["off_symbol"]: round(1 - buf, 4)}
        w = self.weight(state)
        t = {}
        if w > 0:
            t[p["trade"]] = round(w if w < 1 else 1 - buf, 4)
        rest = round(1 - buf - (w if w < 1 else 1 - buf), 4)
        if rest > 0.0005 and p["cash_symbol"]:
            t[p["cash_symbol"]] = rest
        return t

    @staticmethod
    def close_ts(idx_ts) -> int:
        """A daily bar (dated at 00:00 UTC) closes at 16:00 New York that day."""
        d = pd.Timestamp(idx_ts).date()
        return int(datetime.combine(d, dtime(16, 0), NY).timestamp())

    def next_check(self, now):
        d = now.astimezone(NY).date()
        for k in range(0, 10):
            b = mh.session_bounds(d + timedelta(days=k), "CORE")
            if b:
                t = b[1] + timedelta(minutes=10)
                if t > now:
                    return int(t.timestamp())
        return None

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state = last["state"]
        k = len(fr) - 1
        while k > 0 and fr["state"].iloc[k - 1] == state:
            k -= 1
        gate = p["vol_gate_pct"]
        pct = (last["c"] / last["sma_long"] - 1) * 100
        checks = [
            {"k": f"{p['signal']} vs SMA{p['ma_days']}", "v": f"{last['c']:,.2f} vs {last['sma_long']:,.2f} · {pct:+.1f}%",
             "cls": "up" if pct > 0 else "dn", "h": f"Trend turns off if {p['signal']} closes ≤ {last['sma_long']:,.2f}"},
            {"k": f"SMA{p['confirm_days']} vs SMA{p['ma_days']}",
             "v": f"{last['sma_short']:,.2f} {'>' if last['sma_short'] > last['sma_long'] else '≤'} {last['sma_long']:,.2f}",
             "cls": "up" if last["sma_short"] > last["sma_long"] else "dn",
             "h": "Uptrend confirmed" if last["sma_short"] > last["sma_long"] else "Not confirmed yet"},
            {"k": f"{p['vol_days']}-day volatility vs gate", "v": f"{last['vol'] * 100:.1f}% {'<' if last['vol'] * 100 < gate else '≥'} {gate:g}%",
             "cls": "up" if last["vol"] * 100 < gate else "dn",
             "h": "Calm" if last["vol"] * 100 < gate else f"Jumpy: only {p['jumpy_weight']:g}% in {p['trade']}"},
        ]
        hist = []
        sts = fr["state"].values
        for i in range(max(1, len(fr) - 500), len(fr)):
            if sts[i] != sts[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "STATE", "from": sts[i - 1], "to": sts[i],
                             "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "sma_long": float(r["sma_long"]),
                             "sma_short": float(r["sma_short"]), "vol": float(r["vol"]), "state": r["state"],
                             "changed": bool(i > 0 and sts[i] != sts[i - 1]), "from": sts[i - 1] if i > 0 else None})
        target = self.target_for(state)
        return {"ok": True, "state": state, "label": f"{state} · {self.position_text(target)}", "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"close": float(last["c"]), "sma_long": float(last["sma_long"]), "sma_short": float(last["sma_short"]),
                           "vol": float(last["vol"]), "gate": gate / 100, "state_text": STATE_TEXT[state], "log": log_rows,
                           "date": str(fr.index[-1].date())}}

    def why(self, fr, i):
        p = self.params
        a, z = fr["state"].iloc[i - 1], fr["state"].iloc[i]
        if a == "off" or z == "off":
            return f"{p['signal']} closed {'below' if z == 'off' else 'above'} SMA{p['ma_days']}"
        if (a == "1x") != (z == "1x"):
            return f"SMA{p['confirm_days']} crossed {'below' if z == '1x' else 'above'} SMA{p['ma_days']}"
        v = fr["vol"].iloc[i] * 100
        return f"vol{p['vol_days']} {v:.1f}% {'≥' if v >= p['vol_gate_pct'] else '<'} {p['vol_gate_pct']:g}%"

    @staticmethod
    def position_text(target):
        return " + ".join(f"{w * 100:.0f}% {s}" for s, w in sorted(target.items(), key=lambda x: -x[1])) or "cash"

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now)
        nd = RANGE_DAYS.get(rng, 168)
        fr = fr.iloc[-nd:]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def bar(df, i):
            return {"time": t[i], "open": round(float(df["o"].iloc[i]), 4), "high": round(float(df["h"].iloc[i]), 4),
                    "low": round(float(df["l"].iloc[i]), 4), "close": round(float(df["c"].iloc[i]), 4)}

        def ln(col, mult=1.0, digits=4):
            return [{"time": t[i], "value": round(float(v) * mult, digits)} if not np.isnan(v) else {"time": t[i]}
                    for i, v in enumerate(fr[col].values)]

        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — the state is read from this chart",
               "candles": [bar(fr, i) for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['ma_days']}", "color": "#FF9800", "width": 2, "data": ln("sma_long")},
                         {"name": f"SMA {p['confirm_days']}", "color": "#2962FF", "width": 2, "data": ln("sma_short")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(fr["state"].values)],
               "panes": [{"id": "vol", "title": f"Volatility {p['vol_days']}d (annualised, %)", "height": 110,
                          "lines": [{"name": "Volatility", "color": "#B084F5", "width": 2, "data": ln("vol", 100, 2)}],
                          "hlines": [{"value": p["vol_gate_pct"], "label": f"gate {p['vol_gate_pct']:g}%"}]}],
               "markers": [], "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        charts = [sig]
        tr = md.daily_closed(p["trade"], now)
        tr = tr[tr.index.isin(fr.index)]
        if len(tr):
            tt = [int(pd.Timestamp(x).timestamp()) for x in tr.index]
            w = fr["weight"].reindex(tr.index).values
            stv = fr["state"].reindex(tr.index).values
            markers = []
            for i in range(1, len(tr)):
                if stv[i] != stv[i - 1] and stv[i - 1]:
                    up = w[i] > w[i - 1]
                    markers.append({"time": tt[i], "position": "belowBar" if up else "aboveBar",
                                    "color": "#2962FF" if up else "#E040FB", "shape": "arrowUp" if up else "arrowDown",
                                    "text": "→ " + ("Off · " + p["off_symbol"] if stv[i] == "off" else stv[i])})
            charts.append({"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — what the bot buys and sells",
                           "candles": [{"time": tt[i], "open": round(float(tr["o"].iloc[i]), 4), "high": round(float(tr["h"].iloc[i]), 4),
                                        "low": round(float(tr["l"].iloc[i]), 4), "close": round(float(tr["c"].iloc[i]), 4)} for i in range(len(tr))],
                           "lines": [], "markers": markers,
                           "panes": [{"id": "weight", "title": f"Money in {p['trade']} (%)", "height": 90, "step": True,
                                      "lines": [{"name": f"% in {p['trade']}", "color": self.color, "width": 2, "area": True,
                                                 "data": [{"time": tt[i], "value": round(float(w[i]) * 100, 1)} for i in range(len(tr))]}],
                                      "hlines": []}],
                           "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close, read {p['signal']}'s daily close, SMA{p['ma_days']}, SMA{p['confirm_days']} and {p['vol_days']}-day volatility.",
            f"2x: close > SMA{p['ma_days']}, SMA{p['confirm_days']} > SMA{p['ma_days']} and volatility < {p['vol_gate_pct']:g}% → {p['calm_weight']:g}% {p['trade']}.",
            f"0.5x: same but volatility ≥ {p['vol_gate_pct']:g}% → {p['jumpy_weight']:g}% {p['trade']}, rest {p['cash_symbol']}.",
            f"1x: close > SMA{p['ma_days']} but SMA{p['confirm_days']} ≤ SMA{p['ma_days']} → {p['unconfirmed_weight']:g}% {p['trade']}, rest {p['cash_symbol']}.",
            f"Off: close ≤ SMA{p['ma_days']} → 100% {p['off_symbol']}.",
            "Orders start at the next market open, split into lots. Between state changes the bot trades only when a holding drifts "
            f"more than {p['rebalance_band_pct']:g}% from target."],
            "flow": f"{p['signal']} daily → {p['trade']} · {p['cash_symbol']} · {p['off_symbol']}",
            "tv": f'"Moving Average" lengths {p["ma_days"]} and {p["confirm_days"]} on {p["signal"]} daily; '
                  f'"Historical Volatility" length {p["vol_days"]}',
            "rule": f"{p['signal']} vs SMA{p['ma_days']} / SMA{p['confirm_days']}, {p['vol_days']}-day vol gate {p['vol_gate_pct']:g}% → "
                    f"{p['trade']}, {p['cash_symbol']} or {p['off_symbol']}"}
