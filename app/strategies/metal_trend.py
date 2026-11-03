"""Metals: slow 4-hour Supertrend + daily trend filter + calm-market gate + RSI(2) dip buys (gold challenger G1,
research "Gold & Silver Challengers", 3 Nov 2026).

Long the ETF (UGL) when
  * trend: the 4H futures Supertrend is up, AND the futures' last daily close is above its daily SMA, AND the market is
    calm (the standard deviation of the last `vol_days` daily log changes is at or below its `vol_q`-th percentile over
    the last `vol_lookback` days, today included);
  * OR an RSI(2) dip trade is open: opened on a daily close with RSI(2) below `rsi_buy` while the close is above its
    SMA(`dip_ma`), closed on the first daily close above its SMA(`exit_ma`).
Cash otherwise.

Daily bars are built from the same roll-adjusted 4H bars (a session runs 18:00-17:00 New York). A session's daily close
is known when its 14:00-17:00 bar closes (or, on a short holiday session, at the first bar of the next session), so the
rule is the same live and in the backtest. Everything is decided on a 4H close and traded with the metals execution
settings (buys from 22:00 Bangkok, sells as soon as the US market is open), like Gold #1 and Gold #2.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as ind
from .. import metals
from .base import register
from .signal import COMMON, SYMBOLS, MetalsSignal, _series

NY = "America/New_York"


def daily_from_4h(bars: pd.DataFrame):
    """Session closes from 4H bars and, for every 4H bar, the index of the last session known at its close (-1: none)."""
    ny = bars.index.tz_convert(NY)
    hr = np.asarray(ny.hour)
    sess = np.asarray((ny + pd.Timedelta(hours=6)).normalize().tz_localize(None).values.astype("datetime64[D]").astype(np.int64))
    c = bars["c"].values.astype(float)
    closes, days, known = [], [], np.full(len(c), -1, dtype=int)
    pend = None                                   # (session, close) of a session not yet complete
    for i in range(len(c)):
        if pend is not None and sess[i] != pend[0]:
            closes.append(pend[1])                # a short session ended without its 14:00 bar
            days.append(pend[0])
            pend = None
        if hr[i] == 14:
            closes.append(c[i])
            days.append(sess[i])
            pend = None
        else:
            pend = (sess[i], c[i])
        known[i] = len(closes) - 1
    return np.array(closes, dtype=float), np.array(days, dtype=np.int64), known


def daily_rules(dc: np.ndarray, p: dict) -> dict:
    """Daily filter, calm gate and RSI(2) dip state on the session closes."""
    s = pd.Series(dc)
    out = {}
    if p["daily_ma"] > 0:
        ma = s.rolling(p["daily_ma"]).mean().values
        out["ma"] = ma
        out["flt"] = np.where(np.isnan(ma), True, dc > ma)
    else:
        out["ma"] = np.full(len(dc), np.nan)
        out["flt"] = np.ones(len(dc), bool)
    if p["vol_q"] > 0:
        v = np.log(s).diff().rolling(p["vol_days"]).std()
        thr = v.rolling(p["vol_lookback"], min_periods=p["vol_lookback"]).quantile(p["vol_q"] / 100.0)
        out["vol"], out["thr"] = v.values * math.sqrt(252), thr.values * math.sqrt(252)
        out["calm"] = np.where(thr.isna().values, True, (v <= thr).values)
    else:
        out["vol"] = out["thr"] = np.full(len(dc), np.nan)
        out["calm"] = np.ones(len(dc), bool)
    r = ind.rsi(dc, p["rsi_len"]) if len(dc) > p["rsi_len"] else np.full(len(dc), np.nan)
    dma = s.rolling(p["dip_ma"]).mean().values
    ema = s.rolling(p["exit_ma"]).mean().values
    out["rsi"], out["dip_ma"], out["exit_ma"] = r, dma, ema
    dip = np.zeros(len(dc), bool)
    if p["rsi_buy"] > 0:
        cur = False
        with np.errstate(invalid="ignore"):
            ent = np.nan_to_num((r < p["rsi_buy"]) & (dc > dma)).astype(bool)
            ext = np.nan_to_num(dc > ema).astype(bool)
        for i in range(len(dc)):
            if cur and ext[i]:
                cur = False
            elif not cur and ent[i]:
                cur = True
            dip[i] = cur
    out["dip"] = dip
    return out


@register
class TrendCalmDipStrategy(MetalsSignal):
    type = "metal_trend_calm"
    label = "Supertrend + daily trend, calm market & RSI(2) dips"
    description = ("Long while the 4H futures Supertrend is up, the daily close is above its SMA and the market is calm, "
                   "plus RSI(2) dip trades on daily closes.")
    PARAMS = COMMON[:1] + [
        {"key": "atr", "label": "Supertrend ATR period (4H)", "kind": "int", "default": 150, "min": 2, "max": 400, "group": "Rules"},
        {"key": "mult", "label": "Supertrend multiplier", "kind": "float", "default": 4.0, "min": 0.5, "max": 10, "group": "Rules"},
        {"key": "daily_ma", "label": "Daily trend filter: SMA days (0 = off)", "kind": "int", "default": 50, "min": 0, "max": 400,
         "group": "Rules", "help": "The trend part buys only while the last daily close is above this average"},
        {"key": "vol_q", "label": "Calm market: percentile (0 = off)", "kind": "float", "default": 80.0, "min": 0, "max": 100,
         "group": "Rules", "help": "The trend part holds only while daily volatility is at or below this percentile of its own last year"},
        {"key": "vol_days", "label": "Volatility: days", "kind": "int", "default": 20, "min": 5, "max": 120, "group": "Rules"},
        {"key": "vol_lookback", "label": "Volatility: lookback days", "kind": "int", "default": 252, "min": 60, "max": 1000, "group": "Rules"},
        {"key": "rsi_len", "label": "RSI length (dips)", "kind": "int", "default": 2, "min": 2, "max": 30, "group": "Dips"},
        {"key": "rsi_buy", "label": "Buy a dip when daily RSI is below (0 = no dips)", "kind": "float", "default": 5.0, "min": 0,
         "max": 50, "group": "Dips"},
        {"key": "dip_ma", "label": "Dips only above SMA (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Dips"},
        {"key": "exit_ma", "label": "Sell a dip on a close above SMA (days)", "kind": "int", "default": 5, "min": 2, "max": 50, "group": "Dips"},
    ] + COMMON[1:]

    def warmup(self):
        p = self.params
        days = max(p["daily_ma"], p["dip_ma"], (p["vol_lookback"] + p["vol_days"]) if p["vol_q"] > 0 else 0) + 5
        return max(60, p["atr"] * 3, days * 6)

    def compute(self, bars):
        p = self.params
        h, l, c = (bars[k].values.astype(float) for k in ("h", "l", "c"))
        st = ind.supertrend(h, l, c, p["atr"], p["mult"])
        out = pd.DataFrame(index=bars.index)
        out["c"] = c
        out["st_line"], out["upper"], out["lower"] = st["line"], st["upper"], st["lower"]
        up = st["up"] & ~np.isnan(st["atr"])
        out["st_up"] = up
        dc, _, known = daily_from_4h(bars)
        d = daily_rules(dc, p)
        ok = known >= 0
        k = np.clip(known, 0, None)

        def at(name, fill):
            a = d[name]
            if len(a) == 0:
                return np.full(len(c), fill)
            return np.where(ok, a[k], fill)
        out["d_close"] = np.where(ok, dc[k], np.nan) if len(dc) else np.full(len(c), np.nan)
        out["d_ma"], out["d_vol"], out["d_thr"] = at("ma", np.nan), at("vol", np.nan), at("thr", np.nan)
        out["d_rsi"], out["d_dip_ma"], out["d_exit_ma"] = at("rsi", np.nan), at("dip_ma", np.nan), at("exit_ma", np.nan)
        flt = at("flt", False).astype(bool)
        calm = at("calm", False).astype(bool)
        dip = at("dip", False).astype(bool)
        trend = up & flt & calm
        out["flt"], out["calm"], out["dip"], out["trend"] = flt, calm, dip, trend
        out["want"] = (trend | dip).astype(int)
        return out

    # ---------------------------------------------------------------- words
    def _why_on(self, r):
        p = self.params
        if r["trend"]:
            return f"Trend: Supertrend({p['atr']}, {p['mult']:g}) up, daily close above SMA{p['daily_ma']}, calm market"
        return f"RSI({p['rsi_len']}) dip trade (until a daily close above SMA{p['exit_ma']})"

    def _why_off(self, r):
        p = self.params
        bits = []
        if not r["st_up"]:
            bits.append(f"Supertrend({p['atr']}, {p['mult']:g}) down")
        if p["daily_ma"] > 0 and not r["flt"]:
            bits.append(f"daily close below SMA{p['daily_ma']}")
        if p["vol_q"] > 0 and not r["calm"]:
            bits.append(f"volatility above its {p['vol_q']:g}th percentile")
        return ", ".join(bits) or "no trend and no dip trade"

    def check_rows(self, res, f, close, long_):
        p = self.params
        r = res.iloc[-1]
        line = float(r["st_line"]) / f
        up = bool(r["st_up"])
        rows = [{"k": f"Supertrend({p['atr']}, {p['mult']:g}) · 4H", "v": f"{self.fmt(line)} · {'up' if up else 'down'}",
                 "cls": "up" if up else "dn"}]
        if p["daily_ma"] > 0:
            dcl, dma = float(r["d_close"]) / f, float(r["d_ma"]) / f
            rows.append({"k": f"Daily close vs SMA{p['daily_ma']}", "v": f"{self.fmt(dcl)} {'>' if r['flt'] else '≤'} {self.fmt(dma)}",
                         "cls": "up" if r["flt"] else "dn"})
        if p["vol_q"] > 0:
            v, t = float(r["d_vol"]), float(r["d_thr"])
            rows.append({"k": f"Calm: {p['vol_days']}-day volatility vs {p['vol_q']:g}th pct",
                         "v": f"{v * 100:.1f}% {'≤' if r['calm'] else '>'} {t * 100:.1f}%" if t == t and v == v else "—",
                         "cls": "up" if r["calm"] else "dn"})
        if p["rsi_buy"] > 0:
            rv = float(r["d_rsi"])
            rows.append({"k": f"RSI({p['rsi_len']}) daily", "v": (f"{rv:.1f} · dip trade open" if r["dip"] else f"{rv:.1f}"),
                         "cls": "up" if r["dip"] else ""})
        if long_:
            if r["trend"]:
                rows.append({"k": "Trend part ends if", "v": f"a 4H close is below {self.fmt(line)} ({(line / close - 1) * 100:+.1f}%), "
                             f"a daily close is below SMA{p['daily_ma']}, or volatility rises above its {p['vol_q']:g}th percentile"})
            if r["dip"]:
                rows.append({"k": "Dip trade ends on", "v": f"a daily close above SMA{p['exit_ma']} ({self.fmt(float(r['d_exit_ma']) / f)})"})
        else:
            rows.append({"k": "Buys when", "v": f"all three trend checks are green, or daily RSI({p['rsi_len']}) closes below "
                         f"{p['rsi_buy']:g} while above SMA{p['dip_ma']} ({self.fmt(float(r['d_dip_ma']) / f)})"})
        return rows

    def reason(self, res, i, f, raw4):
        r = res.iloc[i]
        c = self.fmt(float(raw4["c"].iloc[i]))
        if res["want"].iloc[i]:
            return f"4H close {c} · " + self._why_on(r)
        why = self._why_off(r)
        if i > 0 and res["dip"].iloc[i - 1] and not r["dip"]:
            why = f"dip trade ended (daily close above SMA{self.params['exit_ma']}); trend part off: {why}"
        return f"4H close {c} · " + why

    def chart_lines(self, res, f, times, s0):
        p = self.params
        up = res["st_up"].values.astype(bool)
        line = res["st_line"].values
        lines = [{"name": f"Supertrend {p['atr']} {p['mult']:g} (up)", "color": "#26A69A", "width": 2, "data": _series(line, f, times, s0, up)},
                 {"name": f"Supertrend {p['atr']} {p['mult']:g} (down)", "color": "#EF5350", "width": 2,
                  "data": _series(line, f, times, s0, ~up), "legend": False}]
        if p["daily_ma"] > 0:
            lines.append({"name": f"Daily SMA{p['daily_ma']}", "color": "#FF9800", "width": 1, "data": _series(res["d_ma"].values, f, times, s0)})
        panes = []
        if p["vol_q"] > 0:
            one = np.ones(len(times))
            panes.append({"id": "vol", "title": f"Daily volatility (% a year) vs its {p['vol_q']:g}th percentile", "height": 110,
                          "lines": [{"name": "Volatility", "color": "#5B8DEF", "width": 2, "data": _series(res["d_vol"].values * 100, one, times, s0, digits=2)},
                                    {"name": f"{p['vol_q']:g}th percentile", "color": "#999999", "width": 1,
                                     "data": _series(res["d_thr"].values * 100, one, times, s0, digits=2)}]})
        if p["rsi_buy"] > 0:
            one = np.ones(len(times))
            panes.append({"id": "rsi", "title": f"RSI({p['rsi_len']}) daily", "height": 90,
                          "lines": [{"name": "RSI", "color": "#B084F5", "width": 1, "data": _series(res["d_rsi"].values, one, times, s0, digits=1)}],
                          "hlines": [{"value": p["rsi_buy"], "label": f"{p['rsi_buy']:g} dip level"}]})
        return lines, panes

    def describe(self):
        p = self.params
        rules = [f"Trend: long while the 4-hour {SYMBOLS[self.sym]} Supertrend (ATR {p['atr']}, multiplier {p['mult']:g}) is up"
                 + (f", the last daily close is above its {p['daily_ma']}-day average" if p["daily_ma"] > 0 else "")
                 + (f", and the market is calm: the {p['vol_days']}-day volatility of daily changes is at or below its "
                    f"{p['vol_q']:g}th percentile of the last {p['vol_lookback']} days" if p["vol_q"] > 0 else "") + "."]
        if p["rsi_buy"] > 0:
            rules.append(f"Dips: a daily close with RSI({p['rsi_len']}) below {p['rsi_buy']:g} while above its {p['dip_ma']}-day "
                         f"average opens a dip trade; it ends on the first daily close above the {p['exit_ma']}-day average.")
        rules += [f"While either is on, the money is in {p['etf']}; otherwise in {p['cash_etf'] or 'cash'}.",
                  "Daily closes are the futures' session closes (17:00 New York), known when that 4H bar closes."]
        tv = (f'4H: built-in "Supertrend" (ATR length {p["atr"]}, factor {p["mult"]:g}); daily: "Moving Average" {p["daily_ma"]}, '
              f'{p["dip_ma"]} and {p["exit_ma"]}, "Relative Strength Index" {p["rsi_len"]}')
        return {"rules": rules, "flow": f"{self.sym}=F 4H + daily → {p['etf']} · cash {p['cash_etf'] or '—'}", "tv": tv,
                "rule": f"Supertrend({p['atr']}, {p['mult']:g}) up + daily > SMA{p['daily_ma']} + calm, or RSI({p['rsi_len']}) < {p['rsi_buy']:g} dips"}

    # ---------------------------------------------------------------- health check: the long way
    def check_table(self, now, rows=12):
        from ..health import ref_supertrend
        p = self.params
        se = metals.series(self.sym, now)
        adj4, raw4, f = se["adj4"], se["raw4"], se["factor4"].values
        res = self.compute(adj4)
        h, l, c = (adj4[k].values.astype(float).tolist() for k in ("h", "l", "c"))
        line, upr = ref_supertrend(h, l, c, p["atr"], p["mult"])
        # daily closes the long way: the 14:00 New York bar's close, or the last bar of a session that ended early
        ny = adj4.index.tz_convert(NY)
        sess = [(t + pd.Timedelta(hours=6)).date() for t in ny]
        dcl, known, pend = [], [], None
        for i in range(len(c)):
            if pend is not None and sess[i] != pend[0]:
                dcl.append(pend[1])
                pend = None
            if ny[i].hour == 14:
                dcl.append(c[i])
                pend = None
            else:
                pend = (sess[i], c[i])
            known.append(len(dcl) - 1)
        n = len(dcl)
        L = p["daily_ma"]
        ma = [sum(dcl[j - L + 1:j + 1]) / L if L > 0 and j >= L - 1 else float("nan") for j in range(n)]
        lg = [float("nan")] + [math.log(dcl[j] / dcl[j - 1]) for j in range(1, n)]
        vd, lb, q = p["vol_days"], p["vol_lookback"], p["vol_q"]
        sd = [float("nan")] * n
        for j in range(vd, n):
            w = lg[j - vd + 1:j + 1]
            m = sum(w) / vd
            sd[j] = (sum((x - m) ** 2 for x in w) / (vd - 1)) ** 0.5
        calm = [True] * n
        if q > 0:
            for j in range(n):
                win = sd[j - lb + 1:j + 1] if j >= lb - 1 else []
                if len(win) < lb or any(x != x for x in win):
                    calm[j] = True                     # not enough history: the gate is open (as in the research)
                    continue
                srt = sorted(win)
                pos = (len(srt) - 1) * q / 100.0
                lo = int(pos)
                hi = min(lo + 1, len(srt) - 1)
                calm[j] = sd[j] == sd[j] and sd[j] <= srt[lo] + (srt[hi] - srt[lo]) * (pos - lo)
        cols = ["Close", "Supertrend · bot", "Supertrend · check", f"Daily SMA{L} · bot", f"Daily SMA{L} · check", "Calm · bot",
                "Calm · check", "Signal · bot", "Signal · check"]
        out, mx = [], 0.0
        ends = pd.to_datetime(raw4["end"], utc=True)
        for i in range(max(0, len(c) - rows), len(c)):
            j = known[i]
            a, b = float(res["st_line"].iloc[i]) / f[i], line[i] / f[i]
            ma_b = float(res["d_ma"].iloc[i]) / f[i]
            ma_c = (ma[j] / f[i]) if j >= 0 and ma[j] == ma[j] else float("nan")
            calm_c = calm[j] if j >= 0 else False
            flt_c = (dcl[j] > ma[j]) if (j >= 0 and ma[j] == ma[j]) else j >= 0
            trend_c = bool(upr[i]) and flt_c and calm_c
            sig_c = 1 if (trend_c or bool(res["dip"].iloc[i])) else 0
            diff = abs(a - b) / max(abs(a), 1e-9)
            if ma_b == ma_b and ma_c == ma_c:
                diff = max(diff, abs(ma_b - ma_c) / max(abs(ma_c), 1e-9))
            same = (bool(res["calm"].iloc[i]) == calm_c) and (int(res["want"].iloc[i]) == sig_c)
            if not same:
                diff = max(diff, 1.0)
            mx = max(mx, diff)
            out.append({"t": int(ends.iloc[i].timestamp()),
                        "vals": [float(raw4["c"].iloc[i]), a, b, ma_b, ma_c, "calm" if res["calm"].iloc[i] else "jumpy",
                                 "calm" if calm_c else "jumpy", "long" if res["want"].iloc[i] else "flat", "long" if sig_c else "flat"],
                        "ok": diff < 1e-6})
        return cols, out, mx


# ---------------------------------------------------------------- silver challengers S1 / S3: sized, gold-confirmed, 1x fallback
def _align(end_from: pd.Series, end_to: pd.Series) -> np.ndarray:
    """For each bar of `end_to`, the index of the last bar of `end_from` that had closed by then (-1: none)."""
    a = pd.to_datetime(end_from, utc=True).values.astype("datetime64[ns]").astype(np.int64)
    b = pd.to_datetime(end_to, utc=True).values.astype("datetime64[ns]").astype(np.int64)
    return np.searchsorted(a, b, side="right") - 1


@register
class TrendSizedStrategy(MetalsSignal):
    """Long the 2x ETF while the metal's 4H Supertrend is up and the checks pass, sized by volatility:
    weight = min(99%, target volatility ÷ (2 × the metal's daily volatility)). Optional checks: gold's own 4H Supertrend up
    (silver only with gold's OK), the daily close above its SMA, the gold/silver ratio below its SMA (silver leading).
    Trend up but a check fails: the 1x ETF if one is set, else cash. Trend down: cash."""
    type = "metal_trend_sized"
    label = "Supertrend sized by volatility, with gold's OK, trend and ratio checks"
    description = ("Long the 2x ETF while the 4H Supertrend is up and the optional checks pass (gold's own trend, daily SMA, "
                   "gold/silver ratio), sized by volatility; the 1x ETF or cash when a check fails.")
    PARAMS = COMMON[:1] + [
        {"key": "atr", "label": "Supertrend ATR period (4H)", "kind": "int", "default": 40, "min": 2, "max": 400, "group": "Rules"},
        {"key": "mult", "label": "Supertrend multiplier", "kind": "float", "default": 2.5, "min": 0.5, "max": 10, "group": "Rules"},
        {"key": "gold_confirm", "label": "Only while gold's 4H Supertrend is up", "kind": "bool", "default": False, "group": "Checks",
         "help": "Silver trades only with gold's OK (gold's Supertrend below, the same as Gold #2's signal)"},
        {"key": "gold_atr", "label": "Gold Supertrend ATR period", "kind": "int", "default": 30, "min": 2, "max": 400, "group": "Checks"},
        {"key": "gold_mult", "label": "Gold Supertrend multiplier", "kind": "float", "default": 2.5, "min": 0.5, "max": 10, "group": "Checks"},
        {"key": "daily_ma", "label": "Daily close above SMA (days, 0 = off)", "kind": "int", "default": 0, "min": 0, "max": 400, "group": "Checks"},
        {"key": "gsr_ma", "label": "Gold/silver ratio below its SMA (days, 0 = off)", "kind": "int", "default": 0, "min": 0, "max": 400,
         "group": "Checks", "help": "Silver leading gold: the ratio of gold's to silver's daily close is below its own average"},
        {"key": "one_x_etf", "label": "When a check fails, hold (1x ETF)", "kind": "symbol", "default": "", "group": "Symbols",
         "help": "e.g. SLV; empty = cash while a check fails"},
        {"key": "target_vol_pct", "label": "Target volatility % (0 = full size)", "kind": "float", "default": 70.0, "min": 0, "max": 200,
         "group": "Size", "help": "2x ETF weight = this ÷ (2 × the metal's daily volatility), at most 99%"},
        {"key": "size_vol_days", "label": "Volatility days (size)", "kind": "int", "default": 40, "min": 5, "max": 250, "group": "Size"},
        {"key": "size_band_pct", "label": "Resize only when the size moves more than (%)", "kind": "float", "default": 10.0, "min": 0,
         "max": 100, "group": "Size", "help": "Relative to the size held, e.g. 10: a 60% position is resized below 54% or above 66%"},
    ] + COMMON[1:]

    def data_needs(self):
        out = [(self.sym, "1h")]
        if (self.params["gold_confirm"] or self.params["gsr_ma"] > 0) and self.sym != "GC":
            out.append(("GC", "1h"))
        return out

    def trade_symbols(self):
        return [s for s in (self.params["etf"], self.params["one_x_etf"], self.params["cash_etf"]) if s]

    def warmup(self):
        p = self.params
        days = max(p["daily_ma"], p["gsr_ma"], p["size_vol_days"] if p["target_vol_pct"] > 0 else 0) + 5
        return max(60, p["atr"] * 3, days * 6)

    def _needs_gold(self):
        p = self.params
        return (p["gold_confirm"] or p["gsr_ma"] > 0) and self.sym != "GC"

    def _gold(self, now=None):
        from .. import marketdata as md
        return metals.series("GC", now or md.now_utc())["adj4"]

    def compute(self, bars, gold=None):
        p = self.params
        h, l, c = (bars[k].values.astype(float) for k in ("h", "l", "c"))
        n = len(c)
        st = ind.supertrend(h, l, c, p["atr"], p["mult"])
        up = st["up"] & ~np.isnan(st["atr"])
        out = pd.DataFrame(index=bars.index)
        out["c"] = c
        out["st_line"], out["upper"], out["lower"], out["st_up"] = st["line"], st["upper"], st["lower"], up
        dc, days, known = daily_from_4h(bars)
        ok_d = known >= 0
        k = np.clip(known, 0, None)
        s = pd.Series(dc, dtype=float)
        at = lambda a, fill: np.where(ok_d, a[k], fill) if len(a) else np.full(n, fill)
        # daily close above its SMA
        if p["daily_ma"] > 0:
            ma = s.rolling(p["daily_ma"]).mean().values
            out["d_ma"] = at(ma, np.nan)
            ma_ok = at(np.where(np.isnan(ma), True, dc > ma), False).astype(bool)
        else:
            out["d_ma"] = np.nan
            ma_ok = np.ones(n, bool)
        # gold: its own 4H Supertrend, and its daily closes for the ratio
        gold_ok = np.ones(n, bool)
        gsr_ok = np.ones(n, bool)
        out["gold_up"], out["d_gsr"], out["d_gsr_ma"] = np.nan, np.nan, np.nan
        if p["gold_confirm"] or p["gsr_ma"] > 0:
            g = bars if self.sym == "GC" else (gold if gold is not None else self._gold())
            j = _align(g["end"], bars["end"]) if len(g) else np.full(n, -1)
            if p["gold_confirm"] and not len(g):
                gold_ok = np.zeros(n, bool)
                out["gold_up"] = gold_ok
            elif p["gold_confirm"]:
                gs = ind.supertrend(g.h.values.astype(float), g.l.values.astype(float), g.c.values.astype(float), p["gold_atr"], p["gold_mult"])
                gup = gs["up"] & ~np.isnan(gs["atr"])
                gold_ok = np.where(j >= 0, gup[np.clip(j, 0, None)], False).astype(bool)
                out["gold_up"] = gold_ok
            if p["gsr_ma"] > 0:
                gdc, gdays, _ = daily_from_4h(g)
                gmap = dict(zip(gdays.tolist(), gdc.tolist()))
                ratio = pd.Series([gmap.get(int(d), np.nan) for d in days], dtype=float) / s
                ratio = ratio.ffill()
                rma = ratio.rolling(p["gsr_ma"]).mean()
                out["d_gsr"], out["d_gsr_ma"] = at(ratio.values, np.nan), at(rma.values, np.nan)
                gsr_ok = at(np.where(rma.isna().values, True, (ratio < rma).values), False).astype(bool)
        # size from the metal's daily volatility (a 2x ETF moves twice as much)
        if p["target_vol_pct"] > 0:
            v = np.log(s).diff().rolling(p["size_vol_days"]).std().values * math.sqrt(252) * 2
            raw = np.where(np.isnan(v) | (v <= 0), 1.0, np.minimum(1.0, p["target_vol_pct"] / 100.0 / np.where(v > 0, v, 1)))
            out["d_vol2"] = at(v, np.nan)
            raw_b = at(raw, 1.0)
        else:
            out["d_vol2"] = np.nan
            raw_b = np.ones(n)
        checks = gold_ok & ma_ok & gsr_ok
        on2 = up & checks
        on1 = up & ~checks & bool(p["one_x_etf"])
        band = p["size_band_pct"] / 100.0
        size = np.zeros(n)
        held = 0.0
        for i in range(n):
            if on2[i]:
                r = float(raw_b[i])
                if held == 0.0 or abs(r - held) > band * held:
                    held = round(r, 2)
                size[i] = held
            else:
                held = 0.0
        out["gold_ok"], out["ma_ok"], out["gsr_ok"], out["checks"] = gold_ok, ma_ok, gsr_ok, checks
        out["raw_size"], out["size"], out["one_x"] = raw_b, size, on1
        out["want"] = (on2 | on1).astype(int)
        return out

    def bar_targets(self, res):
        p = self.params
        buf = 1 - self.buffer()
        out = []
        for sz, one in zip(res["size"].values, res["one_x"].values):
            if sz > 0:
                out.append({p["etf"]: round(buf * float(sz), 4)})
            elif one:
                out.append({p["one_x_etf"]: round(buf, 4)})
            else:
                out.append(dict(self.cash_target()))
        return out

    def _state(self, res, i):
        if res["size"].iloc[i] > 0:
            return f"{self.params['etf']} {res['size'].iloc[i] * 100:.0f}%"
        if res["one_x"].iloc[i]:
            return f"{self.params['one_x_etf']} 99%"
        return self.params["cash_etf"] or "cash"

    def evaluate(self, now):
        se = metals.series(self.sym, now)
        adj4, raw4, factor = se["adj4"], se["raw4"], se["factor4"]
        if len(adj4) < self.warmup():
            return {"ok": False, "error": f"Not enough 4H bars yet ({len(adj4)})"}
        gold = None
        if self._needs_gold():
            # gold's bar for the same 4 hours must be complete too (a late or missing GC hour must not decide on old gold)
            gold = self._gold(now)
            if not len(gold) or gold.index[-1] < adj4.index[-1]:
                last = pd.Timestamp(gold["end"].iloc[-1]).tz_convert("Asia/Bangkok").strftime("%d %b %H:%M") if len(gold) else "none"
                return {"ok": False, "error": f"Waiting for gold's 4H bar (GC last complete bar ends {last} Bangkok)"}
        res = self.compute(adj4, gold)
        if self.params["gsr_ma"] > 0 and self.sym != "GC" and res["d_gsr_ma"].iloc[-1] != res["d_gsr_ma"].iloc[-1]:
            return {"ok": False, "error": f"Not enough gold history yet for the gold/silver ratio's {self.params['gsr_ma']}-day average"}
        tg = self.bar_targets(res)
        n = len(tg)
        ends = pd.to_datetime(raw4["end"], utc=True)
        kk = n - 1
        while kk > 0 and tg[kk - 1] == tg[-1]:
            kk -= 1
        close = float(raw4["c"].iloc[-1])
        f_last = float(factor.iloc[-1])
        long_ = bool(res["want"].iloc[-1])
        checks = [{"k": "Close", "v": self.fmt(close)}] + self.check_rows(res, f_last, close, long_)
        hist = []
        for i in range(max(1, n - 400), n):
            if tg[i] != tg[i - 1]:
                a, b = tg[i - 1], tg[i]
                # BUY: from cash into a position · SELL: to cash · SIZE: resized, or switched between the 2x and 1x ETF
                was_in, now_in = bool(res["want"].iloc[i - 1]), bool(res["want"].iloc[i])
                kind = "SIZE" if (was_in and now_in) else ("BUY" if now_in else "SELL")
                hist.append({"t": int(ends.iloc[i].timestamp()), "kind": kind, "from": self._state(res, i - 1), "to": self._state(res, i),
                             "price": float(raw4["c"].iloc[i]), "text": self.reason(res, i, float(factor.iloc[i]), raw4)})
        lab = self._state(res, n - 1)
        return {"ok": True, "state": "long" if long_ else "flat", "label": ("LONG · " if long_ else "FLAT · ") + lab,
                "target": tg[-1], "bar_time": int(ends.iloc[-1].timestamp()), "signal_time": int(ends.iloc[kk].timestamp()),
                "price": close, "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"bars": n, "symbol": self.sym, "size": float(res["size"].iloc[-1])}}

    def signal_message(self, h):
        word = {"SIZE": "RESIZE", "BUY": "BUY", "SELL": "SELL"}.get(h["kind"], h["kind"])
        if h["kind"] == "SIZE" and h["from"].split(" ")[0] != h["to"].split(" ")[0]:
            word = "SWITCH"
        return f"{word} · {self.name}\n{h['text']}\n{h['from']} → {h['to']}"

    def _fails(self, r):
        p = self.params
        bits = []
        if p["gold_confirm"] and not r["gold_ok"]:
            bits.append(f"gold's Supertrend({p['gold_atr']}, {p['gold_mult']:g}) down")
        if p["daily_ma"] > 0 and not r["ma_ok"]:
            bits.append(f"daily close below SMA{p['daily_ma']}")
        if p["gsr_ma"] > 0 and not r["gsr_ok"]:
            bits.append(f"gold/silver ratio above its SMA{p['gsr_ma']}")
        return bits

    def reason(self, res, i, f, raw4):
        p = self.params
        r = res.iloc[i]
        c = self.fmt(float(raw4["c"].iloc[i]))
        st = f"Supertrend({p['atr']}, {p['mult']:g})"
        if r["size"] > 0:
            v = r["d_vol2"]
            sz = (f", size {r['size'] * 100:.0f}% = {p['target_vol_pct']:g}% ÷ {v * 100:.0f}% expected {p['etf']} volatility"
                  if p["target_vol_pct"] > 0 and v == v else "")
            return f"4H close {c} · {st} up, checks pass{sz}"
        if r["one_x"]:
            return f"4H close {c} · {st} up but {', '.join(self._fails(r))}: {p['one_x_etf']} instead"
        if not r["st_up"]:
            return f"4H close {c} · {st} down"
        return f"4H close {c} · {st} up but {', '.join(self._fails(r))}"

    def check_rows(self, res, f, close, long_):
        p = self.params
        r = res.iloc[-1]
        line = float(r["st_line"]) / f
        up = bool(r["st_up"])
        rows = [{"k": f"Supertrend({p['atr']}, {p['mult']:g}) · 4H", "v": f"{self.fmt(line)} · {'up' if up else 'down'}",
                 "cls": "up" if up else "dn"}]
        if p["gold_confirm"]:
            rows.append({"k": f"Gold's Supertrend({p['gold_atr']}, {p['gold_mult']:g})", "v": "up" if r["gold_ok"] else "down",
                         "cls": "up" if r["gold_ok"] else "dn"})
        if p["daily_ma"] > 0:
            rows.append({"k": f"Daily close vs SMA{p['daily_ma']}", "v": f"{'above' if r['ma_ok'] else 'below'} ({self.fmt(float(r['d_ma']) / f)})",
                         "cls": "up" if r["ma_ok"] else "dn"})
        if p["gsr_ma"] > 0:
            g, gm = float(r["d_gsr"]), float(r["d_gsr_ma"])
            rows.append({"k": f"Gold/silver ratio vs SMA{p['gsr_ma']}", "v": f"{g:.1f} {'<' if r['gsr_ok'] else '≥'} {gm:.1f}" if g == g and gm == gm else "—",
                         "cls": "up" if r["gsr_ok"] else "dn"})
        if p["target_vol_pct"] > 0:
            v = float(r["d_vol2"])
            rows.append({"k": "Size", "v": (f"{float(r['size']) * 100:.0f}% held · now {float(r['raw_size']) * 100:.0f}% "
                                            f"({p['target_vol_pct']:g}% ÷ {v * 100:.0f}%)" if v == v else "—")})
        if long_:
            rows.append({"k": "Sell if a 4H close is below", "v": f"{self.fmt(line)} ({(line / close - 1) * 100:+.1f}%)"})
        else:
            upper = float(r["upper"]) / f
            rows.append({"k": "Trend turns up on a 4H close above", "v": f"{self.fmt(upper)} ({(upper / close - 1) * 100:+.1f}%)"})
        return rows

    def chart_lines(self, res, f, times, s0):
        p = self.params
        up = res["st_up"].values.astype(bool)
        line = res["st_line"].values
        lines = [{"name": f"Supertrend {p['atr']} {p['mult']:g} (up)", "color": "#26A69A", "width": 2, "data": _series(line, f, times, s0, up)},
                 {"name": f"Supertrend {p['atr']} {p['mult']:g} (down)", "color": "#EF5350", "width": 2,
                  "data": _series(line, f, times, s0, ~up), "legend": False}]
        if p["daily_ma"] > 0:
            lines.append({"name": f"Daily SMA{p['daily_ma']}", "color": "#FF9800", "width": 1, "data": _series(res["d_ma"].values, f, times, s0)})
        one = np.ones(len(times))
        panes = [{"id": "size", "title": f"{p['etf']} size (% of the money)", "height": 90,
                  "lines": [{"name": "Size held", "color": "#5B8DEF", "width": 2, "data": _series(res["size"].values * 100, one, times, s0, digits=1)}]}]
        return lines, panes

    def describe(self):
        p = self.params
        checks = []
        if p["gold_confirm"]:
            checks.append(f"gold's own 4-hour Supertrend (ATR {p['gold_atr']}, multiplier {p['gold_mult']:g}) is up")
        if p["daily_ma"] > 0:
            checks.append(f"the last daily close is above its {p['daily_ma']}-day average")
        if p["gsr_ma"] > 0:
            checks.append(f"the gold/silver ratio (daily closes) is below its {p['gsr_ma']}-day average")
        rules = [f"Trend: the 4-hour {SYMBOLS[self.sym]} Supertrend (ATR {p['atr']}, multiplier {p['mult']:g}) is up."]
        if checks:
            rules.append("Checks: " + "; ".join(checks) + ".")
        size = (f"{p['etf']} weight = {p['target_vol_pct']:g}% ÷ (2 × the {p['size_vol_days']}-day volatility of daily changes), "
                f"at most 99%, resized only when it moves more than {p['size_band_pct']:g}%" if p["target_vol_pct"] > 0 else f"99% {p['etf']}")
        rules.append(f"Trend up and checks pass: {size}.")
        rules.append(f"Trend up but a check fails: {'99% ' + p['one_x_etf'] if p['one_x_etf'] else 'cash'}. Trend down: {p['cash_etf'] or 'cash'}.")
        tv = f'4H: built-in "Supertrend" (ATR length {p["atr"]}, factor {p["mult"]:g})'
        if p["gold_confirm"]:
            tv += f'; COMEX:GC1! 4H "Supertrend" ({p["gold_atr"]}, {p["gold_mult"]:g})'
        return {"rules": rules, "flow": f"{self.sym}=F 4H" + (" + GC=F" if p["gold_confirm"] or p["gsr_ma"] else "") +
                f" → {p['etf']}" + (f" / {p['one_x_etf']}" if p["one_x_etf"] else "") + f" · cash {p['cash_etf'] or '—'}", "tv": tv,
                "rule": f"Supertrend({p['atr']}, {p['mult']:g}) up" + (" + gold up" if p["gold_confirm"] else "") +
                (f" + > SMA{p['daily_ma']}" if p["daily_ma"] else "") + (f" + ratio < SMA{p['gsr_ma']}" if p["gsr_ma"] else "") +
                (f" · sized {p['target_vol_pct']:g}% vol" if p["target_vol_pct"] else "")}

    def check_table(self, now, rows=12):
        """Supertrend (own and gold's), the daily checks (SMA, gold/silver ratio) and the size's volatility recomputed the long way."""
        from ..health import ref_supertrend
        p = self.params
        se = metals.series(self.sym, now)
        adj4, raw4, f = se["adj4"], se["raw4"], se["factor4"].values
        res = self.compute(adj4)
        h, l, c = (adj4[k].values.astype(float).tolist() for k in ("h", "l", "c"))
        line, _ = ref_supertrend(h, l, c, p["atr"], p["mult"])
        gup = None
        if p["gold_confirm"]:
            g = adj4 if self.sym == "GC" else self._gold()
            _, gu = ref_supertrend(g.h.astype(float).tolist(), g.l.astype(float).tolist(), g.c.astype(float).tolist(), p["gold_atr"], p["gold_mult"])
            j = _align(g["end"], adj4["end"])
            gup = [bool(gu[x]) if x >= 0 else False for x in j]
        dc, days, known = daily_from_4h(adj4)
        dc = [float(x) for x in dc]
        ratio = None
        if p["gsr_ma"] > 0:
            g2 = adj4 if self.sym == "GC" else self._gold(now)
            gdc, gdays, _ = daily_from_4h(g2)
            gmap = {int(d): float(x) for d, x in zip(gdays, gdc)}
            ratio, last = [], float("nan")
            for d, x in zip(days, dc):
                v = gmap.get(int(d), float("nan")) / x
                last = v if v == v else last
                ratio.append(last)

        def daily_ok(jx):
            """the daily checks the long way: (close above its SMA, ratio below its SMA); an SMA not yet known passes"""
            if jx < 0:                              # no daily close yet: an unused check passes, a used one fails
                return p["daily_ma"] == 0, p["gsr_ma"] == 0
            ma_ok = gsr_ok = True
            m = p["daily_ma"]
            if m > 0 and jx + 1 >= m:
                ma_ok = dc[jx] > sum(dc[jx - m + 1:jx + 1]) / m
            m = p["gsr_ma"]
            if m > 0 and jx + 1 >= m:
                win = ratio[jx - m + 1:jx + 1]
                if all(x == x for x in win):
                    gsr_ok = ratio[jx] < sum(win) / m
            return ma_ok, gsr_ok
        vd = p["size_vol_days"]
        cols = ["Close", "Supertrend · bot", "Supertrend · check", "Gold up · bot", "Gold up · check", "Daily checks · bot",
                "Daily checks · check", "Volatility · bot", "Volatility · check"]
        out, mx = [], 0.0
        ends = pd.to_datetime(raw4["end"], utc=True)
        for i in range(max(0, len(c) - rows), len(c)):
            a, b = float(res["st_line"].iloc[i]) / f[i], line[i] / f[i]
            jx = known[i]
            vc = float("nan")
            if p["target_vol_pct"] > 0 and jx >= vd:
                lg = [math.log(dc[x] / dc[x - 1]) for x in range(jx - vd + 1, jx + 1)]
                m = sum(lg) / vd
                vc = (sum((x - m) ** 2 for x in lg) / (vd - 1)) ** 0.5 * math.sqrt(252) * 2
            vb = float(res["d_vol2"].iloc[i])
            diff = abs(a - b) / max(abs(a), 1e-9)
            if vb == vb and vc == vc:
                diff = max(diff, abs(vb - vc))
            gb = bool(res["gold_ok"].iloc[i]) if p["gold_confirm"] else None
            gc = gup[i] if gup is not None else None
            if gb is not None and gb != gc:
                diff = max(diff, 1.0)
            mc, rc = daily_ok(jx)
            mb, rb = bool(res["ma_ok"].iloc[i]), bool(res["gsr_ok"].iloc[i])
            if (mb, rb) != (mc, rc):
                diff = max(diff, 1.0)
            word = lambda m, r: ("pass" if m and r else ", ".join(x for x, y in (("below SMA", m), ("ratio high", r)) if not y))
            mx = max(mx, diff)
            out.append({"t": int(ends.iloc[i].timestamp()),
                        "vals": [float(raw4["c"].iloc[i]), a, b, "—" if gb is None else ("up" if gb else "down"),
                                 "—" if gc is None else ("up" if gc else "down"), word(mb, rb), word(mc, rc),
                                 vb * 100 if vb == vb else None, vc * 100 if vc == vc else None],
                        "ok": diff < 1e-6})
        return cols, out, mx
