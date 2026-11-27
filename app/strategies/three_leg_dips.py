"""Three dip legs with a confirming stock (URAA, the 2x uranium ETF). Research "URAA (2x uranium): 2 best
strategies" rounds 1–4 (27 Nov 2026): Strategy 1++.

After each US close, from daily bars of the signal ETF (URA) and the confirming stock (CCJ), dividends added back; trades at the
next open. The money held is the largest of three legs:
  A  trend dip   SMA(fast) ≥ (1 + a_spread) × SMA(slow) AND above its close mom_days ago AND RSI2 < a_rsi AND confirm RSI2 < c_rsi → 100%
  B  sharp drop  (above SMA(slow) OR above its close mom_days ago) AND drop_days change ≤ −b_drop AND RSI2 < b_rsi AND confirm
                 RSI2 < c_rsi → 100%
  C  crash       drop_days change ≤ −c_drop AND RSI2 < crash_rsi (any trend) → c_pct
Each leg is sold at the open after the signal ETF's first up close (a close above the one before), max_days closes at most.
Before the traded ETF listed (URAA: Jun 2024) the backtest models it as 2 × the signal ETF minus model_cost_pct a year.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .hk_crash import HkCrashStrategy
from .momentum_calm import model_2x
from .quantum_mix import rsi
from .rates_trend_blend import deep_dip
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"a": "#26A69A", "b": "#F5C76B", "c": "#E8875A", "out": "#4A5263"}
STATE_TEXT = {"a": "leg A · dip in a strong uptrend", "b": "leg B · sharp drop in an uptrend", "c": "leg C · crash (half size)", "out": "out · cash"}
TV.update({"URAA": "AMEX:URAA", "URA": "AMEX:URA", "CCJ": "NYSE:CCJ"})


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values
    s = data[p["signal"]]["c"].astype(float)
    fr["c"] = s.reindex(idx).values
    fr["fast"] = s.rolling(int(p["fast"])).mean().reindex(idx).values
    fr["slow"] = s.rolling(int(p["slow"])).mean().reindex(idx).values
    fr["mom"] = ((s / s.shift(int(p["mom_days"])) - 1) * 100).reindex(idx).values
    fr["drop"] = ((s / s.shift(int(p["drop_days"])) - 1) * 100).reindex(idx).values
    fr["rsi2"] = rsi(s, 2).reindex(idx).values
    fr["up"] = (s > s.shift(1)).reindex(idx).values
    fr["c_rsi2"] = rsi(data[p["confirm"]]["c"].astype(float), 2).reindex(idx).values
    ok = ~fr[["fast", "slow", "mom", "drop", "rsi2", "c_rsi2"]].isna().any(axis=1).values
    v = {k: fr[k].values for k in ("c", "fast", "slow", "mom", "drop", "rsi2", "c_rsi2")}
    conf = v["c_rsi2"] < float(p["c_rsi"])
    strong = v["fast"] >= (1 + float(p["a_spread_pct"]) / 100) * v["slow"]
    above = (v["c"] > v["slow"]) | (v["mom"] > 0)
    sa = ok & strong & (v["mom"] > 0) & (v["rsi2"] < float(p["a_rsi"])) & conf
    sb = ok & above & (v["drop"] <= -float(p["b_drop_pct"])) & (v["rsi2"] < float(p["b_rsi"])) & conf
    sc = ok & (v["drop"] <= -float(p["c_drop_pct"])) & (v["rsi2"] < float(p["crash_rsi"]))
    gate = np.ones(len(fr), dtype=bool)
    up = fr["up"].values.astype(bool)
    md_ = int(p["max_days"])
    a, b, c = deep_dip(sa, gate, up, md_), deep_dip(sb, gate, up, md_), deep_dip(sc, gate, up, md_)
    cp = float(p["c_pct"]) / 100
    fr["leg_a"], fr["leg_b"], fr["leg_c"], fr["ok"] = a, b, c, ok
    fr["start_a"], fr["start_b"], fr["start_c"] = sa, sb, sc
    fr["w"] = np.where(a | b, 1.0, np.where(c, cp, 0.0))
    fr["state"] = np.where(~ok, "", np.where(a, "a", np.where(b, "b", np.where(c, "c", "out"))))
    return fr


@register
class ThreeLegDipsStrategy(RegimeStrategy):
    type = "three_leg_dips"
    label = "Three dip legs (trend dip, sharp drop, crash) with a confirming stock"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: buys the 2x ETF only after sharp falls of its 1x ETF — a dip in a strong uptrend, a 4% three-day drop in an "
                   "uptrend (both confirmed by Cameco's RSI2), or an 8% crash at half size — and sells after the first up close.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "URAA", "group": "Symbols"},
        {"key": "signal", "label": "Signals from", "kind": "symbol", "default": "URA", "group": "Symbols"},
        {"key": "confirm", "label": "Confirmed by (RSI2)", "kind": "symbol", "default": "CCJ", "group": "Symbols"},
        {"key": "fast", "label": "Trend: fast average (days)", "kind": "int", "default": 50, "min": 5, "max": 200, "group": "Trend"},
        {"key": "slow", "label": "Trend: slow average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend"},
        {"key": "mom_days", "label": "Trend: above its close this many days ago", "kind": "int", "default": 252, "min": 20, "max": 504, "group": "Trend"},
        {"key": "a_spread_pct", "label": "Leg A: fast average at least this % above the slow", "kind": "float", "default": 3.0, "min": 0, "max": 20, "group": "Leg A"},
        {"key": "a_rsi", "label": "Leg A: RSI2 below", "kind": "float", "default": 8.0, "min": 0, "max": 50, "group": "Leg A"},
        {"key": "drop_days", "label": "Legs B, C: drop over (days)", "kind": "int", "default": 3, "min": 1, "max": 20, "group": "Leg B"},
        {"key": "b_drop_pct", "label": "Leg B: drop at least (%)", "kind": "float", "default": 4.0, "min": 0, "max": 30, "group": "Leg B"},
        {"key": "b_rsi", "label": "Leg B: RSI2 below", "kind": "float", "default": 10.0, "min": 0, "max": 50, "group": "Leg B"},
        {"key": "c_rsi", "label": "Legs A, B: confirming stock RSI2 below", "kind": "float", "default": 30.0, "min": 0, "max": 100, "group": "Leg B"},
        {"key": "c_drop_pct", "label": "Leg C: drop at least (%)", "kind": "float", "default": 8.0, "min": 0, "max": 50, "group": "Leg C"},
        {"key": "crash_rsi", "label": "Leg C: RSI2 below", "kind": "float", "default": 5.0, "min": 0, "max": 50, "group": "Leg C"},
        {"key": "c_pct", "label": "Leg C size (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Leg C"},
        {"key": "max_days", "label": "Sell after the first up close, or after (closes)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Exit"},
        {"key": "model_cost_pct", "label": "Backtest: model cost before listing (% a year)", "kind": "float", "default": 14.0, "min": 0, "max": 50, "group": "Backtest",
         "help": "Fee, financing and the drag of a 2x fund on a choppy index"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["signal"], p["confirm"]]))

    history_symbols = read_symbols

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def bench_extra(self):
        return [self.params["signal"]]

    def trade_symbols(self):
        return [self.params["trade"]]

    def benchmark_symbol(self):
        return self.params["trade"]

    def cash_target(self):
        return {}

    def parking(self):
        return {}

    def park_text(self):
        return "cash"

    def frame(self, now, model=False) -> pd.DataFrame:
        p = self.params
        data = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            df = df[~df.index.duplicated(keep="last")]
            data[s] = df if s == p["trade"] else HkCrashStrategy.dividend_adjusted(s, df)
        tr = data[p["trade"]]
        if model:
            tr = model_2x(tr, data, {p["signal"]: 1.0}, data[p["signal"]].index, float(p["model_cost_pct"]) / 100)
        fr = signals(tr, data, p)
        if not fr["ok"].any():
            raise md.DataError(f"Need about {int(p['mom_days']) + 5} daily bars of {p['signal']}")
        return fr

    def target_w(self, w):
        w = float(w)
        return {self.params["trade"]: round(min(w, 1.0) * (1 - self.buffer()), 4)} if w > 1e-9 else {}

    def target_for(self, state, size=None):
        return self.target_w(size or 0.0)

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        return f"{h['kind']} · {self.name}\n{h['text']}"

    def why(self, fr, i):
        p = self.params
        r = fr.iloc[i]
        a = fr.iloc[i - 1] if i > 0 else r
        tail = f" · {p['trade']} {r['w'] * 100:.0f}% from the next open"
        if r["w"] > a["w"]:
            leg = "A (dip in a strong uptrend)" if r["start_a"] else "B (sharp drop in an uptrend)" if r["start_b"] else "C (crash, half size)"
            return (f"Leg {leg}: {p['signal']} RSI2 {r['rsi2']:.1f}, {p['drop_days']}-day change {r['drop']:+.1f}%, "
                    f"{p['confirm']} RSI2 {r['c_rsi2']:.1f}") + tail
        if r["w"] < a["w"]:
            return (f"Sell: {p['signal']} closed up" if r["up"] else f"Sell: {p['max_days']} closes held") + tail
        return "No change" + tail

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        w, sts = fr["w"].values, fr["state"].values
        hist = []
        for i in range(max(1, len(fr) - 600), len(fr)):
            if abs(w[i] - w[i - 1]) > 1e-9:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if w[i] > w[i - 1] else "SELL", "from": sts[i - 1], "to": sts[i],
                             "price": float(fr["t_c"].iloc[i]), "text": self.why(fr, i)})
        k = len(fr) - 1
        while k > 0 and abs(w[k - 1] - w[k]) < 1e-9:
            k -= 1
        s, pct = last["state"], round(float(last["w"]) * 100)
        sp = (last["fast"] / last["slow"] - 1) * 100
        checks = [
            {"k": f"Trend · {p['signal']} SMA{p['fast']} vs SMA{p['slow']} · {p['mom_days']}-day change",
             "v": f"{sp:+.1f}% · {last['mom']:+.1f}% · {p['signal']} {(last['c'] / last['slow'] - 1) * 100:+.1f}% vs SMA{p['slow']}",
             "cls": "up" if sp >= float(p["a_spread_pct"]) and last["mom"] > 0 else ("" if (last["c"] > last["slow"] or last["mom"] > 0) else "dn"),
             "h": f"Leg A needs SMA{p['fast']} ≥ {p['a_spread_pct']:g}% above SMA{p['slow']} and the year up; leg B needs {p['signal']} above SMA{p['slow']} or the year up"},
            {"k": f"Dip · {p['signal']} RSI2 · {p['drop_days']}-day change", "v": f"{last['rsi2']:.1f} · {last['drop']:+.1f}%",
             "cls": "warn" if last["rsi2"] < float(p["b_rsi"]) else "",
             "h": f"A: RSI2 < {p['a_rsi']:g}; B: drop ≤ −{p['b_drop_pct']:g}% and RSI2 < {p['b_rsi']:g}; C: drop ≤ −{p['c_drop_pct']:g}% and RSI2 < {p['crash_rsi']:g}"},
            {"k": f"Confirm · {p['confirm']} RSI2", "v": f"{last['c_rsi2']:.1f}", "cls": "up" if last["c_rsi2"] < float(p["c_rsi"]) else "",
             "h": f"Legs A and B need it below {p['c_rsi']:g}"},
            {"k": "Open legs", "v": ", ".join(x for x, f in (("A", last["leg_a"]), ("B", last["leg_b"]), ("C", last["leg_c"])) if f) or "none",
             "h": f"Each is sold at the open after {p['signal']}'s first up close, {p['max_days']} closes at most"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open"}]
        tiles = [{"k": "a", "title": "In · leg A", "text": f"Strong uptrend, RSI2 < {p['a_rsi']:g}, {p['confirm']} confirms", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["a"]},
                 {"k": "b", "title": "In · leg B", "text": f"Uptrend, −{p['b_drop_pct']:g}% in {p['drop_days']} days, {p['confirm']} confirms",
                  "hold": f"100% {p['trade']}", "color": STATE_COLOR["b"]},
                 {"k": "c", "title": "In · leg C", "text": f"−{p['c_drop_pct']:g}% in {p['drop_days']} days, RSI2 < {p['crash_rsi']:g}",
                  "hold": f"{p['c_pct']:g}% {p['trade']}", "color": STATE_COLOR["c"]},
                 {"k": "out", "title": "Out", "text": "No dip", "hold": "cash", "color": STATE_COLOR["out"]}]

        def num(x):
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return None if x != x else x
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (w[i - 1] if i > 0 else w[i]), w[i]
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "sig": num(r["c"]), "rsi2": num(r["rsi2"]), "drop": num(r["drop"]),
                             "crsi": num(r["c_rsi2"]), "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "sig", "label": p["signal"], "fmt": "n2"},
                    {"k": "rsi2", "label": "RSI2", "fmt": "n1"}, {"k": "drop", "label": f"{p['drop_days']}-day %", "fmt": "n1"},
                    {"k": "crsi", "label": f"{p['confirm']} RSI2", "fmt": "n1"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = f"IN · {pct}% {p['trade']} · {STATE_TEXT[s]}" if pct > 0 else "OUT · cash"
        return {"ok": True, "state": s, "label": label, "target": self.target_w(last["w"]),
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": num(last["t_c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": num(last["t_c"]), "state_text": STATE_TEXT[s], "title": "Position · decided after each US close"}}

    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(t))]

        w = fr["w"].values
        markers = []
        for i in range(1, len(fr)):
            if w[i] > w[i - 1] + 1e-9:
                markers.append({"time": t[i], "position": "belowBar", "color": "#2962FF", "shape": "arrowUp", "text": f"→ {w[i] * 100:.0f}%"})
            elif w[i] < w[i - 1] - 1e-9:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#E040FB", "shape": "arrowDown", "text": f"→ {w[i] * 100:.0f}%"})
        sd = md.daily_closed(p["signal"], now)
        sd = HkCrashStrategy.dividend_adjusted(p["signal"], sd[~sd.index.duplicated(keep="last")]).reindex(fr.index)
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — trend and dips are read from this chart (dividends added back)",
               "candles": [{"time": t[i], "open": round(float(sd["o"].iloc[i]), 4), "high": round(float(sd["h"].iloc[i]), 4),
                            "low": round(float(sd["l"].iloc[i]), 4), "close": round(float(sd["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['fast']}", "color": "#26A69A", "width": 1, "data": ln("fast")},
                         {"name": f"SMA {p['slow']}", "color": "#FF9800", "width": 2, "data": ln("slow")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": [{"id": "rsi", "title": f"RSI2 · {p['signal']} and {p['confirm']}", "height": 70,
                          "lines": [{"name": p["signal"], "color": "#F5C76B", "width": 1, "data": ln("rsi2", 2)},
                                    {"name": p["confirm"], "color": "#5B8DEF", "width": 1, "data": ln("c_rsi2", 2)}],
                          "hlines": [{"value": float(p["b_rsi"]), "label": f"{p['b_rsi']:g}"}, {"value": float(p["c_rsi"]), "label": f"{p['c_rsi']:g}"}]},
                         {"id": "drop", "title": f"{p['signal']} {p['drop_days']}-day change (%)", "height": 60,
                          "lines": [{"name": "Change", "color": "#EF5350", "width": 1, "data": ln("drop", 2)}],
                          "hlines": [{"value": -float(p["b_drop_pct"]), "label": f"−{p['b_drop_pct']:g}%"}, {"value": -float(p["c_drop_pct"]), "label": f"−{p['c_drop_pct']:g}%"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                          "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}],
               "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        trd = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "markers": markers, "panes": [], "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, trd], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close, buy {p['trade']} at the next open when one of three dips appears in {p['signal']} (dividends added back):",
            f"A: SMA{p['fast']} at least {p['a_spread_pct']:g}% above SMA{p['slow']}, {p['signal']} above its close {p['mom_days']} days ago and RSI2 < {p['a_rsi']:g}, "
            f"with {p['confirm']} RSI2 < {p['c_rsi']:g} → 100%.",
            f"B: {p['signal']} above SMA{p['slow']} or above a year ago, down {p['b_drop_pct']:g}%+ over {p['drop_days']} days and RSI2 < {p['b_rsi']:g}, "
            f"with {p['confirm']} RSI2 < {p['c_rsi']:g} → 100%.",
            f"C: down {p['c_drop_pct']:g}%+ over {p['drop_days']} days and RSI2 < {p['crash_rsi']:g}, any trend → {p['c_pct']:g}%.",
            f"Each is sold at the open after {p['signal']}'s first up close ({p['max_days']} closes at most). Otherwise cash."],
            "flow": f"{p['signal']} + {p['confirm']} daily → {p['trade']} · cash",
            "tv": f"{p['signal']} daily: SMA {p['fast']}, SMA {p['slow']}, RSI 2, {p['drop_days']}-day change; {p['confirm']}: RSI 2",
            "rule": f"Dips only: A trend dip (RSI2 < {p['a_rsi']:g}), B −{p['b_drop_pct']:g}%/{p['drop_days']}d (RSI2 < {p['b_rsi']:g}), both with {p['confirm']} "
                    f"RSI2 < {p['c_rsi']:g}; C crash {p['c_pct']:g}%; sell after the first up close"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.read_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        base = BT.daily_tr(p["signal"])
        tr = model_2x(BT.daily_tr(sym), {p["signal"]: base}, {p["signal"]: 1.0}, base.index, float(p["model_cost_pct"]) / 100).reindex(fr.index)
        ok = fr["ok"].values & tr["o"].notna().values & tr["c"].notna().values
        if not ok.any():
            raise BT.BacktestError("Not enough overlapping history yet")
        first = int(np.argmax(ok))
        o_tr, c_tr = tr["o"].astype(float).values, tr["c"].astype(float).values
        W = fr["w"].values
        B = BT.Book(cost)
        buf, band = 1 - self.buffer(), self.rebalance_band()
        days, eq, expo, states = [], [], [], []
        cur, drift = 0.0, False
        for i in range(first, len(fr)):
            j = i - 1 - delay
            d = fr.index[i].date()
            t_open = datetime.combine(d, dtime(9, 30), NY)
            if j >= first:
                want = float(W[j])
                if abs(want - cur) > 1e-9:
                    kind = "START" if not B.trades else ("BUY" if want > cur else "SELL")
                    B.rebalance({sym: want * buf} if want > 0 else {}, {sym: o_tr[i]}, t_open, self.why(fr, j), kind)
                    cur = want
                elif drift and cur > 0:
                    B.rebalance({sym: cur * buf}, {sym: o_tr[i]}, t_open,
                                f"rebalance: the holding drifted more than {band * 100:g} points from its target", "REBALANCE")
            aw = B.weights({sym: c_tr[i]}).get(sym, 0.0)
            drift = abs(aw - cur * buf) > band
            days.append(d)
            eq.append(B.value({sym: c_tr[i]}))
            expo.append(aw)
            states.append(fr["state"].iloc[i])
        real0 = BT.daily_tr(sym)
        listed = str(real0.index[0].date()) if real0 is not None and not real0.empty else None
        return {"days": days, "eq": eq, "expo": expo, "trades": B.trades, "fees": B.fees, "state": states,
                "built": {sym: listed} if listed and listed > str(days[0]) else {},
                "bench": {sym: tr.dropna(subset=["c"]), p["signal"]: base}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": p["signal"],
                "data_from": str(days[0]),
                "data_note": f"{p['signal']} and {p['confirm']} daily bars with dividends added back (signals) · {sym} daily total-return prices; {sym} "
                             f"before {listed}: modelled as 2 × {p['signal']} daily minus {p['model_cost_pct']:g}% a year"}

    def check_table(self, now, rows=12):
        """An independent recompute of the two RSI2 values (Wilder, plain loops) from the closes."""
        p = self.params
        fr = self.frame(now)

        def rsi_loop(sym):
            q = md.daily_closed(sym, now)
            q = HkCrashStrategy.dividend_adjusted(sym, q[~q.index.duplicated(keep="last")])["c"].astype(float)
            c = q.tolist()
            au = ad = None
            out = {}
            for i in range(1, len(c)):
                d = c[i] - c[i - 1]
                u, dn = max(d, 0.0), max(-d, 0.0)
                au = u if au is None else au + (u - au) / 2
                ad = dn if ad is None else ad + (dn - ad) / 2
                out[q.index[i]] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
            return out
        r1, r2 = rsi_loop(p["signal"]), rsi_loop(p["confirm"])
        cols = [p["signal"], "RSI2 · bot / check", f"{p['confirm']} RSI2 · bot / check", "Held %"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            a, b = r1.get(d, float("nan")), r2.get(d, float("nan"))
            diff = max(abs(r["rsi2"] - a), abs(r["c_rsi2"] - b)) / 100
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()), "vals": [float(r["c"]), f"{r['rsi2']:.2f} / {a:.2f}", f"{r['c_rsi2']:.2f} / {b:.2f}",
                        float(r["w"] * 100)], "ok": bool(diff < 1e-6)})
        return cols, out, worst
