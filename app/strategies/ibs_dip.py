"""QLD Trend + IBS-dip (vol cap): QLD timed by its own price, sized by Nasdaq volatility.
Research: "Research on single Stock Nasdaq" · Strategy_2_and_3_Research.xlsx, strategy 2 ("QLD own-price + vol cap").

After each US close, from QLD's own daily bar (and QQQ's daily closes for the size):
  trend   Supertrend(ATR 14, x4) on QLD is up AND QLD closes above its SMA200          → in
  dip     IBS < 0.2 AND ADX(14) > 20, where IBS = (close − low) / (high − low)           → in for the next day only
  off     neither                                                                       → parking
Size when in = min(100%, 50% ÷ (2 × QQQ's 60-day volatility)); it changes only when the new size differs from the size held
by more than 20 points (a fresh entry takes the size of the day). The part not in QLD, and everything when off, is parked
50% gold (GLD) + 50% T-bills (BIL). Orders go out from the next market open, split into lots.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register
from .regime import RANGE_DAYS, TV, RegimeStrategy, tv_url

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "off": "#4A5263"}
STATE_TEXT = {"trend": "trend on (Supertrend up, above SMA200)", "dip": "one-day dip trade after a weak close",
              "off": "off · parked in gold + T-bills"}


def states(h, l, c, atr=14, mult=4.0, ma=200, ibs_max=0.2, adx_min=20.0):
    """The research rule bar by bar. Returns (state array 'trend'|'dip'|'off'|'', supertrend dict, sma, ibs, adx)."""
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    st = I.supertrend(h, l, c, atr, mult)
    sma = I.sma(c, ma)
    adx = I.dmi(h, l, c, 14, 14)["adx"]
    rng = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        ibs = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    # 4 decimals: the data feed's float noise must not decide a tie. Real prices are in cents, so a true IBS of exactly 0.2
    # (QLD on 10 Feb 2022) can come out as 0.19999… from one feed and 0.20000… from another.
    ibs = np.round(ibs, 4)
    out = np.array([""] * len(c), dtype=object)
    for i in range(len(c)):
        if np.isnan(sma[i]) or np.isnan(st["atr"][i]):
            continue
        if bool(st["up"][i]) and c[i] > sma[i]:
            out[i] = "trend"
        elif ibs[i] < ibs_max and not np.isnan(adx[i]) and adx[i] > adx_min:
            out[i] = "dip"
        else:
            out[i] = "off"
    return out, st, sma, ibs, adx


def sizes(state, raw, band=0.20):
    """Size held after each close: a fresh entry takes the size of the day; while in, it changes only when the size of the
    day differs from the size held by more than `band`; off → 0."""
    held, out = 0.0, []
    for s, r in zip(state, raw):
        if s in ("trend", "dip") and not np.isnan(r):
            if held == 0 or abs(r - held) > band:
                held = round(float(r), 2)
        else:
            held = 0.0
        out.append(held)
    return np.asarray(out)


@register
class IbsDipStrategy(RegimeStrategy):
    type = "ibs_dip"
    label = "Trend + IBS-dip with a volatility cap (leveraged ETF timed by its own price)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a leveraged ETF while its own Supertrend is up and it is above its SMA200, or for one day after a "
                   "weak close (IBS < 0.2, ADX > 20). Size capped by the index's 60-day volatility. Gold + T-bills when out.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with (and read the signal from)", "kind": "symbol", "default": "QLD", "group": "Symbols",
         "help": "The leveraged ETF; its own daily bars give the trend and the dips"},
        {"key": "vol_symbol", "label": "Size from the volatility of", "kind": "symbol", "default": "QQQ", "group": "Symbols",
         "help": "The index the ETF follows"},
        {"key": "compare_symbol", "label": "Compare with (backtest)", "kind": "symbol", "default": "QQQ", "group": "Symbols",
         "help": "Shown next to the strategy in the Backtest tab"},
        {"key": "gold_etf", "label": "Parking: gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols"},
        {"key": "cash_symbol", "label": "Parking: T-bill ETF", "kind": "symbol", "default": "BIL", "group": "Symbols"},
        {"key": "gold_pct", "label": "Parking: share in gold %", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Symbols",
         "help": "The rest goes to the T-bill ETF"},
        {"key": "st_atr", "label": "Supertrend ATR length", "kind": "int", "default": 14, "min": 2, "max": 100, "group": "Rules"},
        {"key": "st_mult", "label": "Supertrend multiplier", "kind": "float", "default": 4.0, "min": 0.5, "max": 10, "group": "Rules"},
        {"key": "ma_days", "label": "Trend average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Rules"},
        {"key": "ibs_max", "label": "Dip day when IBS is below", "kind": "float", "default": 0.2, "min": 0.01, "max": 0.5, "group": "Rules",
         "help": "IBS = (close − low) ÷ (high − low): 0 = closed on the low"},
        {"key": "adx_min", "label": "…and ADX(14) is above", "kind": "float", "default": 20.0, "min": 0, "max": 60, "group": "Rules"},
        {"key": "target_vol_pct", "label": "Volatility cap %", "kind": "float", "default": 50.0, "min": 10, "max": 200, "group": "Rules",
         "help": "Size = this ÷ (leverage × index volatility), at most 100%"},
        {"key": "leverage", "label": "ETF leverage", "kind": "float", "default": 2.0, "min": 1, "max": 3, "group": "Rules"},
        {"key": "vol_days", "label": "Volatility window (days)", "kind": "int", "default": 60, "min": 10, "max": 250, "group": "Rules"},
        {"key": "dip_full_size", "label": "Dip days at full size (100%)", "kind": "bool", "default": False, "group": "Rules",
         "help": "Off: a dip day uses the volatility-capped size. On: a dip signal holds 100% for the next day (USD strategy C)"},
        {"key": "size_band_pct", "label": "Resize only when the size moves more than %", "kind": "float", "default": 20.0, "min": 0,
         "max": 100, "group": "Rules"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    def data_needs(self):
        p = self.params
        return [(p["trade"], "1d"), (p["vol_symbol"], "1d")]

    def history_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["vol_symbol"]]))

    def bench_extra(self):
        c = self.params.get("compare_symbol")
        return [c] if c and c != self.params["trade"] else []

    def size_formula(self, short=False):
        p = self.params
        lev = "" if p["leverage"] == 1 else f"{p['leverage']:g} × "
        vol = "vol" if short else f"{p['vol_symbol']} {p['vol_days']}-day volatility"
        return f"min(100%, {p['target_vol_pct']:g}% ÷ ({lev}{vol}))" if lev else f"min(100%, {p['target_vol_pct']:g}% ÷ {vol})"

    def dip_hold(self):
        return f"100% {self.params['trade']} for one day" if self.params.get("dip_full_size") else \
            f"{self.params['trade']} at the capped size, rest parked"

    def trade_symbols(self):
        p = self.params
        return [s for s in (p["trade"], p["gold_etf"], p["cash_symbol"]) if s]

    def benchmark_symbol(self):
        return self.params["trade"]

    def parking(self) -> dict:
        p, buf = self.params, self.buffer()
        g = max(0.0, min(1.0, p["gold_pct"] / 100))
        out = {}
        if g > 0 and p["gold_etf"]:
            out[p["gold_etf"]] = round((1 - buf) * g, 4)
        if g < 1 and p["cash_symbol"]:
            out[p["cash_symbol"]] = round((1 - buf) * (1 - g), 4)
        return out

    def cash_target(self):
        return self.parking()

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        df = md.daily_closed(p["trade"], now)
        need = max(p["ma_days"], p["vol_days"]) + 2
        if len(df) < need:
            raise md.DataError(f"Need {need} daily bars of {p['trade']}, have {len(df)}")
        q = md.daily_closed(p["vol_symbol"], now)
        if len(q) < p["vol_days"] + 2:
            raise md.DataError(f"Need {p['vol_days'] + 2} daily closes of {p['vol_symbol']}, have {len(q)}")
        h, l, c = (df[k].astype(float).values for k in ("h", "l", "c"))
        st, sup, sma, ibs, adx = states(h, l, c, p["st_atr"], p["st_mult"], p["ma_days"], p["ibs_max"], p["adx_min"])
        qc = q["c"].astype(float)
        vol = (qc.pct_change().rolling(p["vol_days"]).std() * math.sqrt(252)).reindex(df.index).ffill()
        with np.errstate(invalid="ignore", divide="ignore"):
            raw = np.minimum(1.0, (p["target_vol_pct"] / 100) / (p["leverage"] * vol.values))
        st = np.array([s if not np.isnan(r) else "" for s, r in zip(st, raw)], dtype=object)
        dip_sig = (ibs < p["ibs_max"]) & (np.nan_to_num(adx) > p["adx_min"])
        if p.get("dip_full_size"):                       # a dip signal holds 100% the next day, trend or not
            raw = np.where(dip_sig & (st != ""), 1.0, raw)
        out = pd.DataFrame(index=df.index)
        out["o"], out["h"], out["l"], out["c"] = df["o"], df["h"], df["l"], c
        out["sma_long"], out["st_line"], out["st_up"] = sma, sup["line"], sup["up"]
        out["ibs"], out["adx"], out["vol"], out["raw_size"] = ibs, adx, vol.values, raw
        out["state"] = st
        out["size"] = sizes(st, raw, p["size_band_pct"] / 100)
        out["weight"] = out["size"]
        return out

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
        to = p["trade"] if word == "BUY" else " + ".join(self.parking())
        return f"{word} · {self.name}\n{h['text']}\nMoves to {to}"

    def why(self, fr, i):
        p = self.params
        a, z = fr["state"].iloc[i - 1], fr["state"].iloc[i]
        c, sl = fr["c"].iloc[i], fr["sma_long"].iloc[i]
        if z == "trend":
            return (f"{p['trade']} trend on: Supertrend up and close {c:,.2f} > SMA{p['ma_days']} {sl:,.2f} · "
                    f"size {fr['size'].iloc[i] * 100:.0f}%")
        if z == "dip":
            return (f"Dip day: IBS {fr['ibs'].iloc[i]:.2f} < {p['ibs_max']:g}"
                    + (f" and ADX {fr['adx'].iloc[i]:.1f} > {p['adx_min']:g}" if p["adx_min"] > 0 else "") + " · "
                    f"hold {p['trade']} for the next day ({fr['size'].iloc[i] * 100:.0f}%)")
        if a == "dip":
            return f"Dip day over: no new dip signal (IBS {fr['ibs'].iloc[i]:.2f}) and the trend is off"
        return (f"{p['trade']} trend off: " + ("Supertrend turned down" if not fr["st_up"].iloc[i]
                                               else f"close {c:,.2f} ≤ SMA{p['ma_days']} {sl:,.2f}"))

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state, size = last["state"], float(last["size"])
        inpos = (fr["size"].values > 0).astype(int)
        szv = fr["size"].values
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
                             "text": f"{p['vol_symbol']} {p['vol_days']}-day volatility {fr['vol'].iloc[i] * 100:.1f}% → size "
                                     f"{fr['raw_size'].iloc[i] * 100:.0f}% (moved more than {p['size_band_pct']:g} points)"})
        target = self.target_for(state, size)
        pct = (last["c"] / last["sma_long"] - 1) * 100
        raw = float(last["raw_size"])
        checks = [
            {"k": f"{p['trade']} vs SMA{p['ma_days']}", "v": f"{last['c']:,.2f} vs {last['sma_long']:,.2f} · {pct:+.1f}%",
             "cls": "up" if pct > 0 else "dn", "h": "Trend needs the close above it"},
            {"k": f"Supertrend({p['st_atr']}, {p['st_mult']:g})", "v": f"{'up' if last['st_up'] else 'down'} · line {last['st_line']:,.2f}",
             "cls": "up" if last["st_up"] else "dn", "h": "Trend needs Supertrend up"},
            {"k": "IBS · ADX(14)", "v": f"{last['ibs']:.2f} · {last['adx']:.1f}",
             "cls": "warn" if (last["ibs"] < p["ibs_max"] and last["adx"] > p["adx_min"]) else "",
             "h": f"A dip day needs IBS < {p['ibs_max']:g} and ADX > {p['adx_min']:g}"},
            {"k": f"Size · {p['vol_symbol']} {p['vol_days']}d volatility", "v": f"{size * 100:.0f}% held · today {raw * 100:.0f}% · vol {last['vol'] * 100:.1f}%",
             "h": f"{self.size_formula(True)}{'; 100% on a dip signal' if p.get('dip_full_size') else ''}; resized only on a move over {p['size_band_pct']:g} points"},
        ]
        park = " + ".join(f"{v * 100:.0f}% {s}" for s, v in self.parking().items())
        tiles = [{"k": "trend", "title": "In · trend", "text": f"Supertrend up and {p['trade']} above SMA{p['ma_days']}",
                  "hold": f"{p['trade']} at the capped size, rest parked", "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip day", "text": (f"IBS < {p['ibs_max']:g} and ADX > {p['adx_min']:g}" if p["adx_min"] > 0 else f"IBS < {p['ibs_max']:g}") + ": held for the next day only",
                  "hold": self.dip_hold(), "color": STATE_COLOR["dip"]},
                 {"k": "off", "title": "Off", "text": "Trend off and no dip signal", "hold": park, "color": STATE_COLOR["off"]}]
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (szv[i - 1] if i > 0 else szv[i]), szv[i]
            act = ("no trade" if a0 == a1 else f"buy {a1 * 100:.0f}% {p['trade']} next open" if a0 == 0
                   else f"sell {p['trade']} next open" if a1 == 0 else f"resize {a0 * 100:.0f}% → {a1 * 100:.0f}% next open")
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "sma_long": float(r["sma_long"]),
                             "st_line": float(r["st_line"]), "ibs": float(r["ibs"]), "adx": float(r["adx"]),
                             "size": float(r["size"]) * 100, "state": r["state"], "action": act,
                             "changed": bool(i > 0 and szv[i] != szv[i - 1]), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "sma_long", "label": f"SMA{p['ma_days']}", "fmt": "n2"},
                    {"k": "st_line", "label": "Supertrend", "fmt": "n2"}, {"k": "ibs", "label": "IBS", "fmt": "n2"},
                    {"k": "adx", "label": "ADX", "fmt": "n1"}, {"k": "size", "label": "Size %", "fmt": "n0"}]
        label = {"trend": f"IN · {size * 100:.0f}% {p['trade']} (trend)", "dip": f"IN · {size * 100:.0f}% {p['trade']} (dip day)",
                 "off": "OFF · " + " + ".join(self.parking())}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols,
                           "checks": checks, "state_text": STATE_TEXT[state], "size": size,
                           "title": "Position · decided after each US close"}}

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, mask=None, digits=4, mult=1.0):
            v = fr[col].values
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) and (mask is None or mask[i])
                    else {"time": t[i]} for i in range(len(fr))]

        up = fr["st_up"].values.astype(bool)
        sz, stv = fr["size"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if not stv[i - 1] or sz[i] == sz[i - 1]:
                continue
            if sz[i - 1] == 0 or sz[i] == 0:
                b = sz[i] > sz[i - 1]
                markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                                "shape": "arrowUp" if b else "arrowDown",
                                "text": ("Dip" if stv[i] == "dip" else f"Buy {sz[i] * 100:.0f}%") if b else "Sell"})
            else:
                markers.append({"time": t[i], "position": "belowBar", "color": "#F5C76B", "shape": "circle",
                                "text": f"Size {sz[i] * 100:.0f}%"})
        sig = {"id": "signal", "title": f"{p['trade']} · 1D", "subtitle": "Signal and trade — the bot reads and buys this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['ma_days']}", "color": "#FF9800", "width": 2, "data": ln("sma_long")},
                         {"name": f"Supertrend {p['st_atr']} {p['st_mult']:g} (up)", "color": "#26A69A", "width": 1, "data": ln("st_line", up)},
                         {"name": f"Supertrend {p['st_atr']} {p['st_mult']:g} (down)", "color": "#EF5350", "width": 1,
                          "data": ln("st_line", ~up), "legend": False}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": [{"id": "ibs", "title": "IBS (close position in the day's range)", "height": 90,
                          "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", digits=3)}],
                          "hlines": [{"value": p["ibs_max"], "label": f"dip < {p['ibs_max']:g}"}]},
                         {"id": "adx", "title": "ADX(14)", "height": 80,
                          "lines": [{"name": "ADX", "color": "#B084F5", "width": 2, "data": ln("adx", digits=2)}],
                          "hlines": [{"value": p["adx_min"], "label": f"dip needs > {p['adx_min']:g}"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                          "lines": [{"name": "Size held", "color": self.color, "width": 2, "area": True, "data": ln("size", digits=1, mult=100)},
                                    {"name": "Size today", "color": "#8592A3", "width": 1, "data": ln("raw_size", digits=1, mult=100)}],
                          "hlines": []}],
               "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        park = " + ".join(f"{v / (1 - self.buffer()) * 100:.0f}% {s}" for s, v in self.parking().items())
        return {"rules": [
            f"After each US close, read {p['trade']}'s own daily bar: Supertrend({p['st_atr']}, {p['st_mult']:g}), SMA{p['ma_days']}, "
            f"IBS = (close − low) ÷ (high − low) and ADX(14).",
            f"Trend: Supertrend up AND close > SMA{p['ma_days']} → in.",
            (f"Dip day: IBS < {p['ibs_max']:g} AND ADX > {p['adx_min']:g} → in for the next day only." if p["adx_min"] > 0 else
             f"Dip day: IBS < {p['ibs_max']:g} → in for the next day only."),
            f"Size when in: {self.size_formula()}" + (", but 100% on a dip signal" if p.get("dip_full_size") else "") +
            f"; changed only when it moves more than {p['size_band_pct']:g} points.",
            f"The rest, and everything when off: {park}.",
            "Orders start at the next market open, split into lots."],
            "flow": f"{p['trade']} daily (own price) + {p['vol_symbol']} volatility → {p['trade']} · {' / '.join(self.parking())}",
            "tv": f'"Supertrend" (ATR {p["st_atr"]}, factor {p["st_mult"]:g}), "Moving Average" {p["ma_days"]} and '
                  f'"Average Directional Index" 14 on {p["trade"]} daily; IBS = (close − low) / (high − low)',
            "rule": f"{p['trade']} Supertrend up + above SMA{p['ma_days']}, or a 1-day dip after IBS < {p['ibs_max']:g}"
                    + (f" (ADX > {p['adx_min']:g})" if p["adx_min"] > 0 else "")
                    + (" at full size" if p.get("dip_full_size") else "")
                    + f"; size capped by {p['vol_symbol']} volatility; else gold + T-bills"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        from ..health import ref_adx, ref_supertrend
        p = self.params
        fr = self.frame(now)
        h, l, c = (fr[k].values.astype(float).tolist() for k in ("h", "l", "c"))
        line, up = ref_supertrend(h, l, c, p["st_atr"], p["st_mult"])
        adx = ref_adx(h, l, c, 14)
        ma = p["ma_days"]
        cols = ["Close", "Supertrend · bot", "Supertrend · check", f"SMA{ma} · bot", f"SMA{ma} · check", "IBS bot / check",
                "ADX · bot", "ADX · check", "State bot / check"]
        out, worst = [], 0.0
        for i in range(len(c) - rows, len(c)):
            sl = sum(c[i - ma + 1:i + 1]) / ma
            rg = h[i] - l[i]
            ibs = round((c[i] - l[i]) / rg, 4) if rg > 0 else 0.5
            st_chk = "trend" if (up[i] and c[i] > sl) else ("dip" if (ibs < p["ibs_max"] and adx[i] > p["adx_min"]) else "off")
            a, b = float(fr["st_line"].iloc[i]), line[i]
            d1, d2 = float(fr["adx"].iloc[i]), adx[i]
            diff = max(abs(a - b) / max(abs(a), 1e-9), abs(float(fr["sma_long"].iloc[i]) - sl) / sl,
                       abs(float(fr["ibs"].iloc[i]) - ibs), abs(d1 - d2) / 100 if not (math.isnan(d1) or math.isnan(d2)) else 0)
            if fr["state"].iloc[i] != st_chk:
                diff = max(diff, 1.0)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(fr.index[i]).timestamp()),
                        "vals": [c[i], a, b, float(fr["sma_long"].iloc[i]), sl, f"{fr['ibs'].iloc[i]:.3f} / {ibs:.3f}", d1, d2,
                                 f"{fr['state'].iloc[i]} / {st_chk}"], "ok": diff < 1e-6})
        return cols, out, worst
