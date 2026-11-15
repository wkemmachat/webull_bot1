"""IBD market direction + calm gate + one-day RSI dips: hold a leveraged ETF while its index is in an uptrend by the IBD
market-direction rule (optionally: or above a long SMA) and calm, sized by the ETF's volatility; on every other day buy for one
day after an RSI(2) dip. Research: "Strategy research and stress tests" round 1 picks QLD-B and QLD-C (15 Nov 2026,
claude/challengers-all-underlyings-nov-2026.md), the second and third legs of round 2 split C. Signal at the close, fill at the
next open.

IBD market direction (William O'Neil's rule, on the 1x index ETF and its volume):
  distribution day   the index closes down ibd_down_pct % or more on higher volume than the day before
                     (it stops counting after ibd_window sessions or once a later close is ibd_expire_pct % above it)
  correction         ibd_dist or more distribution days in the last ibd_window sessions (only those after the last
                     follow-through day count) → the uptrend ends
  rally attempt      in a correction, day 1 is the first higher close after the lowest close; the attempt restarts when the
                     index closes below the attempt's low
  follow-through     on day ibd_ftd_day or later of the attempt, a close up ibd_ftd_pct % or more on higher volume → uptrend
After each US close:
  trend    IBD uptrend (trend_mode IBD), or IBD uptrend OR close > SMA(ma_days) (trend_mode SMA|IBD)
  calm     the index's vol_days-day standard deviation of daily changes is below its vol_gate_q-th percentile over the last
           vol_lookback days, today included
  in       trend and calm → the ETF at min(99%, target_vol_pct ÷ the ETF's size_vol_days-day volatility); resized only on a
           move over size_band_pct points
  dip      not in, and the index's RSI(rsi_len) < rsi_buy (and, if dip_vol_cap_pct > 0, its vol_days-day volatility a year is
           under that cap) → the ETF for the next day only, at dip_size_pct
  else     parked: gold_share_pct in the gold ETF, the rest cash
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register, switch_dot
from .regime import RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401
from .trend_dip import vol_gate
from .trend_gate import held_sizes

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "volatile": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"trend": "uptrend and calm", "dip": "one-day RSI dip", "volatile": "uptrend but jumpy · out", "out": "out"}
MODES = ("IBD", "SMA|IBD", "SMA")


KNOBS = {"expire_pct": 5.0, "reset_on_ftd": True, "day1": "up"}   # calibrated to the research: 5% expiry, count since the last FTD


def ibd_direction(c, v, dist=6, window=25, down_pct=0.2, ftd_pct=1.25, ftd_day=4, expire_pct=None):
    """IBD market direction, bar by bar. Returns (uptrend flags, distribution-day flags, distribution count, attempt day).
    expire_pct > 0: a distribution day also stops counting once a later close is that much above its close."""
    expire_pct = KNOBS["expire_pct"] if expire_pct is None else expire_pct
    n = len(c)
    up = np.zeros(n, dtype=bool)
    ddays = np.zeros(n, dtype=bool)
    count = np.zeros(n, dtype=int)
    att = np.zeros(n, dtype=int)
    state, since, low, day1, att_low = True, 0, None, None, None
    live = []                                                   # distribution days still counting: (index, close)
    for i in range(n):
        if i > 0 and c[i - 1] > 0 and v[i - 1] > 0:
            ch = c[i] / c[i - 1] - 1
            hv = v[i] > v[i - 1]
            ddays[i] = ch <= -down_pct / 100 and hv
        else:
            ch, hv = 0.0, False
        if ddays[i]:
            live.append((i, c[i]))
        live = [(j, cj) for j, cj in live if j > i - window and (expire_pct <= 0 or c[i] < cj * (1 + expire_pct / 100))]
        if state:
            k = sum(1 for j, _ in live if j >= since)
            count[i] = k
            if k >= dist:
                state, low, day1, att_low = False, c[i], None, None
        else:
            count[i] = len(live)
            if c[i] < low:
                low, day1, att_low = c[i], None, None
            elif day1 is None:
                if ch > 0 or KNOBS["day1"] == "any":
                    day1, att_low = i, low
            elif c[i] < att_low:
                day1, att_low, low = None, None, c[i]
            if day1 is not None:
                att[i] = i - day1 + 1
                if att[i] >= ftd_day and ch >= ftd_pct / 100 and hv:
                    state, day1, att_low = True, None, None
                    since = i if KNOBS["reset_on_ftd"] else 0
        up[i] = state
    return up, ddays, count, att


@register
class IbdGateStrategy(RegimeStrategy):
    type = "ibd_gate"
    label = "IBD trend + calm + one-day RSI dips (IBD market direction → leveraged ETF, volatility-sized)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a leveraged ETF while the index is in an IBD uptrend (optionally: or above a long average) and calm, "
                   "sized by the ETF's volatility; on other days buys for one day after an RSI(2) dip. Half gold when out.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the trend from", "kind": "symbol", "default": "QQQ", "group": "Symbols",
         "help": "Index ETF, daily bars with volume"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "QLD", "group": "Symbols"},
        {"key": "cash_symbol", "label": "When out, hold", "kind": "symbol", "default": "", "group": "Symbols",
         "help": "Empty = plain cash"},
        {"key": "gold_share_pct", "label": "Gold share when out (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100,
         "group": "Symbols"},
        {"key": "gold_symbol", "label": "Gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols"},
        {"key": "trend_mode", "label": "Trend", "kind": "select", "default": "IBD", "options": list(MODES), "group": "Trend",
         "help": "IBD = IBD market direction only; SMA|IBD = IBD uptrend or close above the SMA"},
        {"key": "ma_days", "label": "SMA (days, for SMA|IBD)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend"},
        {"key": "ibd_dist", "label": "IBD: distribution days that end the uptrend", "kind": "int", "default": 6, "min": 3, "max": 12,
         "group": "Trend"},
        {"key": "ibd_window", "label": "IBD: counted over (sessions)", "kind": "int", "default": 25, "min": 10, "max": 60, "group": "Trend"},
        {"key": "ibd_down_pct", "label": "IBD: distribution day = down at least %", "kind": "float", "default": 0.2, "min": 0.05,
         "max": 2.0, "group": "Trend", "help": "on higher volume than the day before"},
        {"key": "ibd_ftd_pct", "label": "IBD: follow-through day = up at least %", "kind": "float", "default": 1.25, "min": 0.5,
         "max": 5.0, "group": "Trend", "help": "on higher volume, on day 4 or later of a rally attempt"},
        {"key": "ibd_ftd_day", "label": "IBD: follow-through from rally day", "kind": "int", "default": 4, "min": 2, "max": 10, "group": "Trend"},
        {"key": "ibd_expire_pct", "label": "IBD: a distribution day stops counting once the index is up % from it (0 = never)",
         "kind": "float", "default": 5.0, "min": 0, "max": 20, "group": "Trend",
         "help": "IBD's own rule: a distribution day expires after 25 sessions or once the index has risen about 5% from its close"},
        {"key": "vol_gate_q", "label": "Calm: percentile (0 = off)", "kind": "float", "default": 80.0, "min": 0, "max": 99, "group": "Gates"},
        {"key": "vol_days", "label": "Calm: volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Gates"},
        {"key": "vol_lookback", "label": "Calm: percentile over (days)", "kind": "int", "default": 252, "min": 60, "max": 756, "group": "Gates"},
        {"key": "rsi_buy", "label": "One-day dip: RSI below (0 = off)", "kind": "float", "default": 5.0, "min": 0, "max": 30, "group": "Dips",
         "help": "On any day the strategy is not in: hold the ETF for the next day only"},
        {"key": "rsi_len", "label": "RSI length", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "Dips"},
        {"key": "dip_vol_cap_pct", "label": "One-day dip only while the index's volatility is under % a year (0 = always)",
         "kind": "float", "default": 40.0, "min": 0, "max": 200, "group": "Dips"},
        {"key": "dip_size_pct", "label": "Dip day size %", "kind": "float", "default": 99.0, "min": 1, "max": 100, "group": "Dips",
         "help": "Share of the money in the ETF on a dip day"},
        {"key": "target_vol_pct", "label": "Trend size: volatility target % (0 = always 99%)", "kind": "float", "default": 40.0, "min": 0,
         "max": 200, "group": "Size", "help": "Trend size = min(99%, this ÷ the traded ETF's volatility)"},
        {"key": "size_vol_days", "label": "Size: volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 250, "group": "Size"},
        {"key": "size_band_pct", "label": "Resize only when the size moves more than %", "kind": "float", "default": 20.0, "min": 0,
         "max": 100, "group": "Size"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    @classmethod
    def merge_params(cls, given: dict) -> dict:
        out = super().merge_params(given)
        m = str(out.get("trend_mode") or "").strip().upper()
        if m not in MODES:
            raise ValueError(f"Trend: IBD, SMA|IBD or SMA (not {out.get('trend_mode')})")
        out["trend_mode"] = m
        return out

    # ---------------------------------------------------------------- symbols
    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["signal"], p["trade"]]))

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def history_symbols(self):
        return self.read_symbols()

    def bench_extra(self):
        s = self.params["signal"]
        return [s] if s != self.params["trade"] else []

    def trade_symbols(self):
        p = self.params
        return [s for s in (p["trade"], p["cash_symbol"], self.gold_sym()) if s]

    def benchmark_symbol(self):
        return self.params["trade"]

    def gold_share(self):
        try:
            return min(max(float(self.params.get("gold_share_pct") or 0), 0.0), 100.0) / 100.0
        except (TypeError, ValueError):
            return 0.0

    def gold_sym(self):
        return (self.params.get("gold_symbol") or "GLD") if self.gold_share() > 0 else ""

    def parking(self) -> dict:
        p, buf, g = self.params, self.buffer(), self.gold_share()
        out = {}
        if g > 0:
            out[self.gold_sym()] = round((1 - buf) * g, 4)
        if g < 1 and p["cash_symbol"]:
            out[p["cash_symbol"]] = round((1 - buf) * (1 - g), 4)
        return out

    def cash_target(self):
        return self.parking()

    def park_text(self):
        p, g = self.params, self.gold_share()
        cash = p["cash_symbol"] or "cash"
        if g <= 0:
            return cash
        if g >= 1:
            return self.gold_sym()
        return f"{g * 100:g}% {self.gold_sym()} + {(1 - g) * 100:g}% {cash}"

    def trend_name(self):
        p = self.params
        ibd = f"IBD ({p['ibd_dist']} distribution days)"
        return {"IBD": ibd, "SMA|IBD": f"{ibd} or SMA{p['ma_days']}", "SMA": f"SMA{p['ma_days']}"}[p["trend_mode"]]

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        dfs = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            dfs[s] = df[~df.index.duplicated(keep="last")]
        sg = dfs[p["signal"]]
        cs = sg["c"].astype(float).values
        vs = sg["v"].astype(float).fillna(0).values if "v" in sg.columns else np.zeros(len(cs))
        ibd_up, dday, dcount, att = ibd_direction(cs, vs, p["ibd_dist"], p["ibd_window"], p["ibd_down_pct"], p["ibd_ftd_pct"],
                                                  p["ibd_ftd_day"], p.get("ibd_expire_pct", KNOBS["expire_pct"]))
        sma = I.sma(cs, p["ma_days"])
        above = ~np.isnan(sma) & (cs > np.nan_to_num(sma, nan=np.inf))
        mode = p["trend_mode"]
        if mode == "IBD":
            up_s, ok_trend = ibd_up, np.ones(len(cs), dtype=bool)
        elif mode == "SMA":
            up_s, ok_trend = above, ~np.isnan(sma)
        else:
            up_s, ok_trend = ibd_up | above, ~np.isnan(sma)
        if p["vol_gate_q"] > 0:
            calm_s, vol_s, thr_s = vol_gate(cs, p["vol_gate_q"], p["vol_days"], p["vol_lookback"])
            ready_s = ~np.isnan(thr_s)
        else:
            calm_s, vol_s, thr_s = np.ones(len(cs), dtype=bool), pd.Series(cs).pct_change().rolling(p["vol_days"]).std().values, np.full(len(cs), np.nan)
            ready_s = np.ones(len(cs), dtype=bool)
        rsi_s = I.rsi(cs, p["rsi_len"])
        tc_full = dfs[p["trade"]]["c"].astype(float)
        tvol_full = tc_full.pct_change(fill_method=None).rolling(p["size_vol_days"]).std() * math.sqrt(252)
        idx = sg.index
        for df in dfs.values():
            idx = idx.intersection(df.index)
        need = max(p["ma_days"] if mode != "IBD" else 0, p["vol_lookback"] + p["vol_days"], p["size_vol_days"]) + 2
        if len(idx) < need:
            raise md.DataError(f"Need {need} daily bars of {', '.join(dfs)} on the same days, have {len(idx)}")
        pos = sg.index.get_indexer(idx)

        def on(a):
            return np.asarray(a)[pos]
        sig = sg.reindex(idx)
        c = on(cs)
        ok = on(ok_trend) & on(ready_s)
        up, calm, vol, thr, rsi = on(up_s), on(calm_s), on(vol_s), on(thr_s), on(rsi_s)
        trend = ok & up & calm
        vol_y = vol * math.sqrt(252) * 100
        dip_ok = (vol_y < p["dip_vol_cap_pct"]) if p["dip_vol_cap_pct"] > 0 else np.ones(len(c), dtype=bool)
        dip = ok & ~trend & (rsi < p["rsi_buy"]) & dip_ok if p["rsi_buy"] > 0 else np.zeros(len(c), dtype=bool)
        tvol = tvol_full.reindex(idx).values
        if float(p["target_vol_pct"] or 0) > 0:
            with np.errstate(invalid="ignore", divide="ignore"):
                raw = np.minimum(0.99, (p["target_vol_pct"] / 100) / tvol)
            held = held_sizes(trend, raw, p["size_band_pct"] / 100)
        else:
            raw = np.full(len(c), 0.99)
            held = trend * 0.99
        size = np.where(trend, held, np.where(dip, p["dip_size_pct"] / 100, 0.0))
        state = np.array([""] * len(c), dtype=object)
        for i in range(len(c)):
            if not ok[i]:
                continue
            state[i] = "trend" if trend[i] and size[i] > 0 else "dip" if dip[i] else ("volatile" if up[i] and not calm[i] else "out")
        fr = pd.DataFrame(index=idx)
        fr["o"], fr["h"], fr["l"], fr["c"] = sig["o"].values, sig["h"].values, sig["l"].values, c
        fr["sma"], fr["ibd_up"], fr["dday"], fr["dcount"], fr["att"] = on(sma), on(ibd_up), on(dday), on(dcount), on(att)
        fr["above"] = on(above)
        fr["vol"], fr["vol_thr"], fr["vol_y"], fr["rsi"] = vol * 100, thr * 100, vol_y, rsi
        fr["tvol"], fr["raw_size"] = tvol, raw
        fr["size"] = np.where(state == "", 0.0, np.round(size, 4))
        fr["weight"] = fr["size"]
        fr["state"] = state
        fr["sma_long"] = fr["sma"]
        fr["ma"] = fr["sma"]
        return fr

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state, size=None):
        p, buf = self.params, self.buffer()
        s = 0.0 if size is None else max(0.0, min(1.0, float(size)))
        if s <= 0:
            return self.parking()
        t = {p["trade"]: round(s * (1 - buf), 4)}
        rest = 1 - s
        if rest > 0.0005:
            for k, v in self.parking().items():
                t[k] = round(t.get(k, 0) + v * rest, 4)
        return {k: v for k, v in t.items() if v > 0}

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        p = self.params
        if h["kind"] == "SIZE":
            return f"RESIZE · {self.name}\n{h['text']}\n{p['trade']} {h['from']} → {h['to']} of the money"
        word = "BUY" if h["kind"] == "BUY" else "SELL"
        return f"{word} · {self.name}\n{h['text']}\nMoves to {p['trade'] if word == 'BUY' else self.park_text()}"

    def why(self, fr, i):
        p = self.params
        r, a, z = fr.iloc[i], fr["state"].iloc[i - 1], fr["state"].iloc[i]
        if z == "dip":
            return f"One-day dip: {p['signal']} RSI({p['rsi_len']}) {r['rsi']:.1f} < {p['rsi_buy']:g} · hold the next day"
        if z == "trend":
            if a == "volatile":
                return f"Calm again: {p['signal']} volatility {r['vol']:.2f}% < {r['vol_thr']:.2f}%"
            if bool(r["ibd_up"]) and not bool(fr["ibd_up"].iloc[i - 1]):
                return f"IBD follow-through day: {p['signal']} up {(r['c'] / fr['c'].iloc[i - 1] - 1) * 100:.2f}% on higher volume"
            if bool(r["above"]) and p["trend_mode"] != "IBD":
                return f"{p['signal']} above SMA{p['ma_days']} ({r['c']:,.2f} > {r['sma']:,.2f}) and calm"
            return f"{self.trend_name()} uptrend and calm"
        if z == "volatile":
            return f"Jumpy: {p['signal']} volatility {r['vol']:.2f}% ≥ {r['vol_thr']:.2f}% ({p['vol_gate_q']:g}th percentile)"
        if a == "dip":
            return "Dip day over: one-day dip, no new dip signal"
        if not bool(r["ibd_up"]) and bool(fr["ibd_up"].iloc[i - 1]):
            return f"IBD: {int(r['dcount'])} distribution days in {p['ibd_window']} sessions → correction"
        return f"Out: {self.trend_name()} not in an uptrend"

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state, size = last["state"], float(last["size"])
        szv = fr["size"].values
        inpos = (szv > 0).astype(int)
        k = len(fr) - 1
        while k > 0 and szv[k - 1] == szv[k]:
            k -= 1
        hist, sts = [], fr["state"].values
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if inpos[i] != inpos[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if inpos[i] > inpos[i - 1] else "SELL",
                             "from": sts[i - 1], "to": sts[i], "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
            elif inpos[i] and szv[i] != szv[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "SIZE", "from": f"{szv[i - 1] * 100:.0f}%",
                             "to": f"{szv[i] * 100:.0f}%", "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        target = self.target_for(state, size)
        ibd_txt = "uptrend" if bool(last["ibd_up"]) else f"correction (rally day {int(last['att'])})" if int(last["att"]) else "correction"
        checks = [{"k": f"IBD market direction · {p['signal']}", "v": f"{ibd_txt} · {int(last['dcount'])} distribution days in {p['ibd_window']}",
                   "cls": "up" if bool(last["ibd_up"]) else "dn",
                   "h": f"A correction starts at {p['ibd_dist']} distribution days (down ≥ {p['ibd_down_pct']:g}% on higher volume); an "
                        f"uptrend at a follow-through day (day {p['ibd_ftd_day']}+ of a rally attempt, up ≥ {p['ibd_ftd_pct']:g}% on higher volume)"}]
        if p["trend_mode"] != "IBD":
            pct = (last["c"] / last["sma"] - 1) * 100
            checks.append({"k": f"{p['signal']} vs SMA{p['ma_days']}", "v": f"{last['c']:,.2f} vs {last['sma']:,.2f} · {pct:+.1f}%",
                           "cls": "up" if pct > 0 else "dn", "h": "The trend counts when either the IBD rule or this is up"})
        if p["vol_gate_q"] > 0:
            vv, vt = float(last["vol"]), float(last["vol_thr"])
            checks.append({"k": f"Volatility {p['vol_days']}d", "v": f"{vv:.2f}% vs {vt:.2f}% · {'calm' if vv < vt else 'jumpy'}",
                           "cls": "up" if vv < vt else "warn",
                           "h": f"Calm while below the {p['vol_gate_q']:g}th percentile of the last {p['vol_lookback']} days"})
        if p["rsi_buy"] > 0:
            rv = float(last["rsi"])
            cap = f" · vol {float(last['vol_y']):.0f}% a year (cap {p['dip_vol_cap_pct']:g}%)" if p["dip_vol_cap_pct"] > 0 else ""
            checks.append({"k": f"RSI({p['rsi_len']}) · {p['signal']}", "v": f"{rv:.1f}{cap}", "cls": "warn" if rv < p["rsi_buy"] else "",
                           "h": f"Not in: a one-day buy when RSI < {p['rsi_buy']:g}"
                                + (f" while the volatility is under {p['dip_vol_cap_pct']:g}% a year" if p["dip_vol_cap_pct"] > 0 else "")})
        if float(p["target_vol_pct"] or 0) > 0:
            checks.append({"k": f"Size · {p['trade']} {p['size_vol_days']}d volatility",
                           "v": f"{size * 100:.0f}% held · today {float(last['raw_size']) * 100:.0f}% · vol {float(last['tvol']) * 100:.1f}%",
                           "h": f"Trend size min(99%, {p['target_vol_pct']:g}% ÷ volatility), resized on a move over {p['size_band_pct']:g} points"})
        tiles = [{"k": "trend", "title": "In · trend", "text": f"{self.trend_name()} up and calm",
                  "hold": f"{p['trade']} at the volatility size, rest {self.park_text()}", "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip day", "text": f"Not in and RSI({p['rsi_len']}) < {p['rsi_buy']:g}", "hold": f"{p['dip_size_pct']:g}% {p['trade']} for one day",
                  "color": STATE_COLOR["dip"]},
                 {"k": "volatile", "title": "Out · jumpy", "text": "Trend up but not calm", "hold": self.park_text(), "color": STATE_COLOR["volatile"]},
                 {"k": "out", "title": "Out", "text": "No uptrend, no dip", "hold": self.park_text(), "color": STATE_COLOR["out"]}]
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (szv[i - 1] if i > 0 else szv[i]), szv[i]
            act = ("no trade" if a0 == a1 else f"buy {a1 * 100:.0f}% {p['trade']} next open" if a0 == 0
                   else f"sell {p['trade']} next open" if a1 == 0 else f"resize {a0 * 100:.0f}% → {a1 * 100:.0f}% next open")

            def num(x):
                return float(x) if x == x else None
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "ibd": "up" if bool(r["ibd_up"]) else "corr.",
                             "dcount": int(r["dcount"]), "vol": num(r["vol"]), "vol_thr": num(r["vol_thr"]), "rsi": num(r["rsi"]),
                             "size": float(r["size"]) * 100, "state": r["state"], "action": act, "changed": bool(i > 0 and szv[i] != szv[i - 1]),
                             "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["signal"], "fmt": "n2"}, {"k": "ibd", "label": "IBD", "fmt": "text"},
                    {"k": "dcount", "label": "Dist. days", "fmt": "n0"}]
        if p["vol_gate_q"] > 0:
            log_cols += [{"k": "vol", "label": "Vol %", "fmt": "n2"}, {"k": "vol_thr", "label": f"Vol p{p['vol_gate_q']:g} %", "fmt": "n2"}]
        log_cols += [{"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"}, {"k": "size", "label": "Size %", "fmt": "n0"}]
        label = {"trend": f"IN · {size * 100:.0f}% {p['trade']} (trend)", "dip": f"IN · {size * 100:.0f}% {p['trade']} (dip)",
                 "volatile": f"OUT · {self.park_text()} (jumpy)", "out": f"OUT · {self.park_text()}"}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": float(last["c"]), "sma_long": float(last["sma"]) if last["sma"] == last["sma"] else float(last["c"]),
                           "state_text": STATE_TEXT[state], "size": size, "title": "Position · decided after each US close"}}

    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(fr))]
        sz, stv = fr["size"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if not stv[i - 1]:
                continue
            if bool(fr["dday"].iloc[i]):
                markers.append({"time": t[i], "position": "aboveBar", "color": "#EF5350", "shape": "circle", "text": "D"})
            if sz[i] == sz[i - 1]:
                if sz[i] > 0 and stv[i] != stv[i - 1]:
                    markers.append(switch_dot(t[i], stv[i], STATE_COLOR))
                continue
            if sz[i - 1] == 0 or sz[i] == 0:
                b = sz[i] > sz[i - 1]
                markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                                "shape": "arrowUp" if b else "arrowDown",
                                "text": ("Buy · dip" if stv[i] == "dip" else f"Buy {sz[i] * 100:.0f}%") if b else "Sell"})
            else:
                markers.append({"time": t[i], "position": "belowBar", "color": "#F5C76B", "shape": "circle", "text": f"Size {sz[i] * 100:.0f}%"})
        markers.sort(key=lambda m: m["time"])
        panes = [{"id": "ibd", "title": f"IBD distribution days (last {p['ibd_window']} sessions)", "height": 80, "step": True,
                  "lines": [{"name": "Distribution days", "color": "#EF5350", "width": 2, "data": ln("dcount", 0)}],
                  "hlines": [{"value": p["ibd_dist"], "label": f"correction at {p['ibd_dist']}"}]}]
        if p["vol_gate_q"] > 0:
            panes.append({"id": "vol", "title": f"Volatility {p['vol_days']}d (% a day)", "height": 90,
                          "lines": [{"name": "Volatility", "color": "#8E6BBF", "width": 2, "data": ln("vol", 3)},
                                    {"name": f"{p['vol_gate_q']:g}th percentile", "color": "#FF9800", "width": 1, "data": ln("vol_thr", 3)}], "hlines": []})
        if p["rsi_buy"] > 0:
            panes.append({"id": "rsi", "title": f"RSI({p['rsi_len']})", "height": 80,
                          "lines": [{"name": "RSI", "color": "#B084F5", "width": 2, "data": ln("rsi", 2)}],
                          "hlines": [{"value": p["rsi_buy"], "label": f"dip < {p['rsi_buy']:g}"}]})
        panes.append({"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                      "lines": [{"name": "Size", "color": self.color, "width": 2, "area": True, "data": ln("size", 1, 100)}], "hlines": []})
        lines = [{"name": f"SMA {p['ma_days']}", "color": "#FF9800", "width": 2, "data": ln("sma")}] if p["trend_mode"] != "IBD" else []
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — IBD market direction, volatility and RSI are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": lines, "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": panes, "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        return {"charts": [sig], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        size = (f"min(99%, {p['target_vol_pct']:g}% ÷ {p['trade']} {p['size_vol_days']}-day volatility)" if float(p["target_vol_pct"] or 0) > 0 else "99%")
        rules = [f"After each US close, read {p['signal']}'s daily bar and volume.",
                 f"IBD market direction: {p['ibd_dist']} or more distribution days (down ≥ {p['ibd_down_pct']:g}% on higher volume) in "
                 f"{p['ibd_window']} sessions end the uptrend; a follow-through day (day {p['ibd_ftd_day']}+ of a rally attempt, up ≥ "
                 f"{p['ibd_ftd_pct']:g}% on higher volume) starts a new one.",
                 f"In: {self.trend_name()} up" + (f" and calm (volatility below its {p['vol_gate_q']:g}th percentile of {p['vol_lookback']} days)" if p["vol_gate_q"] > 0 else "")
                 + f" → {p['trade']} at {size}."]
        if p["rsi_buy"] > 0:
            rules.append(f"Any other day: when RSI({p['rsi_len']}) < {p['rsi_buy']:g}" + (f" and {p['signal']}'s volatility is under "
                         f"{p['dip_vol_cap_pct']:g}% a year" if p["dip_vol_cap_pct"] > 0 else "") + f", hold {p['dip_size_pct']:g}% {p['trade']} for the next day only.")
        rules += [f"Otherwise → {self.park_text()}.", "Orders start at the next market open, split into lots."]
        return {"rules": rules, "flow": f"{p['signal']} daily + volume → {p['trade']} · {self.park_text()}",
                "tv": f'IBD distribution days: count {p["signal"]} down days ≥ {p["ibd_down_pct"]:g}% on higher volume; "Relative Strength Index" length {p["rsi_len"]}',
                "rule": f"{self.trend_name()} up and calm → {p['trade']} ({size}); one-day RSI({p['rsi_len']}) < {p['rsi_buy']:g} dips otherwise; else {self.park_text()}"}

    def check_table(self, now, rows=12):
        """Recompute the last `rows` decisions the long way (plain loops, no app.indicators, its own IBD walk) and compare
        the IBD direction, the calm gate, the RSI and the state."""
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        sg = md.daily_closed(p["signal"], now)
        sg = sg[~sg.index.duplicated(keep="last")]
        c = sg["c"].astype(float).tolist()
        v = (sg["v"].astype(float).fillna(0).tolist() if "v" in sg.columns else [0.0] * len(c))
        n = len(c)
        spos = {d: i for i, d in enumerate(sg.index)}
        # IBD walk, written out separately
        exp = float(p.get("ibd_expire_pct", KNOBS["expire_pct"]) or 0)
        upl, uptrend, since, low, d1, alow, dd = [False] * n, True, 0, None, None, None, []
        for i in range(n):
            chg = c[i] / c[i - 1] - 1 if i > 0 and c[i - 1] > 0 else 0.0
            higher = i > 0 and v[i - 1] > 0 and v[i] > v[i - 1]
            if i > 0 and chg <= -p["ibd_down_pct"] / 100 and higher:
                dd.append(i)
            dd = [j for j in dd if i - j < p["ibd_window"] and not (exp > 0 and c[i] >= c[j] * (1 + exp / 100))]
            if uptrend:
                if len([j for j in dd if j >= since]) >= p["ibd_dist"]:
                    uptrend, low, d1, alow = False, c[i], None, None
            else:
                if c[i] < low:
                    low, d1, alow = c[i], None, None
                elif d1 is None:
                    if chg > 0:
                        d1, alow = i, low
                elif c[i] < alow:
                    d1, alow, low = None, None, c[i]
                if d1 is not None and i - d1 + 1 >= p["ibd_ftd_day"] and chg >= p["ibd_ftd_pct"] / 100 and higher:
                    uptrend, d1, alow, since = True, None, None, i
            upl[i] = uptrend
        L = p["ma_days"]
        sma = [sum(c[i - L + 1:i + 1]) / L if i >= L - 1 else float("nan") for i in range(n)]
        chg = [float("nan")] + [c[i] / c[i - 1] - 1 for i in range(1, n)]
        vd, lb, vq = p["vol_days"], p["vol_lookback"], p["vol_gate_q"]
        sd = [float("nan")] * n
        for i in range(vd, n):
            w = chg[i - vd + 1:i + 1]
            m = sum(w) / vd
            sd[i] = (sum((x - m) ** 2 for x in w) / (vd - 1)) ** 0.5

        def calm_at(i):
            if vq <= 0:
                return True
            win = sd[i - lb + 1:i + 1] if i >= lb - 1 else []
            if len(win) < lb or any(x != x for x in win):
                return False
            srt = sorted(win)
            q = (len(srt) - 1) * vq / 100.0
            lo = int(q)
            hi = min(lo + 1, len(srt) - 1)
            return sd[i] < srt[lo] + (srt[hi] - srt[lo]) * (q - lo)
        k = p["rsi_len"]
        rs = [float("nan")] * n
        gains = [0.0] + [max(c[i] - c[i - 1], 0.0) for i in range(1, n)]
        losses = [0.0] + [max(c[i - 1] - c[i], 0.0) for i in range(1, n)]
        ag, al = sum(gains[1:k + 1]) / k, sum(losses[1:k + 1]) / k
        for i in range(k, n):
            if i > k:
                ag = (ag * (k - 1) + gains[i]) / k
                al = (al * (k - 1) + losses[i]) / k
            rs[i] = 50.0 if (al == 0 and ag == 0) else (100.0 if al == 0 else 100 - 100 / (1 + ag / al))
        out, worst = [], 0.0
        for day in fr.index[-rows:]:
            i = spos[day]
            r = fr.loc[day]
            up = upl[i] if p["trend_mode"] == "IBD" else (upl[i] or c[i] > sma[i]) if p["trend_mode"] == "SMA|IBD" else c[i] > sma[i]
            calm = calm_at(i)
            vol_y = sd[i] * math.sqrt(252) * 100
            dip_ok = p["rsi_buy"] > 0 and rs[i] < p["rsi_buy"] and (p["dip_vol_cap_pct"] <= 0 or vol_y < p["dip_vol_cap_pct"])
            st = "trend" if up and calm else "dip" if dip_ok else ("volatile" if up else "out")
            diff = abs(float(r["rsi"]) - rs[i]) / 100 if r["rsi"] == r["rsi"] and rs[i] == rs[i] else 0.0
            ok = st == r["state"] and bool(r["ibd_up"]) == upl[i] and diff < 1e-6
            worst = max(worst, 0.0 if ok else 1.0, diff)
            out.append({"t": int(pd.Timestamp(day).timestamp()),
                        "vals": [round(c[i], 2), "up" if bool(r["ibd_up"]) else "down", "up" if upl[i] else "down",
                                 round(float(r["rsi"]), 2), round(rs[i], 2), r["state"], st, round(float(r["size"]) * 100)],
                        "ok": bool(ok)})
        cols = ["Close", "IBD · bot", "IBD · check", "RSI · bot", "RSI · check", "State · bot", "State · check", "Size %"]
        return cols, out, worst
