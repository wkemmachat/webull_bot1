"""Breakout + calm + credit, a fast stop, and one-day RSI2 dips (AIBU, Direxion Daily AI and Big Data Bull 2X). Research "AIBU
(2x AI & Big Data): 2 best strategies" rounds 1–4 (27 Nov 2026): Strategy 2++.

After each US close (signal at the close, trade at the next open), from AIBU's own daily bars:
  breakout  AIBU closes above its previous dc_entry-day high → on; closes below its previous dc_exit-day low → off
  gates     AIBU calm (20-day volatility at or below its calm_q percentile of 252 days) AND LQD ÷ IEF above its SMA(credit_ma)
  size      min(1, vt ÷ AIBU's 20-day volatility)
  stop      AIBU's stop_days-day change below −stop_pct → the trend part is in cash for stop_out trading days (dips still allowed)
  dip       QQQ's RSI2 (Wilder) closes below dip_rsi → 100% for one day (held while each close repeats it)
  held      the larger of the trend part and the dip
Before AIBU listed (May 2024) the backtest models it as model_beta × an IYW/FDN mix's daily move minus model_cost_pct a year.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .hk_crash import HkCrashStrategy
from .momentum_calm import parse_weights
from .quantum_mix import rsi
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"trend": "#26A69A", "stop": "#EF5350", "dip": "#F5C76B", "out": "#4A5263"}
STATE_TEXT = {"trend": "breakout trend", "stop": "out · fast stop", "dip": "one-day dip", "out": "out · cash"}
TV.update({"AIBU": "AMEX:AIBU", "FDN": "AMEX:FDN"})


def model_beta(real: pd.DataFrame | None, stocks: dict, weights: dict, idx, beta: float, cost_y: float) -> pd.DataFrame:
    """beta × the weighted mix's daily move (open, high, low, close from the previous close) minus cost, joined to `real`'s first
    close. A member without a price that day is left out and the others re-weighted."""
    rel = {}
    for k in ("o", "h", "l", "c"):
        num = pd.Series(0.0, index=idx)
        den = pd.Series(0.0, index=idx)
        for s, w in weights.items():
            df = stocks[s][~stocks[s].index.duplicated(keep="last")].reindex(idx)
            r = df[k].astype(float) / df["c"].astype(float).shift(1) - 1
            num += (w * r).fillna(0.0)
            den += w * r.notna()
        rel[k] = (num / den.where(den > 0)).values
    n = len(idx)
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    prev = 100.0
    for i in range(n):
        if np.isnan(rel["c"][i]):
            continue
        o[i] = prev * (1 + beta * rel["o"][i])
        cc = prev * (1 + beta * rel["c"][i] - cost_y / 252)
        h[i] = max(prev * (1 + beta * rel["h"][i]), o[i], cc)
        l[i] = min(prev * (1 + beta * rel["l"][i]), o[i], cc)
        c[i] = prev = cc
    M = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": 0.0}, index=idx).dropna(subset=["c"])
    if real is None or real.empty:
        return M
    J = real.index[0]
    if J not in M.index:
        return real
    f = float(real["c"].iloc[0]) / float(M.loc[J, "c"])
    early = M[M.index < J].copy()
    for k in ("o", "h", "l", "c"):
        early[k] = early[k] * f
    return pd.concat([early, real[["o", "h", "l", "c", "v"]]])


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values
    C = tr["c"].astype(float)
    hi = C.shift(1).rolling(int(p["dc_entry"])).max()
    lo = C.shift(1).rolling(int(p["dc_exit"])).min()
    fr["dc_hi"], fr["dc_lo"] = hi.values, lo.values
    v = np.log(C).diff().rolling(20).std()
    fr["vol"] = (v * np.sqrt(252)).values
    fr["vol_q"] = (v.rolling(252).quantile(float(p["calm_q"]) / 100) * np.sqrt(252)).values
    la = data["LQD"]["c"].astype(float) / data["IEF"]["c"].astype(float)
    fr["credit_pct"] = ((la / la.rolling(int(p["credit_ma"])).mean() - 1) * 100).reindex(idx).values
    fr["chg"] = ((C / C.shift(int(p["stop_days"])) - 1) * 100).values
    q = data[p["dip_symbol"]]["c"].astype(float)
    fr["rsi2"] = rsi(q, 2).reindex(idx).values
    need = ["dc_hi", "dc_lo", "vol_q", "credit_pct", "chg", "rsi2"]
    ok = ~fr[need].isna().any(axis=1).values
    n = len(fr)
    on_arr = np.zeros(n, dtype=bool)
    on = False
    cv, hv, lv = C.values, hi.values, lo.values
    for i in range(n):
        if ok[i]:
            if not on and cv[i] > hv[i]:
                on = True
            elif on and cv[i] < lv[i]:
                on = False
        on_arr[i] = on and ok[i]
    calm = ok & (fr["vol"].values <= fr["vol_q"].values)
    credit = ok & (fr["credit_pct"].values > 0)
    stop = np.zeros(n, dtype=bool)
    left = 0
    hit = ok & (fr["chg"].values < -float(p["stop_pct"])) & (float(p["stop_pct"]) > 0)
    for i in range(n):
        if hit[i]:
            left = int(p["stop_out"])
        stop[i] = left > 0
        left = max(0, left - 1)
    trend = on_arr & calm & credit
    vol = np.where(fr["vol"].values > 0, fr["vol"].values, np.inf)
    tw = np.where(trend & ~stop, np.minimum(1.0, float(p["vt_pct"]) / 100 / vol), 0.0)
    dip = ok & (fr["rsi2"].values < float(p["dip_rsi"]))
    fr["w_trend"] = tw
    fr["w"] = np.where(ok, np.maximum(tw, np.where(dip, float(p["dip_pct"]) / 100, 0.0)), 0.0)
    fr["dc_on"], fr["calm"], fr["credit"], fr["trend"], fr["stop"], fr["dip"], fr["ok"] = on_arr, calm, credit, trend, stop, dip, ok
    fr["state"] = np.where(~ok, "", np.where(tw > 0, "trend", np.where(dip, "dip", np.where(trend & stop, "stop", "out"))))
    return fr


@register
class BreakoutCalmDipStrategy(RegimeStrategy):
    type = "breakout_calm_dip"
    label = "Breakout + calm + credit, fast stop, one-day RSI2 dips (2x ETF read from itself)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds the 2x ETF after a 30-day breakout while it is calm and credit is healthy, sized by its volatility; "
                   "a 13% fall in 5 days takes the trend part out for 7 days; one-day dip buys after QQQ's RSI2 closes under 6.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with (also the signal)", "kind": "symbol", "default": "AIBU", "group": "Symbols"},
        {"key": "dip_symbol", "label": "Dips read from", "kind": "symbol", "default": "QQQ", "group": "Symbols"},
        {"key": "dc_entry", "label": "Trend: close above the previous high of (days)", "kind": "int", "default": 30, "min": 5, "max": 250, "group": "Trend"},
        {"key": "dc_exit", "label": "Trend ends: close below the previous low of (days)", "kind": "int", "default": 20, "min": 5, "max": 250, "group": "Trend"},
        {"key": "calm_q", "label": "Calm: volatility at or below percentile", "kind": "float", "default": 80.0, "min": 50, "max": 99, "group": "Trend"},
        {"key": "credit_ma", "label": "Credit: LQD ÷ IEF above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Trend"},
        {"key": "vt_pct", "label": "Trend size: target volatility (%)", "kind": "float", "default": 60.0, "min": 5, "max": 300, "group": "Trend"},
        {"key": "stop_pct", "label": "Fast stop: fall over the look-back (%)", "kind": "float", "default": 13.0, "min": 0, "max": 60, "group": "Fast stop",
         "help": "0 = off"},
        {"key": "stop_days", "label": "Fast stop: look-back (days)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Fast stop"},
        {"key": "stop_out", "label": "Fast stop: trend out for (trading days)", "kind": "int", "default": 7, "min": 1, "max": 60, "group": "Fast stop"},
        {"key": "dip_rsi", "label": "Dip: RSI2 below (0 = off)", "kind": "float", "default": 6.0, "min": 0, "max": 50, "group": "Dips"},
        {"key": "dip_pct", "label": "Dip size (%)", "kind": "float", "default": 100.0, "min": 0, "max": 100, "group": "Dips"},
        {"key": "model_basket", "label": "Backtest: model before listing (symbol:weight)", "kind": "text", "default": "IYW:70,FDN:30", "group": "Backtest"},
        {"key": "model_beta", "label": "Backtest: model leverage", "kind": "float", "default": 2.26, "min": 1, "max": 4, "group": "Backtest"},
        {"key": "model_cost_pct", "label": "Backtest: model cost (% a year)", "kind": "float", "default": 4.0, "min": 0, "max": 30, "group": "Backtest",
         "help": "Fund fee plus the financing of the leverage"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["dip_symbol"], "LQD", "IEF"]))

    def history_symbols(self):
        return list(dict.fromkeys(self.read_symbols() + list(parse_weights(self.params["model_basket"]))))

    def data_needs(self):
        return [(s, "1d") for s in self.history_symbols()]

    def bench_extra(self):
        return [self.params["dip_symbol"]]

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
        for s in (self.history_symbols() if model else self.read_symbols()):
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            df = df[~df.index.duplicated(keep="last")]
            data[s] = df if s == p["trade"] else HkCrashStrategy.dividend_adjusted(s, df)
        tr = data[p["trade"]]
        if model:
            w = parse_weights(p["model_basket"])
            tr = model_beta(tr, data, w, data[p["dip_symbol"]].index, float(p["model_beta"]), float(p["model_cost_pct"]) / 100)
        fr = signals(tr, data, p)
        if not fr["ok"].any():
            raise md.DataError(f"Need about 275 daily bars of {p['trade']}")
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
        z, tail = r["state"], f" · {p['trade']} {r['w'] * 100:.0f}% from the next open"
        if z == "trend":
            if a["w_trend"] == 0:
                return f"Trend on: {p['trade']} above its {p['dc_entry']}-day high, calm, credit healthy" + tail
            return f"Trend size changed ({p['trade']} volatility {r['vol'] * 100:.0f}%)" + tail
        if z == "dip":
            return f"One-day dip: {p['dip_symbol']} RSI2 {r['rsi2']:.1f} < {p['dip_rsi']:g}" + tail
        if z == "stop" and not a["stop"]:
            return f"Fast stop: {p['trade']} {r['chg']:+.1f}% in {p['stop_days']} days · trend out for {p['stop_out']} days" + tail
        if a["w_trend"] > 0:
            bits = []
            if r["stop"]:
                bits.append(f"fast stop ({p['trade']} {r['chg']:+.1f}% in {p['stop_days']} days)")
            if not r["dc_on"]:
                bits.append(f"{p['trade']} below its {p['dc_exit']}-day low")
            if not r["calm"]:
                bits.append("not calm")
            if not r["credit"]:
                bits.append("credit weak")
            return "Trend off: " + ", ".join(bits or ["gate failed"]) + tail
        return "Dip sold" + tail

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
        left = 0
        if last["stop"]:
            j = len(fr) - 1
            while j > 0 and not (fr["chg"].iloc[j] < -float(p["stop_pct"])):
                j -= 1
            left = int(p["stop_out"]) - (len(fr) - 1 - j) - 1
        checks = [
            {"k": f"Trend · {p['trade']} vs its previous {p['dc_entry']}-day high / {p['dc_exit']}-day low",
             "v": f"{last['t_c']:,.2f} · high {last['dc_hi']:,.2f} · low {last['dc_lo']:,.2f} · {'on' if last['dc_on'] else 'off'}",
             "cls": "up" if last["dc_on"] else "dn", "h": "On at a close above the high, off at a close below the low"},
            {"k": f"Calm · {p['trade']} 20-day volatility", "v": f"{last['vol'] * 100:.0f}% a year vs {last['vol_q'] * 100:.0f}% ({p['calm_q']:g}th percentile)",
             "cls": "up" if last["calm"] else "dn"},
            {"k": f"Credit · LQD ÷ IEF vs SMA{p['credit_ma']}", "v": f"{last['credit_pct']:+.2f}%", "cls": "up" if last["credit"] else "dn"},
            {"k": f"Fast stop · {p['trade']} {p['stop_days']}-day change", "v": f"{last['chg']:+.1f}%" + (f" · stop on, {max(left, 0)} more day(s)" if last["stop"] else " · off"),
             "cls": "dn" if last["stop"] else "", "h": f"Below −{p['stop_pct']:g}% → the trend part out for {p['stop_out']} trading days"},
            {"k": "Size", "v": f"{min(1, p['vt_pct'] / 100 / max(last['vol'], 1e-9)) * 100:.0f}% when the trend is on ({p['vt_pct']:g}% ÷ volatility)"},
            {"k": f"Dip · {p['dip_symbol']} RSI2", "v": f"{last['rsi2']:.1f}", "cls": "warn" if last["dip"] else "",
             "h": f"Below {p['dip_rsi']:g} → {p['dip_pct']:g}% for one day"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open"}]
        tiles = [{"k": "trend", "title": "In · breakout trend", "text": f"Above the {p['dc_entry']}-day high, calm, credit ok", "hold": "up to 100% by volatility",
                  "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · one-day dip", "text": f"{p['dip_symbol']} RSI2 < {p['dip_rsi']:g}", "hold": f"{p['dip_pct']:g}% {p['trade']}",
                  "color": STATE_COLOR["dip"]},
                 {"k": "stop", "title": "Out · fast stop", "text": f"{p['trade']} −{p['stop_pct']:g}% in {p['stop_days']} days", "hold": f"cash {p['stop_out']} days",
                  "color": STATE_COLOR["stop"]},
                 {"k": "out", "title": "Out", "text": "No trend, no dip", "hold": "cash", "color": STATE_COLOR["out"]}]

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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "dc": "on" if r["dc_on"] else "off", "vol": num(r["vol"] * 100),
                             "credit": "ok" if r["credit"] else "weak", "chg": num(r["chg"]), "stop": "on" if r["stop"] else "", "rsi2": num(r["rsi2"]),
                             "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "dc", "label": "Breakout"}, {"k": "vol", "label": "Vol %", "fmt": "n0"},
                    {"k": "credit", "label": "Credit"}, {"k": "chg", "label": f"{p['stop_days']}-day %", "fmt": "n1"}, {"k": "stop", "label": "Stop"},
                    {"k": "rsi2", "label": f"{p['dip_symbol']} RSI2", "fmt": "n1"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = f"IN · {pct}% {p['trade']} · {STATE_TEXT[s]}" if pct > 0 else ("OUT · cash (fast stop)" if s == "stop" else "OUT · cash")
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
        sig = {"id": "signal", "title": f"{p['trade']} · 1D", "subtitle": "Signal and traded — breakout, calm and the fast stop are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"Previous {p['dc_entry']}-day high", "color": "#26A69A", "width": 1, "data": ln("dc_hi")},
                         {"name": f"Previous {p['dc_exit']}-day low", "color": "#EF5350", "width": 1, "data": ln("dc_lo")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": [{"id": "vol", "title": f"{p['trade']} volatility (% a year)", "height": 70,
                          "lines": [{"name": "Volatility", "color": "#F5C76B", "width": 2, "data": ln("vol", 2, 100)},
                                    {"name": f"Calm line ({p['calm_q']:g}th)", "color": "#26A69A", "width": 1, "data": ln("vol_q", 2, 100)}], "hlines": []},
                         {"id": "chg", "title": f"{p['trade']} {p['stop_days']}-day change (%) · fast stop below −{p['stop_pct']:g}%", "height": 60,
                          "lines": [{"name": "Change", "color": "#EF5350", "width": 1, "data": ln("chg", 2)}],
                          "hlines": [{"value": -float(p["stop_pct"]), "label": f"−{p['stop_pct']:g}%"}]},
                         {"id": "credit", "title": f"Credit · LQD ÷ IEF, % vs its {p['credit_ma']}-day average", "height": 50,
                          "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("credit_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                          "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}],
               "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        q = md.daily_closed(p["dip_symbol"], now)
        q = HkCrashStrategy.dividend_adjusted(p["dip_symbol"], q[~q.index.duplicated(keep="last")]).reindex(fr.index)
        dip = {"id": "dip", "title": f"{p['dip_symbol']} · 1D", "subtitle": "Dips — RSI2 of its closes (dividends added back)",
               "candles": [{"time": t[i], "open": round(float(q["o"].iloc[i]), 4), "high": round(float(q["h"].iloc[i]), 4),
                            "low": round(float(q["l"].iloc[i]), 4), "close": round(float(q["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "markers": [],
               "panes": [{"id": "rsi", "title": f"RSI2 · {p['dip_symbol']}", "height": 60, "lines": [{"name": "RSI2", "color": "#F5C76B", "width": 1, "data": ln("rsi2", 2)}],
                          "hlines": [{"value": float(p["dip_rsi"]), "label": f"{p['dip_rsi']:g}"}]}],
               "tv": tv_url(p["dip_symbol"]), "tv_symbol": TV.get(p["dip_symbol"], p["dip_symbol"])}
        return {"charts": [sig, dip], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close: the trend part turns on when {p['trade']} closes above its previous {p['dc_entry']}-day high and off below its "
            f"previous {p['dc_exit']}-day low; it holds only while {p['trade']} is calm ({p['calm_q']:g}th percentile of 252 days) and LQD ÷ IEF is above "
            f"its {p['credit_ma']}-day average. Size: {p['vt_pct']:g}% ÷ {p['trade']}'s 20-day volatility, at most 100%.",
            f"Fast stop: when {p['trade']} falls more than {p['stop_pct']:g}% in {p['stop_days']} days, the trend part stays in cash for {p['stop_out']} trading days.",
            f"Dip: after {p['dip_symbol']}'s RSI2 closes below {p['dip_rsi']:g}, {p['dip_pct']:g}% for one day.",
            "Otherwise cash. Orders at the next open."],
            "flow": f"{p['trade']} + {p['dip_symbol']} + LQD ÷ IEF daily → {p['trade']} · cash",
            "tv": f"{p['trade']} daily: Donchian {p['dc_entry']}/{p['dc_exit']} (previous bars); {p['dip_symbol']}: RSI 2; LQD/IEF ratio SMA {p['credit_ma']}",
            "rule": f"{p['trade']} DC{p['dc_entry']}/{p['dc_exit']} + calm + credit (vol-sized), stop −{p['stop_pct']:g}%/{p['stop_days']}d → out "
                    f"{p['stop_out']}d; {p['dip_symbol']} RSI2 < {p['dip_rsi']:g} one-day dips; else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        w = parse_weights(p["model_basket"])
        base = BT.daily_tr(p["dip_symbol"])
        tr = model_beta(BT.daily_tr(sym), {s: BT.daily_tr(s) for s in w}, w, base.index, float(p["model_beta"]),
                        float(p["model_cost_pct"]) / 100).reindex(fr.index)
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
                "bench": {sym: tr.dropna(subset=["c"]), p["dip_symbol"]: base}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": p["dip_symbol"],
                "data_from": str(days[0]),
                "data_note": f"{sym} daily prices (signals and trades), {p['dip_symbol']}, LQD and IEF daily bars with dividends added back; {sym} before "
                             f"{listed}: modelled as {p['model_beta']:g} × ({', '.join(f'{k} {v * 100:.0f}%' for k, v in w.items())}) daily minus "
                             f"{p['model_cost_pct']:g}% a year — the signals use the model too"}

    def check_table(self, now, rows=12):
        """An independent recompute of QQQ's RSI2 (Wilder, plain loop) and the breakout high from the closes."""
        p = self.params
        fr = self.frame(now)
        q = md.daily_closed(p["dip_symbol"], now)
        q = HkCrashStrategy.dividend_adjusted(p["dip_symbol"], q[~q.index.duplicated(keep="last")])["c"].astype(float)
        qc = q.tolist()
        au = ad = None
        rs = {}
        for i in range(1, len(qc)):
            d = qc[i] - qc[i - 1]
            u, dn = max(d, 0.0), max(-d, 0.0)
            au = u if au is None else au + (u - au) / 2
            ad = dn if ad is None else ad + (dn - ad) / 2
            rs[q.index[i]] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
        c = fr["t_c"].tolist()
        e = int(p["dc_entry"])
        cols = [p["trade"], f"{p['dc_entry']}-day high · bot / check", f"{p['dip_symbol']} RSI2 · bot / check", "Held %"]
        out, worst = [], 0.0
        n = len(fr)
        for i in range(n - rows, n):
            r = fr.iloc[i]
            hi = max(c[i - e:i])
            rv = rs.get(fr.index[i], float("nan"))
            diff = max(abs(r["dc_hi"] - hi) / max(hi, 1e-9), abs(r["rsi2"] - rv) / 100)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(fr.index[i]).timestamp()), "vals": [c[i], f"{r['dc_hi']:,.2f} / {hi:,.2f}", f"{r['rsi2']:.2f} / {rv:.2f}",
                        float(r["w"] * 100)], "ok": bool(diff < 1e-6)})
        return cols, out, worst
