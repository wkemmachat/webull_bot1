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
        return f"4H close {c} · " + (self._why_on(r) if res["want"].iloc[i] else self._why_off(r))

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
