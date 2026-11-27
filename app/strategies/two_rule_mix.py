"""Two trend + credit rules with calm dips, half each, in one position (UWM, ProShares Ultra Russell 2000). Research "UWM (2x
Russell 2000)" rounds 2 and 3 (26 Nov 2026): rule A3 and rule R3, combined at the user's request (27 Nov 2026).

Signals from the 1x ETF (IWM) after each US close; orders at the next open. Each rule on its own:
  hold     IWM above its EMA(n) AND credit healthy (ratio above its SMA(credit_ma)) AND SPY above its SMA(spy_ma) AND IWM's
           20-day volatility (log changes × √252) under the rule's cap [AND, rule R, XLY ÷ XLP above its SMA(risk_ma)]
           → the rule's hold size (A3 99%, R3 75%)
  dip      not hold: after IWM closes with IBS < dip_ibs_max while IWM is calm (its 20-day volatility at or below its
           calm_pct percentile of the last calm_lookback days) → 100%; sold on a close above the previous day's high or
           after dip_days days; a dip ends when the rule's hold starts
  else     0
Money in the traded ETF = weight_a × rule A + weight_r × rule R (at most 100%), the rest cash.
Credit: A3 uses LQD ÷ IEF; R3 uses HYG ÷ IEF, with LQD ÷ IEF on days before HYG had credit_ma days of history.
All signal prices have dividends added back, as in the research.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .hk_crash import HkCrashStrategy
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"both": "#26A69A", "a_hold": "#4DB6AC", "r_hold": "#80CBC4", "dip": "#F5C76B", "out": "#4A5263"}
STATE_TEXT = {"both": "both rules hold", "a_hold": "rule A3 holds", "r_hold": "rule R3 holds", "dip": "dip trade", "out": "out · cash"}
TV.update({"UWM": "AMEX:UWM", "IWM": "AMEX:IWM", "HYG": "AMEX:HYG", "XLY": "AMEX:XLY", "XLP": "AMEX:XLP"})


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rule_weights(hold: np.ndarray, size: float, ibs: np.ndarray, calm: np.ndarray, close: np.ndarray, high: np.ndarray,
                 ibs_max: float, max_days: int):
    """Weight each day (decided at the close) and whether a dip trade is on."""
    n = len(hold)
    w, dip = np.zeros(n), np.zeros(n, dtype=bool)
    indip, days = False, 0
    for i in range(n):
        if hold[i]:
            indip = False
            w[i] = size
            continue
        if indip:
            days += 1
            if close[i] > high[i - 1] or days >= max_days:
                indip = False
        if not indip and ibs[i] < ibs_max and calm[i]:
            indip, days = True, 0
        dip[i] = indip
        w[i] = 1.0 if indip else 0.0
    return w, dip


def signals(data: dict, idx, p) -> pd.DataFrame:
    sig = data[p["signal"]].reindex(idx)
    c = sig["c"].astype(float)
    C = {s: data[s]["c"].astype(float).reindex(idx) for s in data}
    fr = pd.DataFrame(index=idx)
    fr["c"], fr["h"], fr["l"] = c.values, sig["h"].astype(float).values, sig["l"].astype(float).values
    rng = fr["h"] - fr["l"]
    fr["ibs"] = np.where(rng > 0, (fr["c"] - fr["l"]) / rng.where(rng > 0, 1.0), 0.5)
    vol = np.log(c).diff().rolling(int(p["vol_days"])).std() * np.sqrt(252)
    q = vol.rolling(int(p["calm_lookback"])).quantile(float(p["calm_pct"]) / 100)
    fr["vol"], fr["vol_q"] = vol.values, q.values
    calm = (vol <= q).fillna(False).values
    spy = C[p["spy"]]
    spy_ok = (spy > spy.rolling(int(p["spy_ma"])).mean()).values
    fr["spy_pct"] = ((spy / spy.rolling(int(p["spy_ma"])).mean() - 1) * 100).values
    cm = int(p["credit_ma"])
    lq = C["LQD"] / C["IEF"]
    lq_ok = lq > lq.rolling(cm).mean()
    fr["lqd_pct"] = ((lq / lq.rolling(cm).mean() - 1) * 100).values
    hy = C["HYG"] / C["IEF"] if "HYG" in C else lq
    hyma = hy.rolling(cm).mean()
    hy_ok = (hy > hyma).where(hyma.notna(), lq_ok)
    fr["hyg_pct"] = ((hy / hyma - 1) * 100).values
    rk = C["XLY"] / C["XLP"]
    rk_ok = (rk > rk.rolling(int(p["risk_ma"])).mean()).values
    fr["risk_pct"] = ((rk / rk.rolling(int(p["risk_ma"])).mean() - 1) * 100).values
    ok = ~(np.isnan(q.values) | np.isnan(lq.rolling(cm).mean().values) | np.isnan(spy.rolling(int(p["spy_ma"])).mean().values)
           | np.isnan(rk.rolling(int(p["risk_ma"])).mean().values))
    fr["ok"] = ok
    ea, er = ema(c, int(p["a_ema"])), ema(c, int(p["r_ema"]))
    fr["ema_a"], fr["ema_r"] = ea.values, er.values
    hold_a = (c > ea).values & lq_ok.values & spy_ok & (vol < float(p["a_vol_cap"]) / 100).values & ok
    hold_r = (c > er).values & hy_ok.fillna(False).astype(bool).values & spy_ok & (vol < float(p["r_vol_cap"]) / 100).values & rk_ok & ok
    args = (fr["ibs"].values, calm & ok, fr["c"].values, fr["h"].values, float(p["dip_ibs_max"]), int(p["dip_days"]))
    wa, da = rule_weights(hold_a, float(p["a_size_pct"]) / 100, *args)
    wr, dr = rule_weights(hold_r, float(p["r_size_pct"]) / 100, *args)
    fr["hold_a"], fr["hold_r"], fr["dip_a"], fr["dip_r"] = hold_a, hold_r, da, dr
    fr["calm"], fr["spy_ok"], fr["lqd_ok"], fr["hyg_ok"], fr["risk_ok"] = calm, spy_ok, lq_ok.values, hy_ok.fillna(False).values, rk_ok
    fr["wa"], fr["wr"] = wa, wr
    fr["w"] = np.minimum(1.0, float(p["weight_a"]) * wa + float(p["weight_r"]) * wr)
    fr["state"] = np.where(~ok, "", np.where(hold_a & hold_r, "both", np.where(hold_a, "a_hold", np.where(hold_r, "r_hold",
                           np.where(da | dr, "dip", "out")))))
    return fr


@register
class TwoRuleMixStrategy(RegimeStrategy):
    type = "two_rule_mix"
    label = "Two trend + credit rules with calm dips, half each (2x ETF read from its 1x)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: two hold rules on the 1x ETF (trend, credit, SPY, volatility cap; the second also needs consumer "
                   "discretionary ahead of staples) with calm-market dip trades, held half each in one 2x position.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "UWM", "group": "Symbols"},
        {"key": "signal", "label": "Signals from", "kind": "symbol", "default": "IWM", "group": "Symbols"},
        {"key": "spy", "label": "Market check", "kind": "symbol", "default": "SPY", "group": "Symbols"},
        {"key": "weight_a", "label": "Rule A3 share", "kind": "float", "default": 0.5, "min": 0, "max": 1, "group": "Mix"},
        {"key": "weight_r", "label": "Rule R3 share", "kind": "float", "default": 0.5, "min": 0, "max": 1, "group": "Mix"},
        {"key": "a_ema", "label": "A3: IWM above its EMA (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Rule A3"},
        {"key": "a_vol_cap", "label": "A3: hold only while IWM volatility under (%)", "kind": "float", "default": 35.0, "min": 5, "max": 200, "group": "Rule A3"},
        {"key": "a_size_pct", "label": "A3: hold size (%)", "kind": "float", "default": 99.0, "min": 10, "max": 100, "group": "Rule A3"},
        {"key": "r_ema", "label": "R3: IWM above its EMA (days)", "kind": "int", "default": 150, "min": 10, "max": 400, "group": "Rule R3"},
        {"key": "r_vol_cap", "label": "R3: hold only while IWM volatility under (%)", "kind": "float", "default": 30.0, "min": 5, "max": 200, "group": "Rule R3"},
        {"key": "r_size_pct", "label": "R3: hold size (%)", "kind": "float", "default": 75.0, "min": 10, "max": 100, "group": "Rule R3"},
        {"key": "risk_ma", "label": "R3: XLY ÷ XLP above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Rule R3"},
        {"key": "credit_ma", "label": "Credit above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Both rules",
         "help": "A3: LQD ÷ IEF · R3: HYG ÷ IEF"},
        {"key": "spy_ma", "label": "SPY above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Both rules"},
        {"key": "dip_ibs_max", "label": "Dip: IWM IBS below", "kind": "float", "default": 0.15, "min": 0.01, "max": 0.5, "group": "Dips"},
        {"key": "dip_days", "label": "Dip: sell after (days)", "kind": "int", "default": 5, "min": 1, "max": 20, "group": "Dips",
         "help": "Or on a close above the previous day's high"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Dips"},
        {"key": "calm_lookback", "label": "Calm: percentile over (days)", "kind": "int", "default": 252, "min": 60, "max": 1000, "group": "Dips"},
        {"key": "calm_pct", "label": "Calm: at or below percentile", "kind": "float", "default": 90.0, "min": 50, "max": 99, "group": "Dips"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["signal"], p["spy"], "LQD", "IEF", "HYG", "XLY", "XLP"]))

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def history_symbols(self):
        return self.read_symbols()

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

    def frame(self, now) -> pd.DataFrame:
        p = self.params
        data = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            # dividends added back (as in the research): the bond ETFs pay monthly, so on plain prices HYG ÷ IEF and LQD ÷ IEF
            # drift down by the yield gap and the credit checks would read "weak" far too often
            data[s] = HkCrashStrategy.dividend_adjusted(s, df[~df.index.duplicated(keep="last")])
        idx = data[p["signal"]].index
        fr = signals(data, idx, p)
        tr = data[p["trade"]].reindex(idx)
        for k in ("o", "h", "l", "c"):
            fr[f"t_{k}"] = tr[k].astype(float).values
        fr = fr[~np.isnan(fr["t_c"].values)]
        if not fr["ok"].any():
            raise md.DataError(f"Need {int(p['calm_lookback']) + int(p['vol_days']) + 2} daily bars of {p['signal']} and "
                               f"{int(p['spy_ma']) + 2} of {p['spy']}")
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

    def _part(self, r, key):
        p = self.params
        if r[f"hold_{key}"]:
            return f"hold {p[f'{key}_size_pct']:g}%"
        if r[f"dip_{key}"]:
            return "dip"
        return "out"

    def why(self, fr, i):
        p = self.params
        r = fr.iloc[i]
        return (f"Rule A3 {self._part(r, 'a')} · rule R3 {self._part(r, 'r')} → {r['w'] * 100:.0f}% {p['trade']} from the next open")

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

        def yn(b):
            return "up" if b else "dn"
        checks = [
            {"k": f"{p['signal']} vs EMA{p['a_ema']} (A3) · EMA{p['r_ema']} (R3)",
             "v": f"{last['c']:,.2f} vs {last['ema_a']:,.2f} · {last['ema_r']:,.2f}", "cls": yn(last["c"] > last["ema_r"] and last["c"] > last["ema_a"])},
            {"k": "Credit · LQD ÷ IEF (A3) · HYG ÷ IEF (R3)", "v": f"{last['lqd_pct']:+.2f}% · {last['hyg_pct']:+.2f}% vs their {p['credit_ma']}-day averages",
             "cls": yn(last["lqd_ok"] and last["hyg_ok"])},
            {"k": f"{p['spy']} vs SMA{p['spy_ma']}", "v": f"{last['spy_pct']:+.1f}%", "cls": yn(last["spy_ok"])},
            {"k": f"{p['signal']} volatility", "v": f"{last['vol'] * 100:.0f}% a year · caps A3 {p['a_vol_cap']:g}% / R3 {p['r_vol_cap']:g}% · calm line "
             f"{last['vol_q'] * 100:.0f}%", "cls": yn(last["vol"] < float(p["r_vol_cap"]) / 100), "h": "Dips need it at or below the calm line"},
            {"k": f"Risk-on · XLY ÷ XLP vs SMA{p['risk_ma']} (R3)", "v": f"{last['risk_pct']:+.2f}%", "cls": yn(last["risk_ok"])},
            {"k": f"IBS · {p['signal']}", "v": f"{last['ibs']:.2f}", "cls": "warn" if last["ibs"] < float(p["dip_ibs_max"]) else "",
             "h": f"Below {p['dip_ibs_max']:g} while calm and a rule is not holding → dip trade"},
            {"k": "Rules", "v": f"A3 {self._part(last, 'a')} · R3 {self._part(last, 'r')} → {pct}% {p['trade']} from the next open",
             "h": f"{p['weight_a']:g} × A3 + {p['weight_r']:g} × R3"}]
        tiles = [{"k": "both", "title": "Both rules hold", "text": f"{p['weight_a']:g} × {p['a_size_pct']:g}% + {p['weight_r']:g} × {p['r_size_pct']:g}%",
                  "hold": f"{(float(p['weight_a']) * float(p['a_size_pct']) + float(p['weight_r']) * float(p['r_size_pct'])):.0f}% {p['trade']}",
                  "color": STATE_COLOR["both"]},
                 {"k": "a_hold", "title": "Rule A3 holds", "text": f"{p['signal']} > EMA{p['a_ema']}, LQD credit, {p['spy']} > SMA{p['spy_ma']}, vol < {p['a_vol_cap']:g}%",
                  "hold": f"{float(p['weight_a']) * float(p['a_size_pct']):.0f}% (+ R3's dip if on)", "color": STATE_COLOR["a_hold"]},
                 {"k": "r_hold", "title": "Rule R3 holds", "text": f"{p['signal']} > EMA{p['r_ema']}, HYG credit, {p['spy']} > SMA{p['spy_ma']}, vol < "
                  f"{p['r_vol_cap']:g}%, XLY ÷ XLP up", "hold": f"{float(p['weight_r']) * float(p['r_size_pct']):.0f}% (+ A3's dip if on)",
                  "color": STATE_COLOR["r_hold"]},
                 {"k": "dip", "title": "Dip trade", "text": f"No rule holds; IBS < {p['dip_ibs_max']:g} while calm; out above the previous high or after "
                  f"{p['dip_days']} days", "hold": f"up to 100% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "out", "title": "Out", "text": "No rule holds, no dip", "hold": "cash", "color": STATE_COLOR["out"]}]

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
                             "vol": num(r["vol"] * 100), "a": self._part(r, "a"), "r": self._part(r, "r"), "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "sig", "label": p["signal"], "fmt": "n2"},
                    {"k": "ibs", "label": "IBS", "fmt": "n2"}, {"k": "vol", "label": "Vol %", "fmt": "n0"}, {"k": "a", "label": "A3"},
                    {"k": "r", "label": "R3"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
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
        fr = fr.assign(v100=fr["vol"] * 100, q100=fr["vol_q"] * 100)
        panes = [{"id": "vol", "title": f"{p['signal']} volatility (% a year)", "height": 80,
                  "lines": [{"name": "Volatility", "color": "#F5C76B", "width": 2, "data": ln("v100", 2)},
                            {"name": f"Calm line ({p['calm_pct']:g}th pct)", "color": "#26A69A", "width": 1, "data": ln("q100", 2)}],
                  "hlines": [{"value": float(p["r_vol_cap"]), "label": f"R3 cap {p['r_vol_cap']:g}%"}, {"value": float(p["a_vol_cap"]), "label": f"A3 cap {p['a_vol_cap']:g}%"}]},
                 {"id": "gates", "title": "Credit (LQD ÷ IEF, HYG ÷ IEF) and risk-on (XLY ÷ XLP), % vs their averages", "height": 80,
                  "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("lqd_pct", 3)},
                            {"name": "HYG ÷ IEF", "color": "#20C997", "width": 1, "data": ln("hyg_pct", 3)},
                            {"name": "XLY ÷ XLP", "color": "#E46AA8", "width": 1, "data": ln("risk_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                 {"id": "ibs", "title": f"IBS · {p['signal']}", "height": 60, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                  "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 70, "step": True,
                  "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}]
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — the rules are read from this chart",
               "candles": [{"time": t[i], "open": None, "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"EMA {p['a_ema']} (A3)", "color": "#FF9800", "width": 2, "data": ln("ema_a")},
                         {"name": f"EMA {p['r_ema']} (R3)", "color": "#2962FF", "width": 2, "data": ln("ema_r")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": panes, "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        sd = md.daily_closed(p["signal"], now)
        sd = HkCrashStrategy.dividend_adjusted(p["signal"], sd[~sd.index.duplicated(keep="last")]).reindex(fr.index)
        for i, cdl in enumerate(sig["candles"]):
            cdl["open"] = round(float(sd["o"].iloc[i]), 4)
        tr = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded",
              "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                           "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
              "lines": [], "markers": markers, "panes": [], "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, tr], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"After each US close, two rules read {p['signal']}; the money in {p['trade']} is {p['weight_a']:g} × rule A3 + {p['weight_r']:g} × rule R3.",
            f"Rule A3 holds {p['a_size_pct']:g}% while {p['signal']} > EMA{p['a_ema']}, LQD ÷ IEF > its {p['credit_ma']}-day average, {p['spy']} > SMA{p['spy_ma']} "
            f"and {p['signal']}'s 20-day volatility < {p['a_vol_cap']:g}%.",
            f"Rule R3 holds {p['r_size_pct']:g}% while {p['signal']} > EMA{p['r_ema']}, HYG ÷ IEF > its {p['credit_ma']}-day average, {p['spy']} > SMA{p['spy_ma']}, "
            f"volatility < {p['r_vol_cap']:g}% and XLY ÷ XLP > its {p['risk_ma']}-day average.",
            f"A rule that is not holding buys 100% after {p['signal']} closes with IBS < {p['dip_ibs_max']:g} while calm (volatility at or below its "
            f"{p['calm_pct']:g}th percentile of {p['calm_lookback']} days); sold on a close above the previous high or after {p['dip_days']} days.",
            "Orders at the next open; cash for the rest."],
            "flow": f"{p['signal']}, {p['spy']}, LQD/HYG ÷ IEF, XLY ÷ XLP daily → {p['trade']} · cash",
            "tv": f"{p['signal']} daily: EMA {p['a_ema']} and {p['r_ema']}; {p['spy']}: SMA {p['spy_ma']}; LQD/IEF, HYG/IEF and XLY/XLP ratio charts with SMA "
                  f"{p['credit_ma']} / {p['risk_ma']}",
            "rule": f"{p['trade']}: {p['weight_a']:g} × A3 ({p['signal']} > EMA{p['a_ema']}, LQD credit, SPY, vol < {p['a_vol_cap']:g}%) + {p['weight_r']:g} × R3 "
                    f"(> EMA{p['r_ema']}, HYG credit, SPY, vol < {p['r_vol_cap']:g}%, XLY/XLP up, {p['r_size_pct']:g}%), each with calm IBS dips; else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
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
                "bench": {sym: tr.dropna(subset=["c"]), p["signal"]: BT.daily_tr(p["signal"])}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym,
                "index": p["signal"], "data_from": str(days[0]),
                "data_note": f"{p['signal']}, {p['spy']}, LQD, IEF, HYG, XLY and XLP daily bars (signals) · {sym} daily total-return prices"}

    def check_table(self, now, rows=12):
        p = self.params
        fr = self.frame(now)
        sig = md.daily_closed(p["signal"], now)
        sig = HkCrashStrategy.dividend_adjusted(p["signal"], sig[~sig.index.duplicated(keep="last")])
        cl = sig["c"].astype(float).tolist()
        pos = {d: i for i, d in enumerate(sig.index)}
        cols = [p["signal"], f"EMA{p['a_ema']} · bot / check", "IBS · bot / check", "Held %"]
        out, worst = [], 0.0
        k = 2 / (int(p["a_ema"]) + 1)
        e = cl[0]
        emas = []
        for x in cl:
            e = x * k + e * (1 - k)
            emas.append(e)
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            i = pos[d]
            h, lo, c = float(sig["h"].iloc[i]), float(sig["l"].iloc[i]), cl[i]
            ibs = (c - lo) / (h - lo) if h > lo else 0.5
            diff = max(abs(r["ema_a"] - emas[i]) / max(emas[i], 1e-9), abs(r["ibs"] - ibs))
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()), "vals": [c, f"{r['ema_a']:,.3f} / {emas[i]:,.3f}", f"{r['ibs']:.3f} / {ibs:.3f}", float(r["w"] * 100)],
                        "ok": bool(diff < 1e-6)})
        return cols, out, worst
