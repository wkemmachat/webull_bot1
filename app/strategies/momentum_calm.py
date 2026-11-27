"""Momentum + calm + one-day dips on a 2x ETF read from its 1x stocks (RAM, Roundhill 2x DRAM / memory chips). Research "RAM (2x
memory ETF): two best strategies" (26 Nov 2026), rule A, kept after round 2 ("RAM round 2: trying to beat A and B").

After each US close, from daily bars (signal at the close, trade at the next open):
  momentum  every `mom_symbols` stock/ETF closes above its close `mom_days` trading days earlier (MU and SMH, 126 days)
  fast      `fast_symbol` closes above its close `fast_days` days earlier (MU, 20 days)
  calm      `calm_symbol`'s volatility (standard deviation of its last vol_days daily log changes) at or below its calm_pct
            percentile of the last vol_lookback days, today included (SMH, 20 days, 90th percentile of 504 days)
  hold      momentum AND fast AND calm                                     → 100% of the traded ETF (less the cash buffer)
  dip       not hold, and the traded ETF closes with IBS < dip_ibs_max     → 100% for one day (next open to the open after)
  else      cash
Before the traded ETF listed (RAM: 24 Jun 2026) the backtest models it as 2 × the daily move of `model_basket` (US memory
stocks, weights) minus model_cost_pct a year, joined to its first real close; its IBS then comes from that model.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"hold": "#26A69A", "dip": "#F5C76B", "jumpy": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"hold": "momentum on and calm", "dip": "one-day dip buy", "jumpy": "out · momentum on but SMH jumpy",
              "out": "out · momentum off"}
TV.update({"RAM": "AMEX:RAM", "MU": "NASDAQ:MU", "STX": "NASDAQ:STX", "WDC": "NASDAQ:WDC"})


def parse_weights(text: str) -> dict:
    out = {}
    for part in str(text or "").split(","):
        sym, _, w = part.strip().partition(":")
        if sym.strip():
            out[sym.strip().upper()] = float(w) if w.strip() else 1.0
    tot = sum(out.values()) or 1.0
    return {k: v / tot for k, v in out.items()}


def model_2x(real: pd.DataFrame | None, stocks: dict, weights: dict, idx, cost_y: float) -> pd.DataFrame:
    """2 × the weighted basket's daily move (open, high, low, close from the previous close) minus cost, joined to `real`'s first
    close (the model alone when there is no real history)."""
    rel = {}
    for k in ("o", "h", "l", "c"):
        parts = []
        for s, w in weights.items():
            df = stocks[s][~stocks[s].index.duplicated(keep="last")].reindex(idx)
            parts.append(w * (df[k].astype(float) / df["c"].astype(float).shift(1) - 1))
        rel[k] = sum(parts)
    ok = rel["c"].notna().values
    n = len(idx)
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    prev = 100.0
    for i in range(n):
        if not ok[i]:
            continue
        o[i] = prev * (1 + 2 * rel["o"].iloc[i])
        cc = prev * (1 + 2 * rel["c"].iloc[i] - cost_y / 252)
        h[i] = max(prev * (1 + 2 * rel["h"].iloc[i]), o[i], cc)
        l[i] = min(prev * (1 + 2 * rel["l"].iloc[i]), o[i], cc)
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
    return pd.concat([early, real])


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    """One row per day of the traded ETF: the rule's parts and the weight held from the next open."""
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[k] = tr[k].astype(float).values
    rng = fr["h"] - fr["l"]
    fr["ibs"] = np.round(np.where(rng > 0, (fr["c"] - fr["l"]) / rng.where(rng > 0, 1.0), 0.5), 4)
    nm, nf = int(p["mom_days"]), int(p["fast_days"])
    mom = pd.Series(True, index=idx)
    ok = pd.Series(True, index=idx)
    for s in [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]:
        c = data[s]["c"].astype(float)
        up = (c > c.shift(nm)).reindex(idx)
        ok &= c.shift(nm).reindex(idx).notna()
        mom &= up.fillna(False).astype(bool)
        fr[f"mom_{s}"] = ((c / c.shift(nm) - 1) * 100).reindex(idx).values
    fc = data[p["fast_symbol"]]["c"].astype(float)
    fast = (fc > fc.shift(nf)).reindex(idx).fillna(False).astype(bool)
    fr["fast"] = ((fc / fc.shift(nf) - 1) * 100).reindex(idx).values
    cc = data[p["calm_symbol"]]["c"].astype(float)
    v = np.log(cc).diff().rolling(int(p["vol_days"])).std()
    q = v.rolling(int(p["vol_lookback"])).quantile(float(p["calm_pct"]) / 100.0)
    fr["vol"], fr["vol_q"] = v.reindex(idx).values, q.reindex(idx).values
    calm = (v <= q).reindex(idx).fillna(False).astype(bool)
    ok &= q.reindex(idx).notna()
    hold = mom & fast & calm & ok
    dip = ok & ~hold & (fr["ibs"] < float(p["dip_ibs_max"]))
    fr["mom"], fr["fast_ok"], fr["calm"], fr["ok"] = mom.values, fast.values, calm.values, ok.values
    fr["w"] = (hold | dip).astype(float).values
    fr["state"] = np.where(~ok, "", np.where(hold, "hold", np.where(dip, "dip", np.where(mom & fast, "jumpy", "out"))))
    return fr


@register
class MomentumCalmStrategy(RegimeStrategy):
    type = "momentum_calm"
    label = "Momentum + calm + one-day dips (2x ETF read from its stocks)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a 2x ETF while its stocks are above their 6-month and 1-month levels and the sector is calm; "
                   "otherwise buys one-day dips after a weak close; cash else.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "RAM", "group": "Symbols"},
        {"key": "mom_symbols", "label": "Momentum: all above their close of N days ago", "kind": "text", "default": "MU,SMH", "group": "Rules"},
        {"key": "mom_days", "label": "Momentum days", "kind": "int", "default": 126, "min": 10, "max": 400, "group": "Rules"},
        {"key": "fast_symbol", "label": "Fast check symbol", "kind": "symbol", "default": "MU", "group": "Rules"},
        {"key": "fast_days", "label": "Fast check days", "kind": "int", "default": 20, "min": 2, "max": 200, "group": "Rules"},
        {"key": "calm_symbol", "label": "Calm check symbol", "kind": "symbol", "default": "SMH", "group": "Rules"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Rules"},
        {"key": "vol_lookback", "label": "Percentile lookback (days)", "kind": "int", "default": 504, "min": 60, "max": 1500, "group": "Rules"},
        {"key": "calm_pct", "label": "Calm: at or below percentile", "kind": "float", "default": 90.0, "min": 50, "max": 99, "group": "Rules"},
        {"key": "dip_ibs_max", "label": "Dip: IBS below (0 = no dips)", "kind": "float", "default": 0.10, "min": 0, "max": 0.5, "group": "Dips",
         "help": "Of the traded ETF's own daily bar; bought for one day when the hold rule is off"},
        {"key": "model_basket", "label": "Backtest: model before listing (symbol:weight)", "kind": "text", "default": "MU:70,STX:15,WDC:15",
         "group": "Backtest", "help": "2 × this basket's daily move before the ETF's first real bar"},
        {"key": "model_cost_pct", "label": "Backtest: model cost (% a year)", "kind": "float", "default": 18.5, "min": 0, "max": 100, "group": "Backtest"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money"},
    ]

    # ---------------------------------------------------------------- symbols
    def signal_symbols(self):
        p = self.params
        mom = [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]
        return list(dict.fromkeys(mom + [p["fast_symbol"], p["calm_symbol"]]))

    def read_symbols(self):
        return list(dict.fromkeys([self.params["trade"]] + self.signal_symbols()))

    def data_needs(self):
        return [(s, "1d") for s in self.history_symbols()]          # the model's stocks too (backtest before the listing)

    def history_symbols(self):
        return list(dict.fromkeys(self.read_symbols() + list(parse_weights(self.params["model_basket"]))))

    def bench_extra(self):
        return [self.params["fast_symbol"]]

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

    # ---------------------------------------------------------------- the days
    def frame(self, now, model=False) -> pd.DataFrame:
        p = self.params
        data = {}
        syms = self.history_symbols() if model else self.read_symbols()
        for s in syms:
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            data[s] = df[~df.index.duplicated(keep="last")]
        tr = data[p["trade"]]
        if model:
            base = data[p["fast_symbol"]].index
            tr = model_2x(tr, data, parse_weights(p["model_basket"]), base, float(p["model_cost_pct"]) / 100)
        fr = signals(tr, data, p)
        if len(fr) < 5 or not fr["ok"].any():
            raise md.DataError(f"Need {int(p['vol_lookback']) + int(p['vol_days']) + 2} daily bars of {p['calm_symbol']} and "
                               f"{int(p['mom_days']) + 2} of {p['mom_symbols']}")
        return fr

    # ---------------------------------------------------------------- live
    def target_for(self, state, size=None):
        return {self.params["trade"]: round(1 - self.buffer(), 4)} if state in ("hold", "dip") else {}

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        return f"{h['kind']} · {self.name}\n{h['text']}"

    def why(self, fr, i):
        p = self.params
        r, a = fr.iloc[i], fr["state"].iloc[i - 1]
        z = r["state"]
        moms = ", ".join(f"{s} {r[f'mom_{s}']:+.0f}%" for s in [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()])
        if z == "hold" and a != "hold":
            return f"Hold: {moms} over {p['mom_days']} days, {p['fast_symbol']} {r['fast']:+.1f}% over {p['fast_days']} days, {p['calm_symbol']} calm · buy {p['trade']} at the next open"
        if z == "dip" and a != "dip":
            return f"Dip: {p['trade']} IBS {r['ibs']:.2f} < {p['dip_ibs_max']:g} · buy at the next open, sell at the open after"
        if a in ("hold", "dip") and z not in ("hold", "dip"):
            if a == "dip":
                return "Dip sold at the next open (one day)"
            if not r["mom"]:
                return f"Momentum off ({moms} over {p['mom_days']} days) · sell at the next open"
            if not r["fast_ok"]:
                return f"{p['fast_symbol']} {r['fast']:+.1f}% over {p['fast_days']} days · sell at the next open"
            return f"{p['calm_symbol']} not calm (volatility above its {p['calm_pct']:g}th percentile) · sell at the next open"
        if z == "dip":
            return f"Dip again: IBS {r['ibs']:.2f}"
        return STATE_TEXT.get(z, z)

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state = last["state"]
        w, sts = fr["w"].values, fr["state"].values
        hist = []
        for i in range(max(1, len(fr) - 600), len(fr)):
            if w[i] != w[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if w[i] > w[i - 1] else "SELL", "from": sts[i - 1], "to": sts[i],
                             "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        k = len(fr) - 1
        while k > 0 and w[k - 1] == w[k]:
            k -= 1
        moms = [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]
        checks = [{"k": f"Momentum · {', '.join(moms)} vs {p['mom_days']} days ago",
                   "v": " · ".join(f"{s} {last[f'mom_{s}']:+.1f}%" for s in moms), "cls": "up" if last["mom"] else "dn",
                   "h": "All must be above their close of that day"},
                  {"k": f"Fast · {p['fast_symbol']} vs {p['fast_days']} days ago", "v": f"{last['fast']:+.1f}%",
                   "cls": "up" if last["fast_ok"] else "dn"},
                  {"k": f"Calm · {p['calm_symbol']} {p['vol_days']}-day volatility", "v": f"{last['vol'] * 100:.2f}% a day vs "
                   f"{last['vol_q'] * 100:.2f}% ({p['calm_pct']:g}th percentile of {p['vol_lookback']} days)",
                   "cls": "up" if last["calm"] else "dn", "h": "At or below the line = calm"},
                  {"k": f"IBS · {p['trade']}", "v": f"{last['ibs']:.2f}", "cls": "warn" if last["ibs"] < float(p["dip_ibs_max"]) else "",
                   "h": f"When the hold rule is off: below {p['dip_ibs_max']:g} → buy for one day"}]
        tiles = [{"k": "hold", "title": "In · momentum + calm", "text": f"{', '.join(moms)} up over {p['mom_days']} days, {p['fast_symbol']} up over "
                  f"{p['fast_days']} days, {p['calm_symbol']} calm", "hold": f"100% {p['trade']}", "color": STATE_COLOR["hold"]},
                 {"k": "dip", "title": "In · one-day dip", "text": f"Hold rule off, {p['trade']} IBS < {p['dip_ibs_max']:g}",
                  "hold": f"100% {p['trade']} for one day", "color": STATE_COLOR["dip"]},
                 {"k": "jumpy", "title": "Out · jumpy", "text": f"Momentum on but {p['calm_symbol']} not calm", "hold": "cash (dips allowed)",
                  "color": STATE_COLOR["jumpy"]},
                 {"k": "out", "title": "Out", "text": "Momentum off", "hold": "cash (dips allowed)", "color": STATE_COLOR["out"]}]

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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["c"]), "ibs": num(r["ibs"]),
                             **{f"m{j}": num(r[f"mom_{s}"]) for j, s in enumerate(moms)}, "fast": num(r["fast"]),
                             "calm": "yes" if r["calm"] else "no", "state": r["state"],
                             "action": "no trade" if a0 == a1 else f"{'buy' if a1 > a0 else 'sell'} {p['trade']} next open",
                             "changed": bool(i > 0 and w[i] != w[i - 1]), "from": sts[i - 1] if i > 0 else None})
        log_cols = ([{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "ibs", "label": "IBS", "fmt": "n2"}]
                    + [{"k": f"m{j}", "label": f"{s} {p['mom_days']}d %", "fmt": "n1"} for j, s in enumerate(moms)]
                    + [{"k": "fast", "label": f"{p['fast_symbol']} {p['fast_days']}d %", "fmt": "n1"}, {"k": "calm", "label": "Calm"}])
        label = {"hold": f"IN · 100% {p['trade']} · momentum + calm", "dip": f"IN · 100% {p['trade']} · one-day dip",
                 "jumpy": f"OUT · cash · {p['calm_symbol']} jumpy", "out": "OUT · cash · momentum off"}[state]
        return {"ok": True, "state": state, "label": label, "target": self.target_for(state),
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": num(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": num(last["c"]), "state_text": STATE_TEXT[state], "title": "Position · decided after each US close"}}

    # ---------------------------------------------------------------- chart
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
            if w[i] > w[i - 1]:
                markers.append({"time": t[i], "position": "belowBar", "color": "#2962FF", "shape": "arrowUp",
                                "text": "Buy · " + ("hold" if fr["state"].iloc[i] == "hold" else "dip")})
            elif w[i] < w[i - 1]:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#E040FB", "shape": "arrowDown", "text": "Sell"})
        moms = [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]
        colors = ["#5B8DEF", "#20C997", "#F5C76B"]
        fr = fr.assign(q_line=fr["vol_q"] * 100, v_line=fr["vol"] * 100)
        panes = [{"id": "mom", "title": f"Momentum: % vs {p['mom_days']} days ago (and {p['fast_symbol']} vs {p['fast_days']})", "height": 90,
                  "lines": [{"name": f"{s} {p['mom_days']}d", "color": colors[j % 3], "width": 1, "data": ln(f"mom_{s}", 1)} for j, s in enumerate(moms)]
                  + [{"name": f"{p['fast_symbol']} {p['fast_days']}d", "color": "#E46AA8", "width": 1, "data": ln("fast", 1)}],
                  "hlines": [{"value": 0, "label": "0"}]},
                 {"id": "vol", "title": f"{p['calm_symbol']} volatility (% a day)", "height": 80,
                  "lines": [{"name": "Volatility", "color": "#F5C76B", "width": 2, "data": ln("v_line", 3)},
                            {"name": f"Calm line ({p['calm_pct']:g}th pct)", "color": "#26A69A", "width": 1, "data": ln("q_line", 3)}], "hlines": []},
                 {"id": "ibs", "title": f"IBS · {p['trade']}", "height": 60, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                  "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                  "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}]
        sig = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — dips are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(fr["state"].values)],
               "panes": panes, "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        charts = [sig]
        for s in self.signal_symbols():
            df = md.daily_closed(s, now)
            df = df[~df.index.duplicated(keep="last")]
            df = df[df.index.isin(fr.index)]
            if not len(df):
                continue
            st = [int(pd.Timestamp(x).timestamp()) for x in df.index]
            charts.append({"id": f"sig_{s}", "title": f"{s} · 1D", "subtitle": "Signal — momentum / calm are read from this chart",
                           "candles": [{"time": st[i], "open": round(float(df["o"].iloc[i]), 4), "high": round(float(df["h"].iloc[i]), 4),
                                        "low": round(float(df["l"].iloc[i]), 4), "close": round(float(df["c"].iloc[i]), 4)} for i in range(len(df))],
                           "lines": [], "markers": [], "panes": [], "tv": tv_url(s), "tv_symbol": TV.get(s, s)})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        moms = [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]
        return {"rules": [
            f"After each US close: hold 100% {p['trade']} while {' and '.join(moms)} close above their close {p['mom_days']} trading days earlier, "
            f"{p['fast_symbol']} closes above its close {p['fast_days']} days earlier, and {p['calm_symbol']}'s {p['vol_days']}-day volatility is at or "
            f"below its {p['calm_pct']:g}th percentile of {p['vol_lookback']} days.",
            f"Otherwise, after a weak close of {p['trade']} (IBS < {p['dip_ibs_max']:g}): buy at the next open, sell at the open after.",
            "Otherwise cash. Orders at the next open."],
            "flow": f"{', '.join(self.signal_symbols())} daily → {p['trade']} · cash",
            "tv": f"{', '.join(moms)}: close vs close[{p['mom_days']}]; {p['fast_symbol']}: close vs close[{p['fast_days']}]; "
                  f"{p['calm_symbol']}: stdev(log(close/close[1]), {p['vol_days']}); {p['trade']}: IBS = (close − low) / (high − low)",
            "rule": f"{p['trade']} while {'+'.join(moms)} up over {p['mom_days']}d, {p['fast_symbol']} up over {p['fast_days']}d and "
                    f"{p['calm_symbol']} calm; one-day dips IBS < {p['dip_ibs_max']:g}; else cash"}

    # ---------------------------------------------------------------- backtest (backtest.py calls this)
    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        weights = parse_weights(p["model_basket"])
        stocks = {s: BT.daily_tr(s) for s in weights}
        base = BT.daily_tr(p["fast_symbol"])
        tr = model_2x(BT.daily_tr(sym), stocks, weights, base.index, float(p["model_cost_pct"]) / 100).reindex(fr.index)
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
                if want != cur:
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
                "bench": {sym: tr.dropna(subset=["c"]), p["fast_symbol"]: base}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym,
                "index": p["fast_symbol"], "data_from": str(days[0]),
                "data_note": f"{', '.join(self.signal_symbols())} daily bars (signals) · {sym} daily total-return prices; {sym} before {listed}: "
                             f"modelled as 2 × ({', '.join(f'{k} {v * 100:.0f}%' for k, v in weights.items())}) daily minus "
                             f"{p['model_cost_pct']:g}% a year"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        p = self.params
        fr = self.frame(now)
        moms = [x.strip().upper() for x in p["mom_symbols"].split(",") if x.strip()]
        data = {s: md.daily_closed(s, now) for s in self.signal_symbols()}
        data = {s: df[~df.index.duplicated(keep="last")] for s, df in data.items()}
        nm, nf = int(p["mom_days"]), int(p["fast_days"])
        cols = ["Close", "Momentum · bot / check", f"{p['fast_symbol']} fast · bot / check", "IBS", "State"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            chk_m = True
            for s in moms:
                cl = data[s]["c"].astype(float).tolist()
                i = data[s].index.get_loc(d)
                chk_m &= i >= nm and cl[i] > cl[i - nm]
            fl = data[p["fast_symbol"]]["c"].astype(float).tolist()
            i = data[p["fast_symbol"]].index.get_loc(d)
            chk_f = i >= nf and fl[i] > fl[i - nf]
            bad = (bool(r["mom"]) != bool(chk_m)) or (bool(r["fast_ok"]) != bool(chk_f))
            worst = max(worst, 1.0 if bad else 0.0)
            out.append({"t": int(pd.Timestamp(d).timestamp()),
                        "vals": [float(r["c"]), f"{'up' if r['mom'] else 'down'} / {'up' if chk_m else 'down'}",
                                 f"{'up' if r['fast_ok'] else 'down'} / {'up' if chk_f else 'down'}", float(r["ibs"]), r["state"]], "ok": not bad})
        return cols, out, worst
