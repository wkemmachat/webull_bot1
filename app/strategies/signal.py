"""Metals signal strategies on 4-hour COMEX futures bars (long only): Supertrend (optionally with an ADX
entry filter) and Donchian breakout. The ETF that is traded (e.g. UGL, AGQ) follows the futures signal.

Rules are evaluated on the CLOSE of a completed 4H bar (closing-basis stops), exactly like the research
and the Pine script in the Gold & Silver bot.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import indicators as ind
from .. import metals
from .base import StrategyBase, register

SYMBOLS = {"GC": "COMEX gold GC=F", "SI": "COMEX silver SI=F"}
TV_SYMBOL = {"GC": "COMEX:GC1!", "SI": "COMEX:SI1!"}
RANGE_BARS = {"2W": 72, "1M": 140, "3M": 400, "1Y": 1550}

COMMON = [
    {"key": "symbol", "label": "Futures signal", "kind": "select", "default": "GC", "options": ["GC", "SI"], "group": "Signal",
     "help": "GC = COMEX gold, SI = COMEX silver (Yahoo GC=F / SI=F, 4-hour bars)"},
    {"key": "etf", "label": "Trade with (ETF)", "kind": "symbol", "default": "UGL", "group": "Symbols",
     "help": "Held while the signal is long, e.g. UGL (2x gold), AGQ (2x silver), GLD, SLV"},
    {"key": "cash_etf", "label": "Cash ETF while flat", "kind": "symbol", "default": "SGOV", "group": "Symbols",
     "help": "T-bill ETF that holds the money while flat; empty = keep cash (the default since 26 Oct 2026: every switch "
             "then trades half as much at Webull's 0.107% fee, for no T-bill interest while flat)"},
    {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
    {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money",
     "help": "Between signals, trade only when a holding is this far from its target (e.g. after Add money)"},
]


class MetalsSignal(StrategyBase):
    family = "signal"
    timeframe = "4H"

    @property
    def sym(self):
        return self.params["symbol"]

    def data_needs(self):
        return [(self.sym, "1h")]

    def trade_symbols(self):
        return [s for s in (self.params["etf"], self.params["cash_etf"]) if s]

    def benchmark_symbol(self):
        return self.params["etf"]

    def cash_target(self):
        c = self.params["cash_etf"]
        return {c: round(1 - self.buffer(), 4)} if c else {}

    def warmup(self):
        return 60

    def compute(self, bars: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def next_check(self, now):
        ne = metals.next_bar_end(now)
        return ne + metals.delay_min() * 60 + 120 if ne else None

    # ---------------------------------------------------------------- evaluation
    def evaluate(self, now):
        se = metals.series(self.sym, now)
        adj4, raw4, factor = se["adj4"], se["raw4"], se["factor4"]
        if len(adj4) < self.warmup():
            return {"ok": False, "error": f"Not enough 4H bars yet ({len(adj4)})"}
        res = self.compute(adj4)
        want = res["want"].values
        n = len(want)
        f_last = float(factor.iloc[-1])
        ends = pd.to_datetime(raw4["end"], utc=True)
        long_ = bool(want[-1])
        k = n - 1
        while k > 0 and want[k - 1] == want[-1]:
            k -= 1
        target = {self.params["etf"]: round(1 - self.buffer(), 4)} if long_ else self.cash_target()
        close = float(raw4["c"].iloc[-1])
        checks = [{"k": "Close", "v": self.fmt(close)}] + self.check_rows(res, f_last, close, long_)
        hist = []
        for i in range(max(1, n - 400), n):
            if want[i] != want[i - 1]:
                fi = float(factor.iloc[i])
                hist.append({"t": int(ends.iloc[i].timestamp()), "kind": "BUY" if want[i] else "SELL",
                             "from": "long" if want[i - 1] else "flat", "to": "long" if want[i] else "flat",
                             "price": float(raw4["c"].iloc[i]), "text": self.reason(res, i, fi, raw4)})
        return {"ok": True, "state": "long" if long_ else "flat",
                "label": f"LONG · {self.params['etf']}" if long_ else f"FLAT · {self.params['cash_etf'] or 'cash'}",
                "target": target, "bar_time": int(ends.iloc[-1].timestamp()), "signal_time": int(ends.iloc[k].timestamp()),
                "price": close, "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"bars": n, "symbol": self.sym}}

    def fmt(self, x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "—"
        return f"{x:,.2f}" if self.sym == "GC" else f"{x:,.3f}"

    def check_rows(self, res, f, close, long_):
        return []

    def reason(self, res, i, f, raw4):
        return ""

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="1M"):
        se = metals.series(self.sym, now)
        adj4, raw4, factor = se["adj4"], se["raw4"], se["factor4"]
        if len(adj4) < self.warmup():
            return {"charts": [], "error": "Not enough data yet"}
        res = self.compute(adj4)
        nb = RANGE_BARS.get(rng, 140)
        s0 = max(0, len(adj4) - nb)
        f = factor.values
        times = [int(t.timestamp()) for t in raw4.index]
        candles = [{"time": times[i], "open": round(float(raw4["o"].iloc[i]), 3), "high": round(float(raw4["h"].iloc[i]), 3),
                    "low": round(float(raw4["l"].iloc[i]), 3), "close": round(float(raw4["c"].iloc[i]), 3)}
                   for i in range(s0, len(raw4))]
        want = res["want"].values
        markers = []
        for i in range(max(s0, 1), len(want)):
            if want[i] != want[i - 1]:
                buy = bool(want[i])
                markers.append({"time": times[i], "position": "belowBar" if buy else "aboveBar",
                                "color": "#2962FF" if buy else "#E040FB", "shape": "arrowUp" if buy else "arrowDown",
                                "text": "Buy" if buy else "Sell"})
        lines, panes = self.chart_lines(res, f, times, s0)
        return {"charts": [{"id": "signal", "title": f"{self.sym}=F · 4H · COMEX", "subtitle": SYMBOLS[self.sym],
                            "candles": candles, "lines": lines, "markers": markers, "panes": panes,
                            "tv": f"https://www.tradingview.com/chart/?symbol={TV_SYMBOL[self.sym].replace(':', '%3A').replace('!', '%21')}",
                            "tv_symbol": TV_SYMBOL[self.sym], "time_visible": True}]}

    def chart_lines(self, res, f, times, s0):
        return [], []


def _series(arr, f, times, s0, mask=None, digits=3):
    out = []
    for i in range(s0, len(arr)):
        v = arr[i]
        if v is None or np.isnan(v) or (mask is not None and not mask[i]):
            out.append({"time": times[i]})          # whitespace: a gap in the line
        else:
            out.append({"time": times[i], "value": round(float(v) / float(f[i]), digits)})
    return out


@register
class SupertrendStrategy(MetalsSignal):
    type = "supertrend"
    label = "Supertrend (optional ADX filter)"
    description = "Long while Supertrend is up on 4H futures bars. With ADX min > 0, buys only while ADX is above it."
    PARAMS = COMMON[:1] + [
        {"key": "atr", "label": "ATR period", "kind": "int", "default": 30, "min": 2, "max": 200, "group": "Rules"},
        {"key": "mult", "label": "Multiplier", "kind": "float", "default": 2.5, "min": 0.5, "max": 10, "group": "Rules"},
        {"key": "adx_min", "label": "ADX minimum to buy (0 = off)", "kind": "float", "default": 0, "min": 0, "max": 60, "group": "Rules",
         "help": "Gold #1 uses 20: buy only while the market is trending"},
        {"key": "adx_len", "label": "ADX length", "kind": "int", "default": 14, "min": 2, "max": 100, "group": "Rules"},
    ] + COMMON[1:]

    def warmup(self):
        return max(60, self.params["atr"] * 5 if self.params["atr"] <= 30 else self.params["atr"] * 3)

    def compute(self, bars):
        p = self.params
        o, h, l, c = (bars[k].values.astype(float) for k in ("o", "h", "l", "c"))
        st = ind.supertrend(h, l, c, p["atr"], p["mult"])
        out = pd.DataFrame(index=bars.index)
        out["c"] = c
        out["st_line"], out["st_up"], out["upper"], out["lower"] = st["line"], st["up"], st["upper"], st["lower"]
        up = st["up"]
        ready = ~np.isnan(st["atr"])
        n = len(c)
        want = np.zeros(n, dtype=int)
        if p["adx_min"] > 0:
            dm = ind.dmi(h, l, c, p["adx_len"], p["adx_len"])
            out["adx"], out["plus_di"], out["minus_di"] = dm["adx"], dm["plus_di"], dm["minus_di"]
            ready = ready & ~np.isnan(dm["adx"])
            cur = 0
            for i in range(n):
                if not ready[i]:
                    cur = 0
                elif cur == 1 and not up[i]:
                    cur = 0
                elif cur == 0 and up[i] and dm["adx"][i] > p["adx_min"]:
                    cur = 1
                want[i] = cur
        else:
            dm = ind.dmi(h, l, c, p["adx_len"], p["adx_len"])
            out["adx"], out["plus_di"], out["minus_di"] = dm["adx"], dm["plus_di"], dm["minus_di"]
            want = (up & ready).astype(int)
        out["want"] = want
        return out

    def check_rows(self, res, f, close, long_):
        p = self.params
        line = float(res["st_line"].iloc[-1]) / f
        up = bool(res["st_up"].iloc[-1])
        rows = [{"k": f"Supertrend({p['atr']}, {p['mult']:g})", "v": f"{self.fmt(line)} · {'up' if up else 'down'}",
                 "cls": "up" if up else "dn"}]
        if p["adx_min"] > 0:
            a = float(res["adx"].iloc[-1])
            rows.append({"k": f"ADX({p['adx_len']})", "v": f"{a:.2f} {'>' if a > p['adx_min'] else '≤'} {p['adx_min']:g}",
                         "cls": "up" if a > p["adx_min"] else ""})
        if long_:
            rows.append({"k": "Sell if a 4H close is below", "v": f"{self.fmt(line)} ({(line / close - 1) * 100:+.1f}%)"})
        elif up and p["adx_min"] > 0:
            rows.append({"k": "Buy when", "v": f"ADX rises above {p['adx_min']:g} while Supertrend stays up"})
        else:
            upper = float(res["upper"].iloc[-1]) / f
            rows.append({"k": "Buy if a 4H close is above", "v": f"{self.fmt(upper)} ({(upper / close - 1) * 100:+.1f}%)"})
        return rows

    def reason(self, res, i, f, raw4):
        c = self.fmt(float(raw4["c"].iloc[i]))
        line = self.fmt(float(res["st_line"].iloc[i - 1]) / f) if i > 0 else "—"
        if res["want"].iloc[i]:
            extra = f" · ADX {float(res['adx'].iloc[i]):.1f} > {self.params['adx_min']:g}" if self.params["adx_min"] > 0 else ""
            return f"4H close {c} above Supertrend {line}{extra}"
        return f"4H close {c} below Supertrend {line}"

    def chart_lines(self, res, f, times, s0):
        up = res["st_up"].values.astype(bool)
        line = res["st_line"].values
        lines = [{"name": f"Supertrend {self.params['atr']} {self.params['mult']:g} (up)", "color": "#26A69A", "width": 2,
                  "data": _series(line, f, times, s0, up)},
                 {"name": f"Supertrend {self.params['atr']} {self.params['mult']:g} (down)", "color": "#EF5350", "width": 2,
                  "data": _series(line, f, times, s0, ~up), "legend": False}]
        panes = []
        if self.params["adx_min"] > 0:
            one = np.ones(len(times))
            panes.append({"id": "adx", "title": f"ADX {self.params['adx_len']}", "height": 120,
                          "lines": [{"name": "ADX", "color": "#FF9800", "width": 2, "data": _series(res["adx"].values, one, times, s0, digits=2)},
                                    {"name": "+DI", "color": "#26A69A", "width": 1, "data": _series(res["plus_di"].values, one, times, s0, digits=2)},
                                    {"name": "−DI", "color": "#EF5350", "width": 1, "data": _series(res["minus_di"].values, one, times, s0, digits=2)}],
                          "hlines": [{"value": self.params["adx_min"], "label": f"{self.params['adx_min']:g} buy threshold"}]})
        return lines, panes

    def describe(self):
        p = self.params
        rules = [f"Indicator: Supertrend (ATR period {p['atr']}, multiplier {p['mult']:g}) on 4-hour {SYMBOLS[self.sym]} bars."]
        if p["adx_min"] > 0:
            rules += [f"Buy when a 4H bar closes with Supertrend up AND ADX({p['adx_len']}) above {p['adx_min']:g}.",
                      f"If Supertrend turns up while ADX is {p['adx_min']:g} or lower, wait for the first close with ADX above it."]
        else:
            rules += ["Buy when a 4H bar closes above the Supertrend line (it flips up)."]
        rules += ["Sell when a 4H bar closes below the Supertrend line.",
                  f"While long the money is in {p['etf']}; while flat in {p['cash_etf'] or 'cash'}."]
        tv = f'built-in "Supertrend" (ATR length {p["atr"]}, factor {p["mult"]:g})'
        if p["adx_min"] > 0:
            tv += f' and "ADX" (smoothing {p["adx_len"]}, DI length {p["adx_len"]})'
        return {"rules": rules, "flow": f"{self.sym}=F 4H → {p['etf']} · cash {p['cash_etf'] or '—'}", "tv": tv,
                "rule": (f"Buy when Supertrend({p['atr']}, {p['mult']:g}) is up and ADX({p['adx_len']}) > {p['adx_min']:g} · sell on a 4H close below the line"
                         if p["adx_min"] > 0 else f"Long while Supertrend({p['atr']}, {p['mult']:g}) is up · flat while it is down")}


@register
class DonchianStrategy(MetalsSignal):
    type = "donchian"
    label = "Donchian breakout"
    description = "Buy a 4H close above the highest high of the previous N bars, sell a close below the lowest low of the previous M bars."
    PARAMS = COMMON[:1] + [
        {"key": "entry", "label": "Breakout bars (buy)", "kind": "int", "default": 30, "min": 2, "max": 300, "group": "Rules"},
        {"key": "exit", "label": "Exit bars (sell)", "kind": "int", "default": 15, "min": 2, "max": 300, "group": "Rules"},
    ] + COMMON[1:]

    def warmup(self):
        return max(60, self.params["entry"] + 2)

    def compute(self, bars):
        ne, nx = self.params["entry"], self.params["exit"]
        h, l, c = (bars[k].values.astype(float) for k in ("h", "l", "c"))
        hh, ll = ind.highest_prev(h, ne), ind.lowest_prev(l, nx)
        out = pd.DataFrame(index=bars.index)
        out["c"], out["hh"], out["ll"] = c, hh, ll
        out["hh_next"], out["ll_next"] = ind.highest_incl(h, ne), ind.lowest_incl(l, nx)
        want = np.zeros(len(c), dtype=int)
        cur = 0
        for i in range(len(c)):
            if np.isnan(hh[i]) or np.isnan(ll[i]):
                cur = 0
            elif cur == 1 and c[i] < ll[i]:
                cur = 0
            elif cur == 0 and c[i] > hh[i]:
                cur = 1
            want[i] = cur
        out["want"] = want
        return out

    def check_rows(self, res, f, close, long_):
        p = self.params
        hn, ln = float(res["hh_next"].iloc[-1]) / f, float(res["ll_next"].iloc[-1]) / f
        rows = [{"k": f"{p['entry']}-bar high (buy above)", "v": self.fmt(hn), "cls": "up" if close >= hn else ""},
                {"k": f"{p['exit']}-bar low (sell below)", "v": f"{self.fmt(ln)} ({(ln / close - 1) * 100:+.1f}%)"}]
        return rows

    def reason(self, res, i, f, raw4):
        c = self.fmt(float(raw4["c"].iloc[i]))
        if res["want"].iloc[i]:
            return f"4H close {c} above {self.params['entry']}-bar high {self.fmt(float(res['hh'].iloc[i]) / f)}"
        return f"4H close {c} below {self.params['exit']}-bar low {self.fmt(float(res['ll'].iloc[i]) / f)}"

    def chart_lines(self, res, f, times, s0):
        p = self.params
        return [{"name": f"{p['entry']}-bar high (buy above)", "color": "#2962FF", "width": 2, "data": _series(res["hh"].values, f, times, s0)},
                {"name": f"{p['exit']}-bar low (sell below)", "color": "#FF6D00", "width": 2, "data": _series(res["ll"].values, f, times, s0)}], []

    def describe(self):
        p = self.params
        return {"rules": [f"Channel: highest high of the previous {p['entry']} 4H bars and lowest low of the previous {p['exit']}.",
                          f"Buy when a 4H bar closes above the {p['entry']}-bar high (a breakout).",
                          f"Sell when a 4H bar closes below the {p['exit']}-bar low.",
                          f"While long the money is in {p['etf']}; while flat in {p['cash_etf'] or 'cash'}."],
                "flow": f"{self.sym}=F 4H → {p['etf']} · cash {p['cash_etf'] or '—'}",
                "tv": f'built-in "Donchian Channels" (length {p["entry"]}, and a second copy with length {p["exit"]})',
                "rule": f"Buy a 4H close above the {p['entry']}-bar high · sell a close below the {p['exit']}-bar low"}


def utcnow():
    return datetime.now(timezone.utc)
