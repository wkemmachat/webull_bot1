"""Trend + volatility gate + dips: hold a leveraged ETF while its index is above a long average AND calm; when the
trend is off, buy short dips (RSI(2) dip trades and/or one-day IBS dips); on jumpy days above the average, optionally
take one-day IBS dips. Research: "2x ETF Strategy Challengers" (2 Nov 2026), picks R1 (ROM) and U1 (USD), engine
scratchpad stage2.py `weights`. Signal at the close, fill at the next open.

After each US close, from daily bars:
  up        signal close > MA(ma_days)                     (SMA, or EMA seeded like TradingView)
  calm      signal's vol_days-day standard deviation of daily changes is below its vol_gate_q-th percentile over the
            last vol_lookback days, today included (vol_gate_q = 0: always calm)
  dip       an RSI dip trade is open (opens when NOT up and RSI(rsi_len) < rsi_buy, closes on the first close above
            SMA(exit_ma); rsi_buy = 0: no RSI dips), OR NOT up and the IBS of dip_ibs_symbol < dip_ibs_max (held the next
            day only; 0 = off), OR up but jumpy and the IBS of jumpy_ibs_symbol < jumpy_ibs_max (next day only; 0 = off)
  state     dip → "dip" (100% ETF) · up and calm → "trend" · up and jumpy → "volatile" (out) · else "out"
  size      trend: 100%, or min(100%, target_vol_pct ÷ the ETF's size_vol_days-day volatility) when target_vol_pct > 0,
            re-sized only when it moves more than size_band_pct points; dip days: 100%
Parked money: gold_share_pct in the gold ETF, the rest in cash_symbol (empty = plain cash).
Every value is computed only on days where all the symbols the rule reads have a closed bar.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401
from .trend_dip import vol_gate

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "volatile": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"trend": "above the long average and calm", "dip": "dip trade", "volatile": "above the average but jumpy · out",
              "out": "out"}


def rsi_dips(c, rsi, sexit, allowed, buy):
    """Open/closed state of RSI dip trades: opens on an allowed day with RSI < buy, closes on a close above SMA(exit)."""
    out = np.zeros(len(c), dtype=bool)
    on = False
    for i in range(len(c)):
        if on and not np.isnan(sexit[i]) and c[i] > sexit[i]:
            on = False
        elif (not on) and allowed[i] and not np.isnan(rsi[i]) and rsi[i] < buy:
            on = True
        out[i] = on
    return out


def held_sizes(trend, raw, band):
    """Size held on trend days: a fresh entry takes the size of the day; while in, it changes only on a move over `band`."""
    held, out = 0.0, np.zeros(len(raw))
    for i in range(len(raw)):
        if trend[i] and not np.isnan(raw[i]):
            if held == 0 or abs(raw[i] - held) > band:
                held = round(float(raw[i]), 2)
        else:
            held = 0.0
        out[i] = held
    return out


def ibs_of(df):
    h, l, c = (df[k].astype(float).values for k in ("h", "l", "c"))
    rng = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        v = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    return np.round(v, 4)          # 4 decimals: float noise from the data feed must not decide a tie (as ibs_dip)


@register
class TrendGateDipStrategy(RegimeStrategy):
    type = "trend_gate"
    label = "Trend + volatility gate + dips (index trend → leveraged ETF, RSI and IBS dips)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a leveraged ETF while its index is above a long average and calm; when the trend is off it buys "
                   "RSI(2) dip trades and one-day IBS dips. Optional volatility-capped size. Cash when out.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the trend from", "kind": "symbol", "default": "IYW", "group": "Symbols",
         "help": "Index ETF, daily bars"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "ROM", "group": "Symbols",
         "help": "Leveraged ETF held while in"},
        {"key": "cash_symbol", "label": "When out, hold", "kind": "symbol", "default": "", "group": "Symbols",
         "help": "Empty = plain cash (the research). A T-bill ETF costs a fee on every switch"},
        {"key": "gold_share_pct", "label": "Gold share when out (%)", "kind": "float", "default": 0.0, "min": 0, "max": 100,
         "group": "Symbols"},
        {"key": "gold_symbol", "label": "Gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols",
         "help": "Used only when the gold share is above 0"},
        {"key": "ma_type", "label": "Trend average type", "kind": "select", "default": "EMA", "options": ["SMA", "EMA"], "group": "Rules"},
        {"key": "ma_days", "label": "Trend average (days)", "kind": "int", "default": 150, "min": 20, "max": 400, "group": "Rules"},
        {"key": "vol_gate_q", "label": "Volatility filter: percentile (0 = off)", "kind": "float", "default": 90.0, "min": 0, "max": 99,
         "group": "Rules", "help": "The trend counts only while the index's volatility is below this percentile of its own recent history"},
        {"key": "vol_days", "label": "Volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Rules"},
        {"key": "vol_lookback", "label": "Volatility percentile over (days)", "kind": "int", "default": 252, "min": 60, "max": 756,
         "group": "Rules"},
        {"key": "rsi_buy", "label": "RSI dip: buy below (0 = off)", "kind": "float", "default": 5.0, "min": 0, "max": 30, "group": "Dips",
         "help": "Below the trend average: a dip trade opens when RSI is below this"},
        {"key": "rsi_len", "label": "RSI length", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "Dips"},
        {"key": "exit_ma", "label": "RSI dip: sell on a close above SMA (days)", "kind": "int", "default": 5, "min": 2, "max": 50,
         "group": "Dips"},
        {"key": "dip_ibs_max", "label": "IBS dip below the trend: IBS below (0 = off)", "kind": "float", "default": 0.15, "min": 0,
         "max": 0.5, "group": "Dips", "help": "IBS = (close − low) ÷ (high − low). Held for the next day only"},
        {"key": "dip_ibs_symbol", "label": "IBS dip below the trend: read from", "kind": "symbol", "default": "", "group": "Dips",
         "help": "Empty = the traded ETF"},
        {"key": "jumpy_ibs_max", "label": "IBS dip on jumpy days: IBS below (0 = off)", "kind": "float", "default": 0.0, "min": 0,
         "max": 0.5, "group": "Dips", "help": "Above the trend average but jumpy. Held for the next day only"},
        {"key": "jumpy_ibs_symbol", "label": "IBS dip on jumpy days: read from", "kind": "symbol", "default": "", "group": "Dips",
         "help": "Empty = the traded ETF"},
        {"key": "target_vol_pct", "label": "Trend size: volatility cap % (0 = always 100%)", "kind": "float", "default": 0.0, "min": 0,
         "max": 200, "group": "Size", "help": "Trend size = min(100%, this ÷ the traded ETF's volatility). Dip days are always 100%"},
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
        t = str(out.get("ma_type") or "").strip().upper()
        if t not in ("SMA", "EMA"):
            raise ValueError(f"Trend average type: SMA or EMA (not {out.get('ma_type')})")
        out["ma_type"] = t
        return out

    # ---------------------------------------------------------------- symbols
    def dip_sym(self):
        return self.params.get("dip_ibs_symbol") or self.params["trade"]

    def jumpy_sym(self):
        return self.params.get("jumpy_ibs_symbol") or self.params["trade"]

    def read_symbols(self):
        """Every symbol whose daily bars the rule reads (signal first)."""
        p = self.params
        out = [p["signal"], p["trade"]]
        if p["dip_ibs_max"] > 0:
            out.append(self.dip_sym())
        if p["jumpy_ibs_max"] > 0:
            out.append(self.jumpy_sym())
        return list(dict.fromkeys(out))

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

    def sized(self) -> bool:
        return float(self.params.get("target_vol_pct") or 0) > 0

    def ma_name(self):
        p = self.params
        return f"{p['ma_type']}{p['ma_days']}"

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        dfs = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            dfs[s] = df[~df.index.duplicated(keep="last")]
        # Indicators come from each symbol's own full series (a day missing from one symbol must not shift another symbol's
        # averages); decisions are made only on days where every symbol the rule reads has a closed bar.
        sg = dfs[p["signal"]]
        cs = sg["c"].astype(float).values
        ma_s = I.ema(cs, p["ma_days"]) if p["ma_type"] == "EMA" else I.sma(cs, p["ma_days"])
        sexit_s = I.sma(cs, p["exit_ma"])
        rsi_s = I.rsi(cs, p["rsi_len"])
        if p["vol_gate_q"] > 0:
            calm_s, vol_s, thr_s = vol_gate(cs, p["vol_gate_q"], p["vol_days"], p["vol_lookback"])
            ready_s = ~np.isnan(thr_s)
        else:
            calm_s, vol_s, thr_s = np.ones(len(cs), dtype=bool), np.full(len(cs), np.nan), np.full(len(cs), np.nan)
            ready_s = np.ones(len(cs), dtype=bool)
        ok_s = ~np.isnan(ma_s) & ready_s
        up_s = ok_s & (cs > np.nan_to_num(ma_s, nan=np.inf))
        rsi_on_s = rsi_dips(cs, rsi_s, sexit_s, ok_s & ~up_s, p["rsi_buy"]) if p["rsi_buy"] > 0 else np.zeros(len(cs), dtype=bool)
        tc_full = dfs[p["trade"]]["c"].astype(float)
        tvol_full = tc_full.pct_change(fill_method=None).rolling(p["size_vol_days"]).std() * math.sqrt(252)
        idx = sg.index
        for df in dfs.values():
            idx = idx.intersection(df.index)
        need = max(p["ma_days"], p["vol_lookback"] + p["vol_days"], p["size_vol_days"]) + 2
        if len(idx) < need:
            raise md.DataError(f"Need {need} daily bars of {', '.join(dfs)} on the same days, have {len(idx)}")
        pos = sg.index.get_indexer(idx)

        def on(a):
            return np.asarray(a)[pos]
        sig = sg.reindex(idx)
        c, ma, sexit, rsi = on(cs), on(ma_s), on(sexit_s), on(rsi_s)
        calm, vol, thr, ok, up, rsi_on = on(calm_s), on(vol_s), on(thr_s), on(ok_s), on(up_s), on(rsi_on_s)
        trend = up & calm
        jumpy = up & ~calm
        out_day = ok & ~up
        dip = rsi_on.copy()
        ibs_d = ibs_of(dfs[self.dip_sym()].reindex(idx)) if p["dip_ibs_max"] > 0 else np.full(len(c), np.nan)
        ibs_j = ibs_of(dfs[self.jumpy_sym()].reindex(idx)) if p["jumpy_ibs_max"] > 0 else np.full(len(c), np.nan)
        ibs_dip = np.zeros(len(c), dtype=bool)
        if p["dip_ibs_max"] > 0:
            ibs_dip = out_day & (ibs_d < p["dip_ibs_max"])
            dip |= ibs_dip
        jumpy_dip = np.zeros(len(c), dtype=bool)
        if p["jumpy_ibs_max"] > 0:
            jumpy_dip = jumpy & (ibs_j < p["jumpy_ibs_max"])
            dip |= jumpy_dip
        dip &= ok
        tvol = tvol_full.reindex(idx).values
        if self.sized():
            with np.errstate(invalid="ignore", divide="ignore"):
                raw = np.minimum(1.0, (p["target_vol_pct"] / 100) / tvol)
            held = held_sizes(trend, raw, p["size_band_pct"] / 100)
        else:
            raw = np.ones(len(c))
            held = trend.astype(float)
        size = np.where(dip, 1.0, held)
        state = np.array([""] * len(c), dtype=object)
        for i in range(len(c)):
            if not ok[i]:
                continue
            if dip[i]:
                state[i] = "dip"
            elif trend[i]:
                state[i] = "trend" if size[i] > 0 else "out"
            elif jumpy[i]:
                state[i] = "volatile"
            else:
                state[i] = "out"
        fr = pd.DataFrame(index=idx)
        fr["o"], fr["h"], fr["l"], fr["c"] = sig["o"].values, sig["h"].values, sig["l"].values, c
        fr["ma"], fr["sma_exit"], fr["rsi"] = ma, sexit, rsi
        fr["vol"], fr["vol_thr"] = vol * 100, thr * 100                # % per day
        fr["ibs_dip"], fr["ibs_jumpy"] = ibs_d, ibs_j
        fr["rsi_on"], fr["ibs_hit"], fr["jumpy_hit"] = rsi_on, ibs_dip, jumpy_dip
        fr["tvol"], fr["raw_size"] = tvol, raw
        fr["size"] = np.where(state == "", 0.0, size)
        fr["weight"] = fr["size"]
        fr["state"] = state
        fr["sma_long"] = ma                                            # name used by other parts of the app (dip zones, idle box)
        return fr

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state, size=None):
        p, buf = self.params, self.buffer()
        if state not in ("trend", "dip"):
            return self.parking()
        s = 1.0 if size is None else max(0.0, min(1.0, float(size)))
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
        to = p["trade"] if word == "BUY" else self.park_text()
        return f"{word} · {self.name}\n{h['text']}\nMoves to {to}"

    def why(self, fr, i):
        p = self.params
        a, z = fr["state"].iloc[i - 1], fr["state"].iloc[i]
        c, ma = fr["c"].iloc[i], fr["ma"].iloc[i]
        if z == "dip":
            r = fr.iloc[i]
            if bool(r["ibs_hit"]):
                return f"Dip day: {self.dip_sym()} IBS {r['ibs_dip']:.2f} < {p['dip_ibs_max']:g} with {p['signal']} below {self.ma_name()} · hold the next day"
            if bool(r["jumpy_hit"]):
                return f"Dip day (jumpy): {self.jumpy_sym()} IBS {r['ibs_jumpy']:.2f} < {p['jumpy_ibs_max']:g} · hold the next day"
            return f"Dip buy: {p['signal']} below {self.ma_name()} and RSI({p['rsi_len']}) {r['rsi']:.1f} < {p['rsi_buy']:g}"
        if z == "trend":
            if a == "volatile":
                return f"Calm again: {p['signal']} volatility {fr['vol'].iloc[i]:.2f}% < {fr['vol_thr'].iloc[i]:.2f}%, above {self.ma_name()}"
            return f"{p['signal']} closed above {self.ma_name()} ({c:,.2f} > {ma:,.2f})" + (" and calm" if p["vol_gate_q"] > 0 else "")
        if z == "volatile":
            return (f"Jumpy: {p['signal']} volatility {fr['vol'].iloc[i]:.2f}% ≥ {fr['vol_thr'].iloc[i]:.2f}% "
                    f"(its {p['vol_gate_q']:g}th percentile of the last {p['vol_lookback']} days)")
        if a == "dip":
            if bool(fr["rsi_on"].iloc[i - 1]):
                return f"Dip sold: {p['signal']} closed above SMA{p['exit_ma']} ({c:,.2f} > {fr['sma_exit'].iloc[i]:,.2f})"
            return "Dip day over: one-day dip, no new dip signal"
        return f"{p['signal']} closed below {self.ma_name()} ({c:,.2f} ≤ {ma:,.2f})"

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
                             "to": f"{szv[i] * 100:.0f}%", "price": float(fr["c"].iloc[i]),
                             "text": (f"{sts[i - 1]} → {sts[i]}: " + self.why(fr, i)) if sts[i] != sts[i - 1] else
                             f"{p['trade']} {p['size_vol_days']}-day volatility {fr['tvol'].iloc[i] * 100:.1f}% → size "
                             f"{fr['raw_size'].iloc[i] * 100:.0f}% (moved more than {p['size_band_pct']:g} points)"})
        target = self.target_for(state, size)
        pct = (last["c"] / last["ma"] - 1) * 100
        checks = [{"k": f"{p['signal']} vs {self.ma_name()}", "v": f"{last['c']:,.2f} vs {last['ma']:,.2f} · {pct:+.1f}%",
                   "cls": "up" if pct > 0 else "dn", "h": f"In the trend while {p['signal']} closes above {last['ma']:,.2f}"}]
        if p["vol_gate_q"] > 0:
            vv, vt = float(last["vol"]), float(last["vol_thr"])
            checks.append({"k": f"Volatility {p['vol_days']}d", "v": f"{vv:.2f}% vs {vt:.2f}% · {'calm' if vv < vt else 'jumpy'}",
                           "cls": "up" if vv < vt else "warn",
                           "h": f"The trend counts only while {p['signal']}'s daily volatility is below the {p['vol_gate_q']:g}th "
                                f"percentile of the last {p['vol_lookback']} days ({vt:.2f}%)"})
        if p["rsi_buy"] > 0:
            rv = float(last["rsi"])
            checks.append({"k": f"RSI({p['rsi_len']}) · exit SMA{p['exit_ma']}", "v": f"{rv:.1f} · {last['sma_exit']:,.2f}",
                           "cls": "warn" if rv < p["rsi_buy"] else "",
                           "h": f"Below the trend: dip trade on RSI < {p['rsi_buy']:g}, sold on a close above SMA{p['exit_ma']}"})
        if p["dip_ibs_max"] > 0:
            v = float(last["ibs_dip"])
            checks.append({"k": f"IBS · {self.dip_sym()}", "v": f"{v:.2f}", "cls": "warn" if v < p["dip_ibs_max"] else "",
                           "h": f"Below the trend: a one-day dip when IBS < {p['dip_ibs_max']:g}"})
        if p["jumpy_ibs_max"] > 0:
            v = float(last["ibs_jumpy"])
            checks.append({"k": f"IBS · {self.jumpy_sym()} (jumpy days)", "v": f"{v:.2f}", "cls": "warn" if v < p["jumpy_ibs_max"] else "",
                           "h": f"Above the trend but jumpy: a one-day dip when IBS < {p['jumpy_ibs_max']:g}"})
        if self.sized():
            checks.append({"k": f"Size · {p['trade']} {p['size_vol_days']}d volatility",
                           "v": f"{size * 100:.0f}% held · today {float(last['raw_size']) * 100:.0f}% · vol {float(last['tvol']) * 100:.1f}%",
                           "h": f"Trend size min(100%, {p['target_vol_pct']:g}% ÷ volatility), resized only on a move over "
                                f"{p['size_band_pct']:g} points; dip days 100%"})
        dips = []
        if p["rsi_buy"] > 0:
            dips.append(f"RSI({p['rsi_len']}) < {p['rsi_buy']:g} trades sold above SMA{p['exit_ma']}")
        if p["dip_ibs_max"] > 0:
            dips.append(f"one-day dips after {self.dip_sym()} IBS < {p['dip_ibs_max']:g}")
        hold_tr = f"{p['trade']} at the capped size, rest {self.park_text()}" if self.sized() else f"100% {p['trade']}"
        tiles = [{"k": "trend", "title": "In · trend", "text": f"{p['signal']} above {self.ma_name()}" + (" and calm" if p["vol_gate_q"] > 0 else ""),
                  "hold": hold_tr, "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip", "text": ("Below the trend: " + " and ".join(dips) if dips else "") +
                  (f"; jumpy days: one-day dips after {self.jumpy_sym()} IBS < {p['jumpy_ibs_max']:g}" if p["jumpy_ibs_max"] > 0 else ""),
                  "hold": f"100% {p['trade']}", "color": STATE_COLOR["dip"]}]
        if p["vol_gate_q"] > 0:
            tiles.append({"k": "volatile", "title": "Out · jumpy", "text": f"Above {self.ma_name()} but volatility above its "
                          f"{p['vol_gate_q']:g}th percentile", "hold": self.park_text(), "color": STATE_COLOR["volatile"]})
        tiles.append({"k": "out", "title": "Out", "text": f"Below {self.ma_name()}, no dip", "hold": self.park_text(),
                      "color": STATE_COLOR["out"]})
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (szv[i - 1] if i > 0 else szv[i]), szv[i]
            act = ("no trade" if a0 == a1 else f"buy {a1 * 100:.0f}% {p['trade']} next open" if a0 == 0
                   else f"sell {p['trade']} next open" if a1 == 0 else f"resize {a0 * 100:.0f}% → {a1 * 100:.0f}% next open")

            def num(x):
                return float(x) if x == x else None
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "ma": float(r["ma"]), "rsi": num(r["rsi"]),
                             "vol": num(r["vol"]), "vol_thr": num(r["vol_thr"]), "ibs_dip": num(r["ibs_dip"]),
                             "ibs_jumpy": num(r["ibs_jumpy"]), "size": float(r["size"]) * 100, "state": r["state"], "action": act,
                             "changed": bool(i > 0 and szv[i] != szv[i - 1]), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["signal"], "fmt": "n2"}, {"k": "ma", "label": self.ma_name(), "fmt": "n2"}]
        if p["vol_gate_q"] > 0:
            log_cols += [{"k": "vol", "label": "Vol %", "fmt": "n2"}, {"k": "vol_thr", "label": f"Vol p{p['vol_gate_q']:g} %", "fmt": "n2"}]
        if p["rsi_buy"] > 0:
            log_cols.append({"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"})
        if p["dip_ibs_max"] > 0:
            log_cols.append({"k": "ibs_dip", "label": f"IBS {self.dip_sym()}", "fmt": "n2"})
        if p["jumpy_ibs_max"] > 0 and (self.jumpy_sym() != self.dip_sym() or p["dip_ibs_max"] <= 0):
            log_cols.append({"k": "ibs_jumpy", "label": f"IBS {self.jumpy_sym()}", "fmt": "n2"})
        log_cols.append({"k": "size", "label": "Size %", "fmt": "n0"})
        label = {"trend": f"IN · {size * 100:.0f}% {p['trade']} (trend)", "dip": f"IN · {size * 100:.0f}% {p['trade']} (dip)",
                 "volatile": f"OUT · {self.park_text()} (jumpy)", "out": f"OUT · {self.park_text()}"}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": float(last["c"]), "sma_long": float(last["ma"]), "state_text": STATE_TEXT[state], "size": size,
                           "title": "Position · decided after each US close"}}

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(fr))]

        from .base import switch_dot
        sz, stv = fr["size"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if not stv[i - 1]:
                continue
            if sz[i] == sz[i - 1]:
                if sz[i] > 0 and stv[i] != stv[i - 1]:                  # trend ↔ dip with no trade: still held
                    markers.append(switch_dot(t[i], stv[i], STATE_COLOR))
                continue
            if sz[i - 1] == 0 or sz[i] == 0:
                b = sz[i] > sz[i - 1]
                markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                                "shape": "arrowUp" if b else "arrowDown",
                                "text": ("Buy · dip" if stv[i] == "dip" else f"Buy {sz[i] * 100:.0f}%") if b else "Sell"})
            else:
                sw = f"→ {stv[i]} · " if stv[i] != stv[i - 1] else ""
                markers.append({"time": t[i], "position": "belowBar", "color": "#F5C76B", "shape": "circle", "text": f"{sw}Size {sz[i] * 100:.0f}%"})
        panes = []
        if p["vol_gate_q"] > 0:
            panes.append({"id": "vol", "title": f"Volatility {p['vol_days']}d (% a day)", "height": 100,
                          "lines": [{"name": "Volatility", "color": "#8E6BBF", "width": 2, "data": ln("vol", 3)},
                                    {"name": f"{p['vol_gate_q']:g}th percentile", "color": "#FF9800", "width": 1, "data": ln("vol_thr", 3)}],
                          "hlines": []})
        if p["rsi_buy"] > 0:
            panes.append({"id": "rsi", "title": f"RSI({p['rsi_len']})", "height": 90,
                          "lines": [{"name": "RSI", "color": "#B084F5", "width": 2, "data": ln("rsi", 2)}],
                          "hlines": [{"value": p["rsi_buy"], "label": f"dip buy < {p['rsi_buy']:g}"}]})
        ibs_lines, ibs_h = [], []
        if p["dip_ibs_max"] > 0:
            ibs_lines.append({"name": f"IBS {self.dip_sym()}", "color": "#F5C76B", "width": 1, "data": ln("ibs_dip", 3)})
            ibs_h.append({"value": p["dip_ibs_max"], "label": f"dip < {p['dip_ibs_max']:g}"})
        if p["jumpy_ibs_max"] > 0 and (self.jumpy_sym() != self.dip_sym() or p["dip_ibs_max"] <= 0):
            ibs_lines.append({"name": f"IBS {self.jumpy_sym()}", "color": "#26A69A", "width": 1, "data": ln("ibs_jumpy", 3)})
        if p["jumpy_ibs_max"] > 0:
            ibs_h.append({"value": p["jumpy_ibs_max"], "label": f"jumpy dip < {p['jumpy_ibs_max']:g}"})
        if ibs_lines:
            panes.append({"id": "ibs", "title": "IBS (close position in the day's range)", "height": 90, "lines": ibs_lines, "hlines": ibs_h})
        panes.append({"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                      "lines": [{"name": "Size held", "color": self.color, "width": 2, "area": True, "data": ln("size", 1, 100)}], "hlines": []})
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — trend, volatility and RSI are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": self.ma_name().replace("MA", "MA "), "color": "#FF9800", "width": 2, "data": ln("ma")}]
               + ([{"name": f"SMA {p['exit_ma']} (dip exit)", "color": "#2962FF", "width": 1, "data": ln("sma_exit")}] if p["rsi_buy"] > 0 else []),
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": panes, "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        charts = [sig]
        tr = md.daily_closed(p["trade"], now)
        tr = tr[tr.index.isin(fr.index)]
        if len(tr):
            tt = [int(pd.Timestamp(x).timestamp()) for x in tr.index]
            tm = [dict(m) for m in markers if m["time"] in set(tt)]
            charts.append({"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — what the bot buys and sells",
                           "candles": [{"time": tt[i], "open": round(float(tr["o"].iloc[i]), 4), "high": round(float(tr["h"].iloc[i]), 4),
                                        "low": round(float(tr["l"].iloc[i]), 4), "close": round(float(tr["c"].iloc[i]), 4)} for i in range(len(tr))],
                           "lines": [], "markers": tm, "panes": [], "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        gate = (f" AND calm ({p['vol_days']}-day volatility of daily changes below its {p['vol_gate_q']:g}th percentile of the last "
                f"{p['vol_lookback']} days)") if p["vol_gate_q"] > 0 else ""
        size = (f"min(100%, {p['target_vol_pct']:g}% ÷ {p['trade']} {p['size_vol_days']}-day volatility), resized only on a move over "
                f"{p['size_band_pct']:g} points") if self.sized() else "100%"
        rules = [f"After each US close, read {p['signal']}'s daily bar: {self.ma_name()}" + (", volatility" if p["vol_gate_q"] > 0 else "")
                 + (f", RSI({p['rsi_len']}) and SMA{p['exit_ma']}" if p["rsi_buy"] > 0 else "") + ".",
                 f"Trend: close > {self.ma_name()}{gate} → {p['trade']} at {size}."]
        if p["rsi_buy"] > 0:
            rules.append(f"Below {self.ma_name()}: buy a dip when RSI({p['rsi_len']}) < {p['rsi_buy']:g}; sell it on the first close "
                         f"above SMA{p['exit_ma']}.")
        if p["dip_ibs_max"] > 0:
            rules.append(f"Below {self.ma_name()}: when {self.dip_sym()} closes with IBS = (close − low) ÷ (high − low) < "
                         f"{p['dip_ibs_max']:g}, hold 100% {p['trade']} for the next day only.")
        if p["jumpy_ibs_max"] > 0:
            rules.append(f"Above {self.ma_name()} but jumpy: when {self.jumpy_sym()} IBS < {p['jumpy_ibs_max']:g}, hold 100% "
                         f"{p['trade']} for the next day only.")
        rules += [f"Otherwise → {self.park_text()}.", "Orders start at the next market open, split into lots."]
        dip_txt = " or ".join(x for x in ((f"RSI({p['rsi_len']}) < {p['rsi_buy']:g} dips (exit > SMA{p['exit_ma']})" if p["rsi_buy"] > 0 else ""),
                                          (f"1-day dips after {self.dip_sym()} IBS < {p['dip_ibs_max']:g}" if p["dip_ibs_max"] > 0 else "")) if x)
        return {"rules": rules,
                "flow": f"{p['signal']} daily" + (f" + {self.dip_sym()} IBS" if p["dip_ibs_max"] > 0 and self.dip_sym() != p["signal"] else "")
                        + f" → {p['trade']} · {self.park_text()}",
                "tv": f'"Moving Average{" Exponential" if p["ma_type"] == "EMA" else ""}" length {p["ma_days"]}'
                      + (f', "Relative Strength Index" length {p["rsi_len"]}' if p["rsi_buy"] > 0 else "") + f" on {p['signal']} daily; "
                      "IBS = (close − low) / (high − low); volatility: compare the bot's Volatility pane",
                "rule": f"{p['signal']} > {self.ma_name()}" + (" and calm" if p["vol_gate_q"] > 0 else "")
                        + (f" (size capped at {p['target_vol_pct']:g}% ÷ vol)" if self.sized() else "")
                        + (f", or {dip_txt} below it" if dip_txt else "")
                        + (f", or 1-day dips after {self.jumpy_sym()} IBS < {p['jumpy_ibs_max']:g} on jumpy days" if p["jumpy_ibs_max"] > 0 else "")
                        + f" → {p['trade']}, else {self.park_text()}"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        """Recompute the last `rows` decisions the long way (plain loops, no app.indicators) and compare state and size."""
        p = self.params
        fr = self.frame(now)
        sg = md.daily_closed(p["signal"], now)
        sg = sg[~sg.index.duplicated(keep="last")]
        c = sg["c"].astype(float).tolist()
        n = len(c)
        L = p["ma_days"]
        # trend average on the signal's own full series
        ma = [float("nan")] * n
        if p["ma_type"] == "EMA":
            a = 2.0 / (L + 1)
            ma[L - 1] = sum(c[:L]) / L
            for i in range(L, n):
                ma[i] = a * c[i] + (1 - a) * ma[i - 1]
        else:
            for i in range(L - 1, n):
                ma[i] = sum(c[i - L + 1:i + 1]) / L
        # volatility gate: sample stdev of the last vd daily changes vs its q-th percentile (linear) over the lookback, today included
        vq, vd, lb = p["vol_gate_q"], p["vol_days"], p["vol_lookback"]
        calm, ready = [True] * n, [True] * n
        if vq > 0:
            chg = [float("nan")] + [c[i] / c[i - 1] - 1 for i in range(1, n)]
            sd = [float("nan")] * n
            for i in range(vd, n):
                w = chg[i - vd + 1:i + 1]
                m = sum(w) / vd
                sd[i] = (sum((x - m) ** 2 for x in w) / (vd - 1)) ** 0.5
            for i in range(n):
                win = sd[i - lb + 1:i + 1] if i >= lb - 1 else []
                if len(win) < lb or any(x != x for x in win):
                    calm[i], ready[i] = False, False
                    continue
                srt = sorted(win)
                q = (len(srt) - 1) * vq / 100.0
                lo = int(q)
                hi = min(lo + 1, len(srt) - 1)
                calm[i] = sd[i] < srt[lo] + (srt[hi] - srt[lo]) * (q - lo)
        # RSI the long way (Wilder averages seeded with a simple mean)
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
        # RSI dip trades replayed on every signal day
        okd, upd, rsi_on, on = [False] * n, [False] * n, [False] * n, False
        for i in range(n):
            okd[i] = ma[i] == ma[i] and ready[i]
            upd[i] = okd[i] and c[i] > ma[i]
            se = sum(c[i - p["exit_ma"] + 1:i + 1]) / p["exit_ma"] if i >= p["exit_ma"] - 1 else float("nan")
            if p["rsi_buy"] > 0:
                if on and se == se and c[i] > se:
                    on = False
                elif not on and okd[i] and not upd[i] and rs[i] == rs[i] and rs[i] < p["rsi_buy"]:
                    on = True
            rsi_on[i] = on

        ibs_src = {}

        def ibs_at(sym, day):
            if sym not in ibs_src:
                ibs_src[sym] = md.daily_closed(sym, now)
            r = ibs_src[sym].loc[day]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[-1]
            rg = r["h"] - r["l"]
            return round((r["c"] - r["l"]) / rg, 4) if rg > 0 else 0.5
        # trade ETF volatility the long way, for the size
        tr = md.daily_closed(p["trade"], now)
        tr = tr[~tr.index.duplicated(keep="last")]
        tcl = tr["c"].astype(float).tolist()
        tpos = {d: i for i, d in enumerate(tr.index)}
        vdz = p["size_vol_days"]

        def tvol(day):
            j = tpos[day]
            if j < vdz:
                return float("nan")
            ch = [tcl[x] / tcl[x - 1] - 1 for x in range(j - vdz + 1, j + 1)]
            m = sum(ch) / vdz
            return (sum((x - m) ** 2 for x in ch) / (vdz - 1)) ** 0.5 * 252 ** 0.5
        spos = {d: i for i, d in enumerate(sg.index)}
        state, size, held = [], [], 0.0
        for day in fr.index:
            i = spos[day]
            ok, up = okd[i], upd[i]
            d = rsi_on[i] or (ok and not up and p["dip_ibs_max"] > 0 and ibs_at(self.dip_sym(), day) < p["dip_ibs_max"]) or \
                (up and not calm[i] and p["jumpy_ibs_max"] > 0 and ibs_at(self.jumpy_sym(), day) < p["jumpy_ibs_max"])
            d = d and ok
            tr_on = up and calm[i]
            if tr_on and self.sized():
                v = tvol(day)
                if v == v:
                    raw = min(1.0, (p["target_vol_pct"] / 100) / v)
                    if held == 0 or abs(raw - held) > p["size_band_pct"] / 100:
                        held = round(raw, 2)
                else:
                    held = 0.0
            else:
                held = 1.0 if tr_on else 0.0
            sz = 1.0 if d else held
            if not ok:
                state.append("")
                size.append(0.0)
            else:
                state.append("dip" if d else "trend" if tr_on and sz > 0 else "volatile" if up and not tr_on else "out")
                size.append(sz)
        cols = ["Close", f"{self.ma_name()} · bot", f"{self.ma_name()} · check", "Calm bot / check", "State bot / check",
                "Size bot / check"]
        out, worst = [], 0.0
        m = len(fr)
        for j in range(m - rows, m):
            i = spos[fr.index[j]]
            a_ = float(fr["ma"].iloc[j])
            bv = bool(fr["vol"].iloc[j] < fr["vol_thr"].iloc[j]) if vq > 0 else True
            sb, zb = fr["state"].iloc[j], float(fr["size"].iloc[j])
            diff = abs(a_ - ma[i]) / ma[i]
            if bv != bool(calm[i]) or sb != state[j] or abs(zb - size[j]) > 1e-9:
                diff = max(diff, 1.0)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(fr.index[j]).timestamp()),
                        "vals": [c[i], a_, ma[i], f"{bv} / {bool(calm[i])}", f"{sb} / {state[j]}", f"{zb * 100:.0f}% / {size[j] * 100:.0f}%"],
                        "ok": diff < 1e-6})
        return cols, out, worst
