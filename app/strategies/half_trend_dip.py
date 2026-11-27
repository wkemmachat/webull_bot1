"""Half trend, half dip, with a yuan filter (CHAU, Direxion Daily CSI 300 China A Share Bull 2X). Research "CHAU 2x China A-shares:
best buy/sell strategies" rounds 1–4 (26 Nov 2026): S4, kept after round 4.

After each US close, from daily bars with dividends added back (signal at the close, trade at the next open):
  yuan     USD/CNY's daily close (that day's, or the day before with yuan_lag 1) below its SMA(yuan_ma) — both halves
           trade only while it is on
  trend    half: ASHR's Supertrend (st_atr, st_mult) up AND FXI above its SMA(fxi_ma)           → trend_pct of the money
  dip      half: a dip starts after CHAU closes with IBS < dip_ibs_max while CHAU is above its SMA(dip_ma) and
           LQD ÷ IEF is above its SMA(credit_ma); it ends at a close with IBS > exit_ibs or after dip_days closes → dip_pct
  else     cash
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from ..indicators import supertrend
from .base import register
from .hk_crash import HkCrashStrategy
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"both": "#26A69A", "trend": "#5B8DEF", "dip": "#F5C76B", "out": "#4A5263", "yuan_off": "#8E6CC8"}
STATE_TEXT = {"both": "trend half + dip half", "trend": "trend half", "dip": "dip half", "out": "out · cash",
              "yuan_off": "out · yuan filter off"}
TV.update({"CHAU": "AMEX:CHAU", "ASHR": "AMEX:ASHR", "CNY=X": "FX_IDC:USDCNY"})


def as_of(s: pd.Series, idx, lag: int = 0) -> np.ndarray:
    """For each date in idx, the last value of s dated on it (lag 0) or strictly before it (lag 1). USD/CNY's daily bar is
    dated in London; its day's rate is known at the US close (onshore yuan trading ends at 15:30 UTC)."""
    s = s.dropna().sort_index()
    pos = np.searchsorted(s.index.values, pd.DatetimeIndex(idx).values, side="right" if int(lag) <= 0 else "left") - 1
    out = np.where(pos >= 0, s.values[np.clip(pos, 0, None)], np.nan)
    return out.astype(float)


def dip_weights(start_ok, ibs, exit_ibs, max_days):
    """1 while a dip trade is open. A dip opens at a close where start_ok; it closes at a later close with IBS > exit_ibs,
    or at the close max_days after it opened. A new dip may open at the close that ends one."""
    n = len(ibs)
    on = np.zeros(n, dtype=bool)
    open_, days = False, 0
    for i in range(n):
        if open_:
            days += 1
            if ibs[i] > exit_ibs or days >= max_days:
                open_ = False
        if not open_ and start_ok[i]:
            open_, days = True, 0
        on[i] = open_
    return on


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values
    rng = fr["t_h"] - fr["t_l"]
    fr["ibs"] = np.where(rng > 0, (fr["t_c"] - fr["t_l"]) / rng.where(rng > 0, 1.0), 0.5)
    sig = data[p["dip_symbol"]]["c"].astype(float)
    fr["dip_c"] = sig.reindex(idx).values
    fr["dip_ma"] = sig.rolling(int(p["dip_ma"])).mean().reindex(idx).values
    a = data[p["trend_symbol"]]
    st = supertrend(a["h"].values, a["l"].values, a["c"].values, int(p["st_atr"]), float(p["st_mult"]))
    fr["st_line"] = pd.Series(st["line"], index=a.index).reindex(idx).values
    fr["st_up"] = pd.Series(st["up"].astype(float), index=a.index).reindex(idx).values
    fr["a_c"] = a["c"].astype(float).reindex(idx).values
    f = data[p["gate_symbol"]]["c"].astype(float)
    fr["f_c"], fr["f_ma"] = f.reindex(idx).values, f.rolling(int(p["fxi_ma"])).mean().reindex(idx).values
    la = data["LQD"]["c"].astype(float) / data["IEF"]["c"].astype(float)
    fr["credit_pct"] = ((la / la.rolling(int(p["credit_ma"])).mean() - 1) * 100).reindex(idx).values
    y = data[p["yuan"]]["c"].astype(float)
    y = y[y > 0]
    lag = int(p.get("yuan_lag", 0))
    fr["cny"], fr["cny_ma"] = as_of(y, idx, lag), as_of(y.rolling(int(p["yuan_ma"])).mean(), idx, lag)
    need = ["dip_ma", "st_line", "st_up", "f_ma", "credit_pct", "cny_ma"]
    ok = ~fr[need].isna().any(axis=1).values
    yuan = ok & (fr["cny"].values < fr["cny_ma"].values)
    trend = ok & (fr["st_up"].values > 0.5) & (fr["f_c"].values > fr["f_ma"].values)
    credit = ok & (fr["credit_pct"].values > 0)
    start = ok & (fr["ibs"].values < float(p["dip_ibs_max"])) & (fr["dip_c"].values > fr["dip_ma"].values) & credit
    if p.get("yuan_gates_dip_start", True):
        start = start & yuan
    dip = dip_weights(start, fr["ibs"].values, float(p["exit_ibs"]), int(p["dip_days"]))
    tw, dw = float(p["trend_pct"]) / 100, float(p["dip_pct"]) / 100
    fr["yuan"], fr["trend"], fr["credit"], fr["dip"], fr["ok"] = yuan, trend, credit, dip, ok
    fr["w_trend"] = np.where(trend & yuan, tw, 0.0)
    fr["w_dip"] = np.where(dip & yuan, dw, 0.0)
    fr["w"] = np.minimum(1.0, fr["w_trend"] + fr["w_dip"])
    t_on, d_on = fr["w_trend"].values > 0, fr["w_dip"].values > 0
    fr["state"] = np.where(~ok, "", np.where(t_on & d_on, "both", np.where(t_on, "trend", np.where(d_on, "dip",
                           np.where(~yuan & (trend | dip), "yuan_off", "out")))))
    return fr


@register
class HalfTrendDipStrategy(RegimeStrategy):
    type = "half_trend_dip"
    label = "Half trend (Supertrend + gate), half IBS dip, yuan filter (2x China A-shares)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: half the money on a trend (ASHR Supertrend up and FXI above its 200-day average), half on CHAU IBS dips "
                   "(above its 100-day average, credit healthy), both only while the yuan is firm; cash else.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "CHAU", "group": "Symbols"},
        {"key": "trend_symbol", "label": "Trend read from", "kind": "symbol", "default": "ASHR", "group": "Symbols"},
        {"key": "gate_symbol", "label": "Trend gate", "kind": "symbol", "default": "FXI", "group": "Symbols"},
        {"key": "dip_symbol", "label": "Dip average read from", "kind": "symbol", "default": "CHAU", "group": "Symbols"},
        {"key": "yuan", "label": "Yuan (USD per CNY quote)", "kind": "text", "default": "CNY=X", "group": "Symbols"},
        {"key": "trend_pct", "label": "Trend half (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Trend half"},
        {"key": "st_atr", "label": "Supertrend ATR (days)", "kind": "int", "default": 10, "min": 2, "max": 50, "group": "Trend half"},
        {"key": "st_mult", "label": "Supertrend multiplier", "kind": "float", "default": 2.0, "min": 0.5, "max": 6, "group": "Trend half"},
        {"key": "fxi_ma", "label": "Gate: above its SMA (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend half"},
        {"key": "dip_pct", "label": "Dip half (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Dip half"},
        {"key": "dip_ibs_max", "label": "Dip: CHAU IBS below", "kind": "float", "default": 0.2, "min": 0, "max": 0.5, "group": "Dip half"},
        {"key": "dip_ma", "label": "Dip only above its SMA (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Dip half"},
        {"key": "credit_ma", "label": "Dip only while LQD ÷ IEF above its SMA (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Dip half"},
        {"key": "exit_ibs", "label": "Dip ends: IBS above", "kind": "float", "default": 0.8, "min": 0.5, "max": 1, "group": "Dip half"},
        {"key": "dip_days", "label": "Dip ends after (closes)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Dip half"},
        {"key": "yuan_ma", "label": "Yuan filter: USD/CNY below its SMA (days)", "kind": "int", "default": 50, "min": 5, "max": 300, "group": "Yuan"},
        {"key": "yuan_lag", "label": "Yuan: use the close of (0 = that day, 1 = the day before)", "kind": "int", "default": 0, "min": 0, "max": 1, "group": "Yuan"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["dip_symbol"], p["trend_symbol"], p["gate_symbol"], "LQD", "IEF", p["yuan"]]))

    history_symbols = read_symbols

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def bench_extra(self):
        return [self.params["trend_symbol"]]

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

    def frame(self, now) -> pd.DataFrame:
        p = self.params
        data = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            df = df[~df.index.duplicated(keep="last")]
            data[s] = df if s == p["yuan"] else HkCrashStrategy.dividend_adjusted(s, df)
        tr = md.daily_closed(p["trade"], now)
        tr = tr[~tr.index.duplicated(keep="last")]
        fr = signals(tr, data, p)
        if not fr["ok"].any():
            raise md.DataError(f"Need {max(int(p['fxi_ma']), int(p['dip_ma']), int(p['credit_ma'])) + 2} daily bars of the signals")
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
        r, a = fr.iloc[i], fr.iloc[i - 1] if i > 0 else fr.iloc[i]
        bits = []
        if r["w_trend"] > 0 and a["w_trend"] == 0:
            bits.append(f"trend half on ({p['trend_symbol']} Supertrend up, {p['gate_symbol']} above SMA{p['fxi_ma']})")
        elif r["w_trend"] == 0 and a["w_trend"] > 0:
            bits.append("trend half off (" + ("yuan filter off" if not r["yuan"] else f"{p['trend_symbol']} Supertrend down"
                        if r["st_up"] < 0.5 else f"{p['gate_symbol']} below SMA{p['fxi_ma']}") + ")")
        if r["w_dip"] > 0 and a["w_dip"] == 0:
            bits.append(f"dip half on ({p['trade']} IBS {r['ibs']:.2f} < {p['dip_ibs_max']:g})")
        elif r["w_dip"] == 0 and a["w_dip"] > 0:
            bits.append("dip half off (" + ("yuan filter off" if not r["yuan"] else f"IBS {r['ibs']:.2f} > {p['exit_ibs']:g}"
                        if r["ibs"] > float(p["exit_ibs"]) else f"{p['dip_days']} closes") + ")")
        t = ", ".join(bits) or "no change"
        return t[0].upper() + t[1:] + f" · {p['trade']} {r['w'] * 100:.0f}% from the next open"

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
        checks = [
            {"k": f"Yuan · USD/CNY vs SMA{p['yuan_ma']}", "v": f"{last['cny']:.4f} vs {last['cny_ma']:.4f}",
             "cls": "up" if last["yuan"] else "dn", "h": "On while USD/CNY is below its average (the yuan is firm); both halves need it"},
            {"k": f"Trend · {p['trend_symbol']} Supertrend {p['st_atr']}/{p['st_mult']:g}", "v": f"{'up' if last['st_up'] > 0.5 else 'down'} · "
             f"{last['a_c']:,.2f} vs line {last['st_line']:,.2f}", "cls": "up" if last["st_up"] > 0.5 else "dn"},
            {"k": f"Trend gate · {p['gate_symbol']} vs SMA{p['fxi_ma']}", "v": f"{last['f_c']:,.2f} vs {last['f_ma']:,.2f} · "
             f"{(last['f_c'] / last['f_ma'] - 1) * 100:+.1f}%", "cls": "up" if last["f_c"] > last["f_ma"] else "dn"},
            {"k": f"Dip · {p['trade']} IBS", "v": f"{last['ibs']:.2f}" + (" · dip open" if last["dip"] else ""),
             "cls": "warn" if last["ibs"] < float(p["dip_ibs_max"]) else "",
             "h": f"Starts below {p['dip_ibs_max']:g} while {p['dip_symbol']} is above SMA{p['dip_ma']} and credit is healthy; ends above "
                  f"{p['exit_ibs']:g} or after {p['dip_days']} closes"},
            {"k": f"Dip gate · {p['dip_symbol']} vs SMA{p['dip_ma']}", "v": f"{(last['dip_c'] / last['dip_ma'] - 1) * 100:+.1f}%",
             "cls": "up" if last["dip_c"] > last["dip_ma"] else "dn"},
            {"k": f"Dip gate · credit LQD ÷ IEF vs SMA{p['credit_ma']}", "v": f"{last['credit_pct']:+.2f}%", "cls": "up" if last["credit"] else "dn"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open"}]
        tiles = [{"k": "both", "title": "In · both halves", "text": "Trend on and a dip open, yuan firm", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["both"]},
                 {"k": "trend", "title": "In · trend half", "text": f"{p['trend_symbol']} Supertrend up, {p['gate_symbol']} above SMA{p['fxi_ma']}",
                  "hold": f"{p['trend_pct']:g}% {p['trade']}", "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip half", "text": f"{p['trade']} IBS < {p['dip_ibs_max']:g}, up to {p['dip_days']} closes",
                  "hold": f"{p['dip_pct']:g}% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "out", "title": "Out", "text": "No trend, no dip (or the yuan filter is off)", "hold": "cash", "color": STATE_COLOR["out"]}]

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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "ibs": num(r["ibs"]), "st": "up" if r["st_up"] > 0.5 else "down",
                             "fxi": num((r["f_c"] / r["f_ma"] - 1) * 100), "yuan": "on" if r["yuan"] else "off",
                             "credit": "ok" if r["credit"] else "weak", "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "ibs", "label": "IBS", "fmt": "n2"},
                    {"k": "st", "label": f"{p['trend_symbol']} ST"}, {"k": "fxi", "label": f"{p['gate_symbol']} vs SMA{p['fxi_ma']} %", "fmt": "n1"},
                    {"k": "yuan", "label": "Yuan"}, {"k": "credit", "label": "Credit"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = f"IN · {pct}% {p['trade']} · {STATE_TEXT[s]}" if pct > 0 else f"OUT · cash" + (" (yuan filter off)" if s == "yuan_off" else "")
        return {"ok": True, "state": s, "label": label, "target": self.target_w(last["w"]),
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": num(last["t_c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": num(last["t_c"]), "state_text": STATE_TEXT[s], "title": "Position · decided after each US close"}}

    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0, mask=None):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) and (mask is None or mask[i]) else {"time": t[i]}
                    for i in range(len(t))]

        w = fr["w"].values
        markers = []
        for i in range(1, len(fr)):
            if w[i] > w[i - 1] + 1e-9:
                markers.append({"time": t[i], "position": "belowBar", "color": "#2962FF", "shape": "arrowUp", "text": f"→ {w[i] * 100:.0f}%"})
            elif w[i] < w[i - 1] - 1e-9:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#E040FB", "shape": "arrowDown", "text": f"→ {w[i] * 100:.0f}%"})
        a = md.daily_closed(p["trend_symbol"], now)
        a = HkCrashStrategy.dividend_adjusted(p["trend_symbol"], a[~a.index.duplicated(keep="last")]).reindex(fr.index)
        up = fr["st_up"].values > 0.5
        fr = fr.assign(fxi_pct=(fr["f_c"] / fr["f_ma"] - 1) * 100, cny_pct=(fr["cny"] / fr["cny_ma"] - 1) * 100)
        sig = {"id": "signal", "title": f"{p['trend_symbol']} · 1D", "subtitle": "Signal — the trend half's Supertrend (dividends added back)",
               "candles": [{"time": t[i], "open": round(float(a["o"].iloc[i]), 4), "high": round(float(a["h"].iloc[i]), 4),
                            "low": round(float(a["l"].iloc[i]), 4), "close": round(float(a["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": "Supertrend up", "color": "#26A69A", "width": 2, "data": ln("st_line", 4, 1.0, up)},
                         {"name": "Supertrend down", "color": "#EF5350", "width": 2, "data": ln("st_line", 4, 1.0, ~up)}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": [{"id": "fxi", "title": f"{p['gate_symbol']} % vs its {p['fxi_ma']}-day average (trend gate)", "height": 60,
                          "lines": [{"name": p["gate_symbol"], "color": "#E03131", "width": 1, "data": ln("fxi_pct", 2)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "yuan", "title": f"USD/CNY % vs its {p['yuan_ma']}-day average (below 0 = yuan filter on)", "height": 60,
                          "lines": [{"name": "USD/CNY", "color": "#8E6CC8", "width": 1, "data": ln("cny_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "credit", "title": f"Credit · LQD ÷ IEF, % vs its {p['credit_ma']}-day average (dip gate)", "height": 60,
                          "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("credit_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                          "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}],
               "markers": markers, "tv": tv_url(p["trend_symbol"]), "tv_symbol": TV.get(p["trend_symbol"], p["trend_symbol"])}
        trd = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — dips are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['dip_ma']} (dividends added back)", "color": "#FF9800", "width": 1, "data": ln("dip_ma")}],
               "panes": [{"id": "ibs", "title": f"IBS · {p['trade']}", "height": 60, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                          "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}, {"value": float(p["exit_ibs"]), "label": f"exit > {p['exit_ibs']:g}"}]}],
               "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, trd], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close, only while USD/CNY's close is below its {p['yuan_ma']}-day average (the yuan is firm):",
            f"Trend half ({p['trend_pct']:g}%): hold {p['trade']} while {p['trend_symbol']}'s Supertrend ({p['st_atr']}, {p['st_mult']:g}) is up and "
            f"{p['gate_symbol']} is above its {p['fxi_ma']}-day average.",
            f"Dip half ({p['dip_pct']:g}%): after {p['trade']} closes with IBS < {p['dip_ibs_max']:g} while {p['dip_symbol']} is above its {p['dip_ma']}-day "
            f"average and LQD ÷ IEF is above its {p['credit_ma']}-day average; held until a close with IBS > {p['exit_ibs']:g} or {p['dip_days']} closes.",
            "Otherwise cash. Orders at the next open."],
            "flow": f"{p['trend_symbol']} + {p['gate_symbol']} + {p['trade']} + USD/CNY + LQD ÷ IEF daily → {p['trade']} · cash",
            "tv": f"{p['trend_symbol']} daily: Supertrend {p['st_atr']}/{p['st_mult']:g}; {p['gate_symbol']}: SMA {p['fxi_ma']}; {p['trade']}: SMA "
                  f"{p['dip_ma']}, IBS = (close − low) / (high − low); USDCNY: SMA {p['yuan_ma']}",
            "rule": f"Yuan firm → {p['trend_pct']:g}% while {p['trend_symbol']} ST{p['st_atr']}/{p['st_mult']:g} up & {p['gate_symbol']} > SMA{p['fxi_ma']}, "
                    f"+ {p['dip_pct']:g}% on IBS < {p['dip_ibs_max']:g} dips (credit ok); else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.read_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now)
        sym = p["trade"]
        tr = BT.daily_tr(sym).reindex(fr.index)
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
        return {"days": days, "eq": eq, "expo": expo, "trades": B.trades, "fees": B.fees, "state": states, "built": {},
                "bench": {sym: BT.daily_tr(sym), p["trend_symbol"]: BT.daily_tr(p["trend_symbol"])}, "rf": BT.daily_tr(BT.RF_SYMBOL),
                "main": sym, "index": p["trend_symbol"], "data_from": str(days[0]),
                "data_note": f"{sym}, {p['trend_symbol']}, {p['gate_symbol']}, LQD and IEF daily bars with dividends added back (signals); "
                             f"USD/CNY ({p['yuan']}) daily closes{', previous day' if int(p.get('yuan_lag', 0)) else ''}; {sym} daily total-return prices"}

    def check_table(self, now, rows=12):
        p = self.params
        fr = self.frame(now)
        a = md.daily_closed(p["trend_symbol"], now)
        a = HkCrashStrategy.dividend_adjusted(p["trend_symbol"], a[~a.index.duplicated(keep="last")])
        h, l, c = a["h"].values.astype(float), a["l"].values.astype(float), a["c"].values.astype(float)
        # independent Supertrend: plain-loop ATR (Wilder) and band ratchet
        n, m, k = len(c), float(p["st_mult"]), int(p["st_atr"])
        trr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
        atr = [None] * n
        atr[k - 1] = sum(trr[:k]) / k
        for i in range(k, n):
            atr[i] = (atr[i - 1] * (k - 1) + trr[i]) / k
        up_b = lo_b = None
        dirn = [None] * n
        for i in range(k - 1, n):
            mid = (h[i] + l[i]) / 2
            bu, bl = mid + m * atr[i], mid - m * atr[i]
            lo_b = bl if lo_b is None or bl > lo_b or c[i - 1] < lo_b else lo_b
            up_b = bu if up_b is None or bu < up_b or c[i - 1] > up_b else up_b
            if dirn[i - 1] is None:
                dirn[i] = "down"
            elif dirn[i - 1] == "down":
                dirn[i] = "up" if c[i] > up_b else "down"
            else:
                dirn[i] = "down" if c[i] < lo_b else "up"
        pos = {d: i for i, d in enumerate(a.index)}
        cols = [p["trend_symbol"], "Supertrend · bot / check", "IBS", "Held %"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            i = pos[d]
            bot = "up" if r["st_up"] > 0.5 else "down"
            good = bot == dirn[i]
            worst = max(worst, 0.0 if good else 1.0)
            out.append({"t": int(pd.Timestamp(d).timestamp()), "vals": [c[i], f"{bot} / {dirn[i]}", f"{r['ibs']:.3f}", float(r["w"] * 100)], "ok": bool(good)})
        return cols, out, worst
