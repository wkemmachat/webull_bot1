"""Calm guard + dips: hold a leveraged ETF while its 1x market ETF is calm (or, optionally, in an uptrend) and its volatility is
below a fixed cap; otherwise buy short IBS dips of the leveraged ETF; else cash. Research: "DDM · RXL · SSO: 1x signals and a
better rule" (10 Nov 2026), scratchpad lev/single final_rule.py `make` (lab2.py Lab.calm / above / hold_dips). Signal at the close,
fill at the next open.

After each US close, from daily bars:
  vol       standard deviation of the market ETF's daily log changes over vol_days (sample, ddof 1)
  calm      vol ≤ its calm_pct percentile over the last vol_lookback days (today included, linear interpolation)
  uptrend   market close > SMA(uptrend_ma_days) (0 = no uptrend clause)
  capped    vol × √252 < vol_cap_pct % (0 = no cap)
  guard     (calm OR uptrend) AND capped  → hold 100% of the traded ETF
  dip       when not guarded: a dip trade opens when the traded ETF's IBS < dip_ibs_max and vol × √252 < dip_vol_cap_pct %;
            it closes on the first close above the previous day's high or after dip_max_days days; a guard day ends it
  state     "hold" · "dip" · "ready" (out, dips allowed) · "blocked" (out, volatility above the dip cap)
The market's own full history is used for the volatility and the average (a day the leveraged ETF lacks does not move them).
Parked money: gold_share_pct in the gold ETF, the rest in cash_symbol (empty = plain cash).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401
from .trend_gate import ibs_of

STATE_COLOR = {"hold": "#26A69A", "dip": "#F5C76B", "ready": "#4A5263", "blocked": "#8E3B46"}
STATE_TEXT = {"hold": "held · market calm", "dip": "dip trade open", "ready": "out · dips allowed", "blocked": "out · market too jumpy"}


def guard_parts(close: pd.Series, p) -> pd.DataFrame:
    """Volatility, calm, uptrend and caps on the market ETF's own full series."""
    v = np.log(close.astype(float)).diff().rolling(int(p["vol_days"])).std()
    q = v.rolling(int(p["vol_lookback"])).quantile(float(p["calm_pct"]) / 100.0)
    ann = v * np.sqrt(252) * 100
    out = pd.DataFrame(index=close.index)
    out["vol"], out["vol_q"], out["ann"] = v, q, ann
    out["calm"] = (v <= q).fillna(False)
    n = int(p["uptrend_ma_days"])
    out["ma"] = close.rolling(n).mean() if n > 0 else np.nan
    out["up"] = (close > out["ma"]).fillna(False) if n > 0 else False
    cap = float(p["vol_cap_pct"])
    out["capped"] = (ann < cap).fillna(False) if cap > 0 else True
    dcap = float(p["dip_vol_cap_pct"])
    out["dip_ok"] = (ann < dcap).fillna(False) if dcap > 0 else True
    out["guard"] = (out["calm"] | out["up"]) & out["capped"]
    return out


def guard_dips(c, h, ibs, guard, dip_ok, ibs_max, max_days):
    """Research hold_dips: hold on guard days; otherwise one dip trade at a time."""
    n = len(c)
    w = np.zeros(n)
    kind = np.array([""] * n, dtype=object)
    held_n = np.zeros(n, dtype=int)
    why_out = np.array([""] * n, dtype=object)
    dip, held = False, 0
    for i in range(n):
        if guard[i]:
            dip = False
            w[i], kind[i] = 1.0, "hold"
            continue
        if dip:
            held += 1
            if i > 0 and c[i] > h[i - 1]:
                dip, why_out[i] = False, "high"
            elif held >= max_days:
                dip, why_out[i] = False, "days"
        if not dip and ibs_max > 0 and dip_ok[i] and not np.isnan(ibs[i]) and ibs[i] < ibs_max:
            dip, held = True, 0
        if dip:
            w[i], kind[i], held_n[i] = 1.0, "dip", held
    return w, kind, held_n, why_out


@register
class CalmGuardStrategy(RegimeStrategy):
    type = "calm_guard"
    label = "Calm guard + dips (hold while the 1x market is calm, buy dips otherwise)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a leveraged ETF while its 1x market ETF is calm (volatility at or below its usual range, or in an "
                   "uptrend) and below a fixed volatility cap; otherwise buys short dips (IBS) of the leveraged ETF, sold on a close above "
                   "the previous high or after a few days. Cash when out.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "SSO", "group": "Symbols",
         "help": "Leveraged ETF held when calm and bought on dips (its own daily bar gives the IBS)"},
        {"key": "market", "label": "Market (1x) for the signals", "kind": "symbol", "default": "SPY", "group": "Symbols",
         "help": "1x ETF whose volatility and average decide; the research read them from the 1x ETF"},
        {"key": "cash_symbol", "label": "When out, hold", "kind": "symbol", "default": "", "group": "Symbols",
         "help": "Empty = plain cash (the research). A T-bill ETF costs a fee on every switch"},
        {"key": "gold_share_pct", "label": "Gold share when out (%)", "kind": "float", "default": 0.0, "min": 0, "max": 100,
         "group": "Symbols"},
        {"key": "gold_symbol", "label": "Gold ETF", "kind": "symbol", "default": "GLD", "group": "Symbols",
         "help": "Used only when the gold share is above 0"},
        {"key": "calm_pct", "label": "Calm: volatility at or below percentile", "kind": "float", "default": 80, "min": 50, "max": 99,
         "group": "Guard", "help": "Of the market's own volatility over the lookback below"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Guard"},
        {"key": "vol_lookback", "label": "Percentile lookback (days)", "kind": "int", "default": 252, "min": 60, "max": 1000, "group": "Guard"},
        {"key": "uptrend_ma_days", "label": "Or above SMA (days, 0 = off)", "kind": "int", "default": 100, "min": 0, "max": 400,
         "group": "Guard", "help": "Of the market ETF. The research uses 100 for SSO and DDM and none for RXL"},
        {"key": "vol_cap_pct", "label": "Hold only below volatility (% a year, 0 = off)", "kind": "float", "default": 25.0, "min": 0,
         "max": 200, "group": "Guard", "help": "Fixed cap: stops a long bear market (2008) from looking calm"},
        {"key": "dip_ibs_max", "label": "Dip: IBS below (0 = no dips)", "kind": "float", "default": 0.15, "min": 0, "max": 0.5,
         "group": "Dips", "help": "IBS = (close − low) ÷ (high − low) of the traded ETF"},
        {"key": "dip_max_days", "label": "Dip: sell after at most (days)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Dips",
         "help": "Also sold on the first close above the previous day's high"},
        {"key": "dip_vol_cap_pct", "label": "Dips only below volatility (% a year, 0 = off)", "kind": "float", "default": 40.0, "min": 0,
         "max": 200, "group": "Dips"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    # ---------------------------------------------------------------- symbols
    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["market"]]))

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def history_symbols(self):
        return self.read_symbols()

    def bench_extra(self):
        m = self.params["market"]
        return [m] if m and m != self.params["trade"] else []

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

    def guard_text(self):
        p = self.params
        s = f"{p['market']} is calm (20-day volatility at or below its {p['calm_pct']:g}th percentile)" if int(p["vol_days"]) == 20 else \
            f"{p['market']} is calm ({p['vol_days']}-day volatility at or below its {p['calm_pct']:g}th percentile)"
        if int(p["uptrend_ma_days"]) > 0:
            s += f" or above its {p['uptrend_ma_days']}-day average"
        if float(p["vol_cap_pct"]) > 0:
            s += f", and its volatility is under {p['vol_cap_pct']:g}% a year"
        return s

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        dfs = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            dfs[s] = df[~df.index.duplicated(keep="last")]
        tr, mk = dfs[p["trade"]], dfs[p["market"]]
        g = guard_parts(mk["c"], p)
        idx = tr.index.intersection(mk.index)
        need = int(p["vol_days"]) + int(p["vol_lookback"]) + 2
        if len(mk) < need or len(idx) < 30:
            raise md.DataError(f"Need {need} daily bars of {p['market']} (have {len(mk)}) and 30 of {p['trade']} on the same days")
        gp = g.reindex(idx)
        tpos = tr.index.get_indexer(idx)
        o, h, l, c = (tr[k].astype(float).values[tpos] for k in ("o", "h", "l", "c"))
        ibs = ibs_of(tr.iloc[tpos])
        ok = gp["vol_q"].notna().values
        if int(p["uptrend_ma_days"]) > 0:
            ok &= gp["ma"].notna().values
        guard = gp["guard"].values.astype(bool) & ok
        dip_ok = gp["dip_ok"].values.astype(bool) & ok
        w, kind, held, why_out = guard_dips(c, h, ibs, guard, dip_ok, float(p["dip_ibs_max"]), int(p["dip_max_days"]))
        state = np.where(~ok, "", np.where(kind == "hold", "hold", np.where(kind == "dip", "dip", np.where(dip_ok, "ready", "blocked")))).astype(object)
        fr = pd.DataFrame(index=idx)
        fr["o"], fr["h"], fr["l"], fr["c"] = o, h, l, c
        fr["ibs"] = ibs
        fr["market_c"] = mk["c"].astype(float).reindex(idx).values
        for k in ("vol", "vol_q", "ann", "ma"):
            fr[k] = gp[k].values.astype(float)
        fr["calm"], fr["up"], fr["capped"], fr["dip_ok"], fr["guard"] = (gp[k].values.astype(bool) for k in ("calm", "up", "capped", "dip_ok", "guard"))
        fr["held_days"], fr["exit_why"] = held, why_out
        fr["state"] = state
        fr["weight"] = np.where(state == "", 0.0, w)
        fr["sma_long"] = fr["ma"]
        return fr

    def weight(self, state):
        return 1.0 if state in ("hold", "dip") else 0.0

    def target_for(self, state, size=None):
        if state not in ("hold", "dip"):
            return self.parking()
        return {self.params["trade"]: round(1 - self.buffer(), 4)}

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        p = self.params
        word = "BUY" if h["kind"] == "BUY" else "SELL"
        to = p["trade"] if word == "BUY" else self.park_text()
        return f"{word} · {self.name}\n{h['text']}\nMoves to {to}"

    def guard_why(self, r):
        p = self.params
        bits = []
        if bool(r["calm"]):
            bits.append(f"{p['market']} calm (volatility {r['ann']:.0f}% a year)")
        if bool(r["up"]):
            bits.append(f"{p['market']} above its {p['uptrend_ma_days']}-day average")
        return " and ".join(bits) or "guard on"

    def why(self, fr, i):
        p = self.params
        r, a, z = fr.iloc[i], fr["state"].iloc[i - 1], fr["state"].iloc[i]
        if z == "hold" and a != "hold":
            return f"Guard on: {self.guard_why(r)} · hold {p['trade']} from the next open"
        if a == "hold" and z != "hold":
            if not bool(r["capped"]) and float(p["vol_cap_pct"]) > 0:
                why = f"{p['market']} volatility {r['ann']:.0f}% a year, above the {p['vol_cap_pct']:g}% cap"
            else:
                why = f"{p['market']} no longer calm (volatility {r['ann']:.0f}% a year)" + \
                      (f" and below its {p['uptrend_ma_days']}-day average" if int(p["uptrend_ma_days"]) > 0 else "")
            return f"Guard off: {why}" + (" · dip bought" if z == "dip" else "")
        if z == "dip" and a != "dip":
            return f"Dip: {p['trade']} IBS {r['ibs']:.2f} < {p['dip_ibs_max']:g} · buy at the next open"
        if a == "dip" and z not in ("dip", "hold"):
            if r["exit_why"] == "high":
                return f"Dip sold: {p['trade']} closed above the previous day's high ({r['c']:,.2f} > {fr['h'].iloc[i - 1]:,.2f})"
            return f"Dip sold: held {p['dip_max_days']} days"
        if z == "dip":
            return f"Dip sold and bought again: IBS {r['ibs']:.2f}"
        if z == "blocked" and a == "ready":
            return f"Dips blocked: {p['market']} volatility {r['ann']:.0f}% a year, above {p['dip_vol_cap_pct']:g}%"
        if z == "ready" and a == "blocked":
            return f"Dips allowed again: {p['market']} volatility {r['ann']:.0f}% a year"
        return STATE_TEXT.get(z, z)

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state = last["state"]
        w, sts = fr["weight"].values, fr["state"].values
        k = len(fr) - 1
        while k > 0 and w[k - 1] == w[k]:
            k -= 1
        hist = []
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if w[i] != w[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if w[i] > w[i - 1] else "SELL",
                             "from": sts[i - 1], "to": sts[i], "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        target = self.target_for(state)
        checks = [{"k": f"Volatility · {p['market']}", "v": f"{last['ann']:.1f}% a year · {last['vol'] * 100:.2f}% a day",
                   "cls": "up" if last["calm"] else "warn",
                   "h": f"Calm when at or below {last['vol_q'] * 100:.2f}% a day (the {p['calm_pct']:g}th percentile of {p['vol_lookback']} days)"}]
        if int(p["uptrend_ma_days"]) > 0:
            pct = (last["market_c"] / last["ma"] - 1) * 100
            checks.append({"k": f"{p['market']} vs SMA{p['uptrend_ma_days']}", "v": f"{last['market_c']:,.2f} vs {last['ma']:,.2f} · {pct:+.1f}%",
                           "cls": "up" if pct > 0 else "dn", "h": "Above it the guard is on even when the market is not calm"})
        if float(p["vol_cap_pct"]) > 0:
            checks.append({"k": "Volatility cap", "v": f"{'under' if last['capped'] else 'over'} {p['vol_cap_pct']:g}% a year",
                           "cls": "up" if last["capped"] else "dn", "h": "Above it the strategy never holds, however calm the percentile says"})
        checks.append({"k": "Guard", "v": "on" if last["guard"] else "off", "cls": "up" if last["guard"] else "dn",
                       "h": f"Hold while {self.guard_text()}"})
        checks.append({"k": f"IBS · {p['trade']}", "v": f"{last['ibs']:.2f}", "cls": "warn" if last["ibs"] < float(p["dip_ibs_max"]) else "",
                       "h": f"When the guard is off: a dip when IBS < {p['dip_ibs_max']:g} and volatility under {p['dip_vol_cap_pct']:g}% a year"})
        if state == "dip":
            checks.append({"k": "Dip trade", "v": f"day {int(last['held_days']) + 1} of at most {p['dip_max_days']}",
                           "h": f"Sold on the first close above the previous day's high ({last['h']:,.2f}) or after {p['dip_max_days']} days"})
        tiles = [{"k": "hold", "title": "In · guard on", "text": f"Hold while {self.guard_text()}", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["hold"]},
                 {"k": "dip", "title": "In · dip", "text": f"Guard off: {p['trade']} IBS < {p['dip_ibs_max']:g}; sold on a close above the "
                  f"previous high or after {p['dip_max_days']} days", "hold": f"100% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "ready", "title": "Out · dips allowed", "text": f"Guard off, waiting for IBS < {p['dip_ibs_max']:g}",
                  "hold": self.park_text(), "color": STATE_COLOR["ready"]},
                 {"k": "blocked", "title": "Out · too jumpy", "text": f"{p['market']} volatility above {p['dip_vol_cap_pct']:g}% a year: no dips",
                  "hold": self.park_text(), "color": STATE_COLOR["blocked"]}]

        def num(x):
            return float(x) if x == x else None
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (w[i - 1] if i > 0 else w[i]), w[i]
            act = "no trade" if a0 == a1 else f"buy {p['trade']} next open" if a1 > a0 else f"sell {p['trade']} next open"
            log_rows.append({"date": str(fr.index[i].date()), "close": float(r["c"]), "mclose": num(r["market_c"]), "ann": num(r["ann"]),
                             "ma": num(r["ma"]), "ibs": num(r["ibs"]), "guard": "on" if r["guard"] else "off", "state": r["state"],
                             "action": act, "changed": bool(i > 0 and w[i] != w[i - 1]), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "mclose", "label": p["market"], "fmt": "n2"},
                    {"k": "ann", "label": "Vol % a year", "fmt": "n1"}]
        if int(p["uptrend_ma_days"]) > 0:
            log_cols.append({"k": "ma", "label": f"SMA{p['uptrend_ma_days']}", "fmt": "n2"})
        log_cols += [{"k": "guard", "label": "Guard"}, {"k": "ibs", "label": "IBS", "fmt": "n2"}]
        label = {"hold": f"IN · 100% {p['trade']} · guard on", "dip": f"IN · 100% {p['trade']} (dip day {int(last['held_days']) + 1})",
                 "ready": f"OUT · {self.park_text()} · dips allowed", "blocked": f"OUT · {self.park_text()} · market too jumpy"}[state]
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": float(last["c"]), "sma_long": num(last["ma"]), "state_text": STATE_TEXT[state],
                           "title": "Position · decided after each US close"}}

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(fr))]

        w, stv = fr["weight"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if not stv[i - 1]:
                continue
            if w[i] > w[i - 1]:
                markers.append({"time": t[i], "position": "belowBar", "color": "#2962FF", "shape": "arrowUp",
                                "text": "Buy · " + ("guard" if stv[i] == "hold" else "dip")})
            elif w[i] < w[i - 1]:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#E040FB", "shape": "arrowDown", "text": "Sell"})
        qline = fr["vol_q"].values.astype(float) * np.sqrt(252) * 100
        fr = fr.assign(q_ann=qline)
        vol_lines = [{"name": "Volatility % a year", "color": "#F5C76B", "width": 2, "data": ln("ann", 2)},
                     {"name": f"Calm line ({p['calm_pct']:g}th pct)", "color": "#26A69A", "width": 1, "data": ln("q_ann", 2)}]
        hl = []
        if float(p["vol_cap_pct"]) > 0:
            hl.append({"value": float(p["vol_cap_pct"]), "label": f"cap {p['vol_cap_pct']:g}%"})
        if float(p["dip_vol_cap_pct"]) > 0:
            hl.append({"value": float(p["dip_vol_cap_pct"]), "label": f"dips off {p['dip_vol_cap_pct']:g}%"})
        panes = [{"id": "vol", "title": f"{p['market']} volatility (20-day, % a year)", "height": 100, "lines": vol_lines, "hlines": hl},
                 {"id": "ibs", "title": f"IBS · {p['trade']}", "height": 80, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                  "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 70, "step": True,
                  "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("weight", 1, 100)}], "hlines": []}]
        sig = {"id": "signal", "title": f"{p['trade']} · 1D", "subtitle": "Traded — dips are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": panes, "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        mk = md.daily_closed(p["market"], now)
        mk = mk[~mk.index.duplicated(keep="last")]
        mk = mk[mk.index.isin(fr.index)]
        charts = [sig]
        if len(mk):
            mt = [int(pd.Timestamp(x).timestamp()) for x in mk.index]
            lines = []
            if int(p["uptrend_ma_days"]) > 0:
                mav = fr["ma"].reindex(mk.index).values
                lines.append({"name": f"SMA {p['uptrend_ma_days']}", "color": "#FF9800", "width": 2,
                              "data": [{"time": mt[i], "value": round(float(mav[i]), 4)} if mav[i] == mav[i] else {"time": mt[i]} for i in range(len(mk))]})
            charts.append({"id": "market", "title": f"{p['market']} · 1D", "subtitle": "Market — volatility and the average are read from this chart",
                           "candles": [{"time": mt[i], "open": round(float(mk["o"].iloc[i]), 4), "high": round(float(mk["h"].iloc[i]), 4),
                                        "low": round(float(mk["l"].iloc[i]), 4), "close": round(float(mk["c"].iloc[i]), 4)} for i in range(len(mk))],
                           "lines": lines, "markers": [], "panes": [], "tv": tv_url(p["market"]), "tv_symbol": TV.get(p["market"], p["market"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        rules = [f"After each US close, read {p['market']}'s and {p['trade']}'s daily bars.",
                 f"Volatility = standard deviation of {p['market']}'s daily log changes over {p['vol_days']} days; calm = at or below its "
                 f"{p['calm_pct']:g}th percentile of the last {p['vol_lookback']} days."]
        rules.append(f"Guard on while {self.guard_text()} → 100% {p['trade']}.")
        if float(p["dip_ibs_max"]) > 0:
            rules.append(f"Guard off: buy {p['trade']} when its IBS = (close − low) ÷ (high − low) < {p['dip_ibs_max']:g} and "
                         f"{p['market']}'s volatility is under {p['dip_vol_cap_pct']:g}% a year; sell on the first close above the previous "
                         f"day's high or after {p['dip_max_days']} days.")
        rules += [f"Otherwise → {self.park_text()}.", "Orders start at the next market open, split into lots."]
        return {"rules": rules, "flow": f"{p['market']} volatility" + (f" + SMA{p['uptrend_ma_days']}" if int(p["uptrend_ma_days"]) > 0 else "")
                + f" → {p['trade']} · dips · {self.park_text()}",
                "tv": f"{p['market']} daily: standard deviation of log(close/close[1]) over {p['vol_days']}"
                      + (f', "Moving Average" length {p["uptrend_ma_days"]}' if int(p["uptrend_ma_days"]) > 0 else "")
                      + f"; {p['trade']} daily: IBS = (close − low) / (high − low)",
                "rule": f"Hold {p['trade']} while {self.guard_text()}; else {p['trade']} IBS dips; else {self.park_text()}"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        """Recompute the last `rows` decisions the long way (plain loops) and compare state."""
        p = self.params
        fr = self.frame(now)
        mk = md.daily_closed(p["market"], now)
        mk = mk[~mk.index.duplicated(keep="last")]
        tr = md.daily_closed(p["trade"], now)
        tr = tr[~tr.index.duplicated(keep="last")]
        mc = mk["c"].astype(float).tolist()
        nv, lb, n = int(p["vol_days"]), int(p["vol_lookback"]), int(p["uptrend_ma_days"])
        lr = [float("nan")] + [float(np.log(mc[i] / mc[i - 1])) for i in range(1, len(mc))]
        vol = [float("nan")] * len(mc)
        for i in range(nv, len(mc)):
            win = lr[i - nv + 1:i + 1]
            m = sum(win) / nv
            vol[i] = (sum((a - m) ** 2 for a in win) / (nv - 1)) ** 0.5
        mpos = {d: i for i, d in enumerate(mk.index)}
        tpos = {d: i for i, d in enumerate(tr.index)}
        th, tc, tl = tr["h"].astype(float).tolist(), tr["c"].astype(float).tolist(), tr["l"].astype(float).tolist()

        def guard_at(i):
            if i < nv + lb - 1:
                return None, None
            win = sorted(vol[i - lb + 1:i + 1])
            k = float(p["calm_pct"]) / 100 * (lb - 1)
            lo = int(k)
            q = win[lo] + (win[min(lo + 1, lb - 1)] - win[lo]) * (k - lo)
            ann = vol[i] * 252 ** 0.5 * 100
            calm = vol[i] <= q
            up = n > 0 and i >= n - 1 and mc[i] > sum(mc[i - n + 1:i + 1]) / n
            cap = float(p["vol_cap_pct"]) <= 0 or ann < float(p["vol_cap_pct"])
            dok = float(p["dip_vol_cap_pct"]) <= 0 or ann < float(p["dip_vol_cap_pct"])
            return (calm or up) and cap, dok
        state, dip, held, prev = [], False, 0, None
        for day in fr.index:
            gd, dok = guard_at(mpos[day])
            j = tpos[day]
            if fr["state"].loc[day] == "" or gd is None:
                state.append("")
                prev = j
                continue
            if gd:
                dip = False
                state.append("hold")
                prev = j
                continue
            if dip:
                held += 1
                if prev is not None and tc[j] > th[prev]:
                    dip = False
                elif held >= int(p["dip_max_days"]):
                    dip = False
            rg = th[j] - tl[j]
            ib = round((tc[j] - tl[j]) / rg, 4) if rg > 0 else 0.5
            if not dip and float(p["dip_ibs_max"]) > 0 and dok and ib < float(p["dip_ibs_max"]):
                dip, held = True, 0
            state.append("dip" if dip else "ready" if dok else "blocked")
            prev = j
        cols = ["Close", "Vol % a year · bot", "IBS · bot", "Guard bot", "State bot / check"]
        out, worst = [], 0.0
        m = len(fr)
        for j in range(max(0, m - rows), m):
            sb = fr["state"].iloc[j]
            bad = sb != state[j]
            worst = max(worst, 1.0 if bad else 0.0)
            av = fr["ann"].iloc[j]
            out.append({"t": int(pd.Timestamp(fr.index[j]).timestamp()),
                        "vals": [float(fr["c"].iloc[j]), float(av) if av == av else None, float(fr["ibs"].iloc[j]),
                                 "on" if fr["guard"].iloc[j] else "off", f"{sb} / {state[j]}"], "ok": not bad})
        return cols, out, worst
