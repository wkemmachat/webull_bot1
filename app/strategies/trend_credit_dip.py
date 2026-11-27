"""Trend + calm + credit, with one-day IBS dips sized by the storm (TSXU, Direxion 2x Semiconductors Top 5). Research "TSXU: 2 best
strategies" rounds 1–4 (26 Nov 2026): Strategy 2+, unbeaten after four rounds.

After each US close, from daily bars (signal at the close, trade at the next open):
  trend    SMH above its EMA(ema_days) with a band: on at a close above EMA × (1 + band), off at a close below EMA × (1 − band)
  calm     SMH's 20-day volatility (standard deviation of daily log changes) at or below its calm_q percentile of vol_lookback days
  credit   LQD ÷ IEF above its SMA(credit_ma) (dividends added back)
  hold     trend AND calm AND credit                                → 100% of the traded ETF (less the cash buffer)
  dip      not hold and SMH closes with IBS < dip_ibs_max           → dip_size_pct, or storm_size_pct when SMH's volatility is
           above its storm_q percentile; held while each close is another dip day, sold at the open after one that is not
  else     cash
Before the traded ETF listed (TSXU: 2 Oct 2025) the backtest models it as 2 × `model_basket`'s daily move minus model_cost_pct
a year (default 2 × SMH), joined to its first real close.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .hk_crash import HkCrashStrategy
from .momentum_calm import model_2x, parse_weights
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"hold": "#26A69A", "dip": "#F5C76B", "storm_dip": "#E8875A", "out": "#4A5263"}
STATE_TEXT = {"hold": "trend + calm + credit", "dip": "one-day dip buy", "storm_dip": "one-day dip buy (stormy: smaller)",
              "out": "out · cash"}
TV.update({"TSXU": "AMEX:TSXU"})


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    s = data[p["signal"]].reindex(idx)
    c = s["c"].astype(float)
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values
    fr["c"], fr["h"], fr["l"] = c.values, s["h"].astype(float).values, s["l"].astype(float).values
    rng = fr["h"] - fr["l"]
    fr["ibs"] = np.where(rng > 0, (fr["c"] - fr["l"]) / rng.where(rng > 0, 1.0), 0.5)
    full = data[p["signal"]]["c"].astype(float)
    e = full.ewm(span=int(p["ema_days"]), adjust=False).mean()
    v = np.log(full).diff().rolling(int(p["vol_days"])).std()
    q = v.rolling(int(p["vol_lookback"])).quantile(float(p["calm_q"]) / 100)
    qs = v.rolling(int(p["vol_lookback"])).quantile(float(p["storm_q"]) / 100)
    la = data["LQD"]["c"].astype(float) / data["IEF"]["c"].astype(float)
    lma = la.rolling(int(p["credit_ma"])).mean()
    fr["ema"], fr["vol"], fr["vol_q"], fr["vol_s"] = e.reindex(idx).values, v.reindex(idx).values, q.reindex(idx).values, qs.reindex(idx).values
    fr["credit_pct"] = ((la / lma - 1) * 100).reindex(idx).values
    ok = ~(np.isnan(fr["ema"].values) | np.isnan(fr["vol_q"].values) | np.isnan(fr["credit_pct"].values))
    b = float(p["band_pct"]) / 100
    n = len(fr)
    tr_on = np.zeros(n, dtype=bool)
    on = False
    cv, ev = fr["c"].values, fr["ema"].values
    for i in range(n):
        if ok[i]:
            if not on and cv[i] > ev[i] * (1 + b):
                on = True
            elif on and cv[i] < ev[i] * (1 - b):
                on = False
        tr_on[i] = on and ok[i]
    calm = ok & (fr["vol"].values <= fr["vol_q"].values)
    credit = ok & (fr["credit_pct"].values > 0)
    hold = tr_on & calm & credit
    dip = ok & ~hold & (fr["ibs"].values < float(p["dip_ibs_max"]))
    storm = fr["vol"].values > fr["vol_s"].values
    size = np.where(storm, float(p["storm_size_pct"]), float(p["dip_size_pct"])) / 100
    fr["trend"], fr["calm"], fr["credit"], fr["ok"], fr["storm"] = tr_on, calm, credit, ok, storm
    fr["w"] = np.where(hold, 1.0, np.where(dip, size, 0.0))
    fr["state"] = np.where(~ok, "", np.where(hold, "hold", np.where(dip & storm, "storm_dip", np.where(dip, "dip", "out"))))
    return fr


@register
class TrendCreditDipStrategy(RegimeStrategy):
    type = "trend_credit_dip"
    label = "Trend + calm + credit with one-day IBS dips (2x ETF read from SMH)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds a 2x chip ETF while SMH is above its 200-day EMA, calm, and credit is healthy; otherwise buys one-day "
                   "dips after SMH closes near its low (smaller when stormy); cash else.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "TSXU", "group": "Symbols"},
        {"key": "signal", "label": "Signals from", "kind": "symbol", "default": "SMH", "group": "Symbols"},
        {"key": "ema_days", "label": "Trend: above its EMA (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Hold"},
        {"key": "band_pct", "label": "Trend band (%)", "kind": "float", "default": 1.0, "min": 0, "max": 10, "group": "Hold",
         "help": "On above EMA × (1 + band), off below EMA × (1 − band)"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Hold"},
        {"key": "vol_lookback", "label": "Percentile lookback (days)", "kind": "int", "default": 252, "min": 60, "max": 1000, "group": "Hold"},
        {"key": "calm_q", "label": "Calm: at or below percentile", "kind": "float", "default": 90.0, "min": 50, "max": 99, "group": "Hold"},
        {"key": "credit_ma", "label": "Credit: LQD ÷ IEF above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Hold"},
        {"key": "dip_ibs_max", "label": "Dip: SMH IBS below (0 = off)", "kind": "float", "default": 0.25, "min": 0, "max": 0.5, "group": "Dips"},
        {"key": "dip_size_pct", "label": "Dip size (%)", "kind": "float", "default": 100.0, "min": 0, "max": 100, "group": "Dips"},
        {"key": "storm_q", "label": "Stormy: volatility above percentile", "kind": "float", "default": 95.0, "min": 50, "max": 100, "group": "Dips"},
        {"key": "storm_size_pct", "label": "Dip size when stormy (%)", "kind": "float", "default": 75.0, "min": 0, "max": 100, "group": "Dips"},
        {"key": "model_basket", "label": "Backtest: model before listing (symbol:weight)", "kind": "text", "default": "SMH:100", "group": "Backtest"},
        {"key": "model_cost_pct", "label": "Backtest: model cost (% a year)", "kind": "float", "default": 5.0, "min": 0, "max": 100, "group": "Backtest",
         "help": "Fee, financing and spread of a 2x fund"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["signal"], "LQD", "IEF"]))

    def history_symbols(self):
        return list(dict.fromkeys(self.read_symbols() + list(parse_weights(self.params["model_basket"]))))

    def data_needs(self):
        return [(s, "1d") for s in self.history_symbols()]

    def bench_extra(self):
        return [self.params["signal"]]

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
            data[s] = HkCrashStrategy.dividend_adjusted(s, df) if s in ("LQD", "IEF", p["signal"]) else df
        tr = data[p["trade"]]
        if model:
            tr = model_2x(tr, data, parse_weights(p["model_basket"]), data[p["signal"]].index, float(p["model_cost_pct"]) / 100)
        fr = signals(tr, data, p)
        if not fr["ok"].any():
            raise md.DataError(f"Need {int(p['vol_lookback']) + int(p['vol_days']) + 2} daily bars of {p['signal']}")
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
        r, a = fr.iloc[i], fr["state"].iloc[i - 1]
        z = r["state"]
        if z == "hold":
            return f"Hold: {p['signal']} above its EMA{p['ema_days']}, calm, credit healthy · {p['trade']} 100% from the next open"
        if z in ("dip", "storm_dip"):
            return (f"Dip: {p['signal']} IBS {r['ibs']:.2f} < {p['dip_ibs_max']:g} · {r['w'] * 100:.0f}% {p['trade']} at the next open"
                    + (" (stormy)" if z == "storm_dip" else ""))
        if a in ("dip", "storm_dip"):
            return "Dip sold at the next open"
        bits = []
        if not r["trend"]:
            bits.append(f"{p['signal']} below its EMA{p['ema_days']}")
        if not r["calm"]:
            bits.append(f"{p['signal']} not calm")
        if not r["credit"]:
            bits.append("credit weak")
        return "Out: " + ", ".join(bits or ["no signal"]) + " · sell at the next open"

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
            {"k": f"Trend · {p['signal']} vs EMA{p['ema_days']}", "v": f"{last['c']:,.2f} vs {last['ema']:,.2f} · {(last['c'] / last['ema'] - 1) * 100:+.1f}%",
             "cls": "up" if last["trend"] else "dn", "h": f"On above EMA +{p['band_pct']:g}%, off below EMA −{p['band_pct']:g}%"},
            {"k": f"Calm · {p['signal']} {p['vol_days']}-day volatility", "v": f"{last['vol'] * np.sqrt(252) * 100:.0f}% a year vs "
             f"{last['vol_q'] * np.sqrt(252) * 100:.0f}% ({p['calm_q']:g}th percentile of {p['vol_lookback']} days)", "cls": "up" if last["calm"] else "dn"},
            {"k": f"Credit · LQD ÷ IEF vs SMA{p['credit_ma']}", "v": f"{last['credit_pct']:+.2f}%", "cls": "up" if last["credit"] else "dn"},
            {"k": f"IBS · {p['signal']}", "v": f"{last['ibs']:.2f}" + (" · stormy" if last["storm"] else ""),
             "cls": "warn" if last["ibs"] < float(p["dip_ibs_max"]) else "",
             "h": f"Out of the hold: below {p['dip_ibs_max']:g} → {p['dip_size_pct']:g}% for a day ({p['storm_size_pct']:g}% when volatility is above its "
                  f"{p['storm_q']:g}th percentile)"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open"}]
        tiles = [{"k": "hold", "title": "In · trend + calm + credit", "text": f"{p['signal']} above EMA{p['ema_days']}, calm, LQD ÷ IEF above SMA{p['credit_ma']}",
                  "hold": f"100% {p['trade']}", "color": STATE_COLOR["hold"]},
                 {"k": "dip", "title": "In · one-day dip", "text": f"Hold off, {p['signal']} IBS < {p['dip_ibs_max']:g}", "hold": f"{p['dip_size_pct']:g}% {p['trade']}",
                  "color": STATE_COLOR["dip"]},
                 {"k": "storm_dip", "title": "In · dip, stormy", "text": f"As above, {p['signal']} volatility above its {p['storm_q']:g}th percentile",
                  "hold": f"{p['storm_size_pct']:g}% {p['trade']}", "color": STATE_COLOR["storm_dip"]},
                 {"k": "out", "title": "Out", "text": "No hold, no dip", "hold": "cash", "color": STATE_COLOR["out"]}]

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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "sig": num(r["c"]), "ibs": num(r["ibs"]),
                             "vs": num((r["c"] / r["ema"] - 1) * 100), "calm": "yes" if r["calm"] else "no", "credit": "ok" if r["credit"] else "weak",
                             "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "sig", "label": p["signal"], "fmt": "n2"},
                    {"k": "vs", "label": f"vs EMA{p['ema_days']} %", "fmt": "n1"}, {"k": "ibs", "label": "IBS", "fmt": "n2"},
                    {"k": "calm", "label": "Calm"}, {"k": "credit", "label": "Credit"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = f"IN · {pct}% {p['trade']} · {STATE_TEXT[s]}" if pct > 0 else "OUT · cash"
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
        k = np.sqrt(252) * 100
        fr = fr.assign(va=fr["vol"] * k, qa=fr["vol_q"] * k, sa=fr["vol_s"] * k)
        sd = md.daily_closed(p["signal"], now)
        sd = HkCrashStrategy.dividend_adjusted(p["signal"], sd[~sd.index.duplicated(keep="last")]).reindex(fr.index)
        panes = [{"id": "vol", "title": f"{p['signal']} volatility (% a year)", "height": 80,
                  "lines": [{"name": "Volatility", "color": "#F5C76B", "width": 2, "data": ln("va", 2)},
                            {"name": f"Calm line ({p['calm_q']:g}th)", "color": "#26A69A", "width": 1, "data": ln("qa", 2)},
                            {"name": f"Storm line ({p['storm_q']:g}th)", "color": "#EF5350", "width": 1, "data": ln("sa", 2)}], "hlines": []},
                 {"id": "credit", "title": f"Credit · LQD ÷ IEF, % vs its {p['credit_ma']}-day average", "height": 60,
                  "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("credit_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                 {"id": "ibs", "title": f"IBS · {p['signal']}", "height": 60, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                  "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                  "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}]
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — trend, calm and dips are read from this chart (dividends added back)",
               "candles": [{"time": t[i], "open": round(float(sd["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"EMA {p['ema_days']}", "color": "#FF9800", "width": 2, "data": ln("ema")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": panes, "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        trd = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "markers": markers, "panes": [], "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, trd], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close: hold 100% {p['trade']} while {p['signal']} is above its {p['ema_days']}-day EMA ({p['band_pct']:g}% band), {p['signal']} is calm "
            f"(20-day volatility at or below its {p['calm_q']:g}th percentile of {p['vol_lookback']} days) and LQD ÷ IEF is above its {p['credit_ma']}-day average.",
            f"Otherwise, after {p['signal']} closes with IBS < {p['dip_ibs_max']:g}: buy {p['dip_size_pct']:g}% ({p['storm_size_pct']:g}% when its volatility is above "
            f"the {p['storm_q']:g}th percentile) at the next open; held while each close is another dip day, sold at the open after one that is not.",
            "Otherwise cash. Orders at the next open."],
            "flow": f"{p['signal']} + LQD ÷ IEF daily → {p['trade']} · cash",
            "tv": f"{p['signal']} daily: EMA {p['ema_days']}; LQD/IEF ratio with SMA {p['credit_ma']}; IBS = (close − low) / (high − low)",
            "rule": f"{p['trade']} while {p['signal']} > EMA{p['ema_days']} (±{p['band_pct']:g}%), calm and LQD/IEF > SMA{p['credit_ma']}; one-day dips "
                    f"{p['signal']} IBS < {p['dip_ibs_max']:g} ({p['storm_size_pct']:g}% when stormy); else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        weights = parse_weights(p["model_basket"])
        base = BT.daily_tr(p["signal"])
        tr = model_2x(BT.daily_tr(sym), {s: BT.daily_tr(s) for s in weights}, weights, base.index,
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
                "bench": {sym: tr.dropna(subset=["c"]), p["signal"]: base}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": p["signal"],
                "data_from": str(days[0]),
                "data_note": f"{p['signal']}, LQD and IEF daily bars with dividends added back (signals) · {sym} daily total-return prices; {sym} before "
                             f"{listed}: modelled as 2 × ({', '.join(f'{k} {v * 100:.0f}%' for k, v in weights.items())}) daily minus {p['model_cost_pct']:g}% a year"}

    def check_table(self, now, rows=12):
        p = self.params
        fr = self.frame(now)
        sig = md.daily_closed(p["signal"], now)
        sig = HkCrashStrategy.dividend_adjusted(p["signal"], sig[~sig.index.duplicated(keep="last")])
        cl = sig["c"].astype(float).tolist()
        pos = {d: i for i, d in enumerate(sig.index)}
        k = 2 / (int(p["ema_days"]) + 1)
        e = cl[0]
        emas = []
        for x in cl:
            e = x * k + e * (1 - k)
            emas.append(e)
        cols = [p["signal"], f"EMA{p['ema_days']} · bot / check", "IBS · bot / check", "Held %"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            i = pos[d]
            h, lo, c = float(sig["h"].iloc[i]), float(sig["l"].iloc[i]), cl[i]
            ibs = (c - lo) / (h - lo) if h > lo else 0.5
            diff = max(abs(r["ema"] - emas[i]) / max(emas[i], 1e-9), abs(r["ibs"] - ibs))
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()), "vals": [c, f"{r['ema']:,.3f} / {emas[i]:,.3f}", f"{r['ibs']:.3f} / {ibs:.3f}", float(r["w"] * 100)],
                        "ok": bool(diff < 1e-6)})
        return cols, out, worst
