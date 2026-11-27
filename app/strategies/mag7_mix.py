"""Half Strategy 1+, half Strategy 2++ (MAGX, Roundhill Daily 2X Long Magnificent Seven ETF). Research "MAGX (2x Magnificent
Seven): 2 best strategies" rounds 1–3 (26 Nov 2026); combined in one position on 27 Nov 2026.

Signals come from an equal-weight basket of the seven stocks, re-weighted to equal at the start of each quarter (a stock joins at
the first quarter after it listed). After each US close (signal at the close, trade at the next open):
  trend   the basket's close breaks its previous dc_entry-day high → on; closes below its previous dc_exit-day low → off
  gates   the basket is calm (20-day volatility at or below its calm_q percentile of 252 days), LQD ÷ IEF above its SMA(credit_ma),
          SPY above its SMA(spy_ma). "Trend part on" = trend AND gates.
  S1+     trend part on → min(1, vt1 ÷ MAGX's 20-day volatility); else a deep dip: after the basket's RSI2 (Wilder) closes
          < deep_rsi, hold deep_pct until the first close with RSI2 > deep_exit_rsi, or deep_days closes
  S2++    trend part on → min(1, vt2 ÷ MAGX's volatility); else the larger of a one-day buy of day_pct after RSI2 < day_rsi
          (held while each close repeats it) and the same deep dip
  held    share1 × S1+ + share2 × S2++ of MAGX (each trend size changes only on a move of resize_band_pct points or more)
Before MAGX listed (29 Feb 2024) the backtest models it as 2 × the basket's daily move minus model_cost_pct a year.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .half_trend_dip import dip_weights
from .hk_crash import HkCrashStrategy
from .quantum_mix import rsi
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"trend": "#26A69A", "deep": "#E8875A", "day": "#F5C76B", "out": "#4A5263"}
STATE_TEXT = {"trend": "trend part (both halves)", "deep": "deep dip (RSI2 < 5)", "day": "one-day dip (S2++ half)", "out": "out · cash"}
TV.update({"MAGX": "AMEX:MAGX"})


def parse_list(text) -> list:
    return [s.strip().upper() for s in str(text).replace(";", ",").split(",") if s.strip()]


def quarterly_basket(stocks: dict, idx) -> pd.DataFrame:
    """Equal-weight basket re-weighted at the first session of each quarter; between those days each member's share drifts with
    its price. A member joins at the first quarter start after its first close. Returns o/h/l/c of an index (100 at the start)
    built from the members' moves from the previous close, and n = members held."""
    idx = pd.DatetimeIndex(idx)
    cols = list(stocks)
    C = pd.DataFrame({s: stocks[s]["c"].astype(float).reindex(idx) for s in cols})
    rel = {k: pd.DataFrame({s: stocks[s][k].astype(float).reindex(idx) for s in cols}) / C.shift(1) - 1 for k in ("o", "h", "l", "c")}
    q = (idx.tz_localize(None) if idx.tz is not None else idx).to_period("Q")
    qstart = np.r_[True, q[1:] != q[:-1]]
    first = {s: C[s].first_valid_index() for s in cols}
    n = len(idx)
    W = np.zeros((n, len(cols)))
    w = np.zeros(len(cols))
    rc = rel["c"].values
    for i in range(n):
        if qstart[i]:
            have = np.array([first[s] is not None and first[s] < idx[i] and not np.isnan(C[s].values[i - 1] if i else np.nan) for s in cols])
            w = have / have.sum() if have.any() else np.zeros(len(cols))
        W[i] = w                                              # weights held into day i (set at the previous close)
        g = np.where(np.isnan(rc[i]), 0.0, rc[i])
        tot = float((w * (1 + g)).sum())
        if tot > 0:
            w = w * (1 + g) / tot
    out = pd.DataFrame(index=idx)
    m = {}
    for k in ("o", "h", "l", "c"):
        r = np.where(np.isnan(rel[k].values), 0.0, rel[k].values)
        m[k] = (W * r).sum(axis=1)
    held = W.sum(axis=1) > 0
    c = np.cumprod(np.where(held, 1 + m["c"], 1.0)) * 100
    prev = np.r_[100.0, c[:-1]]
    out["o"], out["h"], out["l"], out["c"] = prev * (1 + m["o"]), prev * (1 + m["h"]), prev * (1 + m["l"]), c
    out["rc"] = np.where(held, m["c"], np.nan)
    out["n"] = (W > 0).sum(axis=1)
    return out


def model_from_basket(real: pd.DataFrame | None, bk: pd.DataFrame, cost_y: float) -> pd.DataFrame:
    """2 × the basket's daily move (open, high, low, close from the previous close) minus cost, joined to `real`'s first close."""
    b = bk[bk["n"] > 0]
    prev = b["c"].shift(1)
    ro, rh, rl, rc = ((b[k] / prev - 1).values for k in ("o", "h", "l", "c"))
    n = len(b)
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    p = 100.0
    for i in range(1, n):
        o[i] = p * (1 + 2 * ro[i])
        cc = p * (1 + 2 * rc[i] - cost_y / 252)
        h[i] = max(p * (1 + 2 * rh[i]), o[i], cc)
        l[i] = min(p * (1 + 2 * rl[i]), o[i], cc)
        c[i] = p = cc
    M = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": 0.0}, index=b.index).dropna(subset=["c"])
    if real is None or real.empty:
        return M
    J = real.index[0]
    if J not in M.index:
        return real
    f = float(real["c"].iloc[0]) / float(M.loc[J, "c"])
    early = M[M.index < J].copy()
    for k in ("o", "h", "l", "c"):
        early[k] = early[k] * f
    return pd.concat([early, real[["o", "h", "l", "c", "v"]]])


def sticky(target: np.ndarray, band: float) -> np.ndarray:
    """A size that changes only when the new target is `band` or more away from the size held (0 ↔ non-zero always changes)."""
    out = np.zeros(len(target))
    cur = 0.0
    for i, t in enumerate(target):
        if t <= 0 or cur <= 0 or abs(t - cur) >= band - 1e-12:
            cur = float(t)
        out[i] = cur
    return out


def signals(tr: pd.DataFrame, bk: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values
    b = bk.reindex(idx)
    C = b["c"].astype(float)
    fr["b_c"], fr["n"] = C.values, b["n"].fillna(0).values
    hi = C.shift(1).rolling(int(p["dc_entry"])).max()
    lo = C.shift(1).rolling(int(p["dc_exit"])).min()
    fr["dc_hi"], fr["dc_lo"] = hi.values, lo.values
    v = np.log(C).diff().rolling(20).std()
    fr["b_vol"], fr["b_vol_q"] = v.values, v.rolling(252).quantile(float(p["calm_q"]) / 100).values
    la = data["LQD"]["c"].astype(float) / data["IEF"]["c"].astype(float)
    fr["credit_pct"] = ((la / la.rolling(int(p["credit_ma"])).mean() - 1) * 100).reindex(idx).values
    spy = data["SPY"]["c"].astype(float)
    fr["spy"], fr["spy_ma"] = spy.reindex(idx).values, spy.rolling(int(p["spy_ma"])).mean().reindex(idx).values
    fr["rsi2"] = rsi(C, 2).values
    mv = np.log(tr["c"].astype(float)).diff().rolling(20).std() * np.sqrt(252)
    fr["m_vol"] = mv.values
    need = ["dc_hi", "dc_lo", "b_vol_q", "credit_pct", "spy_ma", "rsi2", "m_vol"]
    ok = ~fr[need].isna().any(axis=1).values & (fr["n"].values >= int(p["min_members"]))
    n = len(fr)
    st = np.zeros(n, dtype=bool)
    on = False
    cv, hv, lv = C.values, hi.values, lo.values
    for i in range(n):
        if ok[i]:
            if not on and cv[i] > hv[i]:
                on = True
            elif on and cv[i] < lv[i]:
                on = False
        st[i] = on and ok[i]
    calm = ok & (fr["b_vol"].values <= fr["b_vol_q"].values)
    credit = ok & (fr["credit_pct"].values > 0)
    spy_ok = ok & (fr["spy"].values > fr["spy_ma"].values)
    trend = st & calm & credit & spy_ok
    r2 = fr["rsi2"].values
    deep = dip_weights(ok & ~trend & (r2 < float(p["deep_rsi"])), r2 / 100.0, float(p["deep_exit_rsi"]) / 100.0, int(p["deep_days"]))
    day = ok & ~trend & (r2 < float(p["day_rsi"]))
    band = float(p["resize_band_pct"]) / 100
    mvol = np.where(np.isnan(fr["m_vol"].values) | (fr["m_vol"].values <= 0), np.inf, fr["m_vol"].values)
    t1 = sticky(np.where(trend, np.minimum(1.0, float(p["vt1_pct"]) / 100 / mvol), 0.0), band)
    t2 = sticky(np.where(trend, np.minimum(1.0, float(p["vt2_pct"]) / 100 / mvol), 0.0), band)
    dp, yp = float(p["deep_pct"]) / 100, float(p["day_pct"]) / 100
    fr["w1"] = np.where(trend, t1, np.where(deep, dp, 0.0))
    fr["w2"] = np.where(trend, t2, np.maximum(np.where(day, yp, 0.0), np.where(deep, dp, 0.0)))
    s1, s2 = float(p["share1_pct"]) / 100, float(p["share2_pct"]) / 100
    fr["w"] = np.minimum(1.0, s1 * fr["w1"].values + s2 * fr["w2"].values)
    fr["dc_on"], fr["calm"], fr["credit"], fr["spy_ok"], fr["trend"], fr["deep"], fr["day"], fr["ok"] = st, calm, credit, spy_ok, trend, deep, day, ok
    fr["state"] = np.where(~ok, "", np.where(trend, "trend", np.where(deep, "deep", np.where(day, "day", "out"))))
    return fr


@register
class Mag7MixStrategy(RegimeStrategy):
    type = "mag7_mix"
    label = "Magnificent Seven basket: breakout trend + gates, RSI2 dips (half S1+, half S2++)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: an equal-weight Mag 7 basket's 55/20-day breakout, while calm, credit healthy and SPY above SMA200, sized by "
                   "MAGX volatility; otherwise RSI2 dip buys. Half Strategy 1+, half Strategy 2++.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "MAGX", "group": "Symbols"},
        {"key": "basket", "label": "Basket (equal weight, re-weighted each quarter)", "kind": "text",
         "default": "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA", "group": "Symbols"},
        {"key": "min_members", "label": "Signals need at least (members)", "kind": "int", "default": 5, "min": 1, "max": 20, "group": "Symbols"},
        {"key": "dc_entry", "label": "Trend: close above the previous high of (days)", "kind": "int", "default": 55, "min": 5, "max": 250, "group": "Trend"},
        {"key": "dc_exit", "label": "Trend ends: close below the previous low of (days)", "kind": "int", "default": 20, "min": 5, "max": 250, "group": "Trend"},
        {"key": "calm_q", "label": "Calm: basket volatility at or below percentile", "kind": "float", "default": 90.0, "min": 50, "max": 99, "group": "Trend"},
        {"key": "credit_ma", "label": "Credit: LQD ÷ IEF above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Trend"},
        {"key": "spy_ma", "label": "Market: SPY above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend"},
        {"key": "vt1_pct", "label": "S1+ trend size: target volatility (%)", "kind": "float", "default": 60.0, "min": 5, "max": 300, "group": "Trend"},
        {"key": "vt2_pct", "label": "S2++ trend size: target volatility (%)", "kind": "float", "default": 80.0, "min": 5, "max": 300, "group": "Trend"},
        {"key": "resize_band_pct", "label": "Resize the trend only on a change of (points)", "kind": "float", "default": 20.0, "min": 0, "max": 100, "group": "Trend"},
        {"key": "deep_rsi", "label": "Deep dip: basket RSI2 below", "kind": "float", "default": 5.0, "min": 0, "max": 50, "group": "Dips"},
        {"key": "deep_pct", "label": "Deep dip size (%)", "kind": "float", "default": 75.0, "min": 0, "max": 100, "group": "Dips"},
        {"key": "deep_exit_rsi", "label": "Deep dip ends: RSI2 above", "kind": "float", "default": 50.0, "min": 10, "max": 100, "group": "Dips"},
        {"key": "deep_days", "label": "Deep dip ends after (closes)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Dips"},
        {"key": "day_rsi", "label": "S2++ one-day dip: RSI2 below (0 = off)", "kind": "float", "default": 10.0, "min": 0, "max": 50, "group": "Dips"},
        {"key": "day_pct", "label": "S2++ one-day dip size (%)", "kind": "float", "default": 100.0, "min": 0, "max": 100, "group": "Dips"},
        {"key": "share1_pct", "label": "Share in Strategy 1+ (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Mix"},
        {"key": "share2_pct", "label": "Share in Strategy 2++ (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Mix"},
        {"key": "model_cost_pct", "label": "Backtest: model cost before listing (% a year)", "kind": "float", "default": 8.0, "min": 0, "max": 50,
         "group": "Backtest", "help": "Fee, financing and the extra drag of a 2x fund"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money"},
    ]

    def basket(self):
        return parse_list(self.params["basket"])

    def read_symbols(self):
        return list(dict.fromkeys([self.params["trade"]] + self.basket() + ["SPY", "LQD", "IEF"]))

    history_symbols = read_symbols

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def bench_extra(self):
        return ["QQQ"]

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

    def inputs(self, now):
        data = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            df = df[~df.index.duplicated(keep="last")]
            data[s] = df if s == self.params["trade"] else HkCrashStrategy.dividend_adjusted(s, df)
        idx = data["SPY"].index
        bk = quarterly_basket({s: data[s] for s in self.basket()}, idx)
        return data, bk

    def frame(self, now, model=False) -> pd.DataFrame:
        p = self.params
        data, bk = self.inputs(now)
        tr = data[p["trade"]]
        if model:
            tr = model_from_basket(tr, bk, float(p["model_cost_pct"]) / 100)
        fr = signals(tr, bk, data, p)
        if not fr["ok"].any():
            raise md.DataError("Need about 280 daily bars of the basket, SPY, LQD and IEF")
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
        r = fr.iloc[i]
        a = fr.iloc[i - 1] if i > 0 else r
        z, tail = r["state"], f" · {p['trade']} {r['w'] * 100:.0f}% from the next open"
        if z == "trend":
            if a["state"] != "trend":
                return f"Trend part on: basket above its {p['dc_entry']}-day high, calm, credit healthy, SPY above SMA{p['spy_ma']}" + tail
            return f"Trend size changed (MAGX volatility {r['m_vol'] * 100:.0f}%)" + tail
        if z == "deep":
            return (f"Deep dip: basket RSI2 {r['rsi2']:.1f} < {p['deep_rsi']:g}" if a["state"] != "deep" else "Deep dip held") + tail
        if z == "day":
            return f"One-day dip (S2++ half): basket RSI2 {r['rsi2']:.1f} < {p['day_rsi']:g}" + tail
        if a["state"] == "trend":
            bits = []
            if not r["dc_on"]:
                bits.append(f"basket below its {p['dc_exit']}-day low")
            if not r["calm"]:
                bits.append("basket not calm")
            if not r["credit"]:
                bits.append("credit weak")
            if not r["spy_ok"]:
                bits.append(f"SPY below SMA{p['spy_ma']}")
            return "Trend part off: " + ", ".join(bits or ["gate failed"]) + tail
        if a["state"] == "deep":
            return f"Deep dip ended (RSI2 {r['rsi2']:.0f})" + tail
        return "Dip sold" + tail

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
            {"k": f"Trend · basket vs its previous {p['dc_entry']}-day high / {p['dc_exit']}-day low",
             "v": f"{(last['b_c'] / last['dc_hi'] - 1) * 100:+.1f}% vs the high · {(last['b_c'] / last['dc_lo'] - 1) * 100:+.1f}% vs the low · "
                  f"{'on' if last['dc_on'] else 'off'}", "cls": "up" if last["dc_on"] else "dn",
             "h": "On at a close above the high, off at a close below the low"},
            {"k": "Calm · basket 20-day volatility", "v": f"{last['b_vol'] * np.sqrt(252) * 100:.0f}% a year vs {last['b_vol_q'] * np.sqrt(252) * 100:.0f}% "
             f"({p['calm_q']:g}th percentile)", "cls": "up" if last["calm"] else "dn"},
            {"k": f"Credit · LQD ÷ IEF vs SMA{p['credit_ma']}", "v": f"{last['credit_pct']:+.2f}%", "cls": "up" if last["credit"] else "dn"},
            {"k": f"Market · SPY vs SMA{p['spy_ma']}", "v": f"{last['spy']:,.2f} vs {last['spy_ma']:,.2f} · {(last['spy'] / last['spy_ma'] - 1) * 100:+.1f}%",
             "cls": "up" if last["spy_ok"] else "dn"},
            {"k": "Size · MAGX 20-day volatility", "v": f"{last['m_vol'] * 100:.0f}% a year → trend size {min(1, p['vt1_pct'] / 100 / last['m_vol']) * 100:.0f}% "
             f"(S1+) / {min(1, p['vt2_pct'] / 100 / last['m_vol']) * 100:.0f}% (S2++)"},
            {"k": "Dips · basket RSI2", "v": f"{last['rsi2']:.1f}" + (" · deep dip open" if last["deep"] else ""),
             "cls": "warn" if last["rsi2"] < float(p["day_rsi"]) else "",
             "h": f"Out of the trend: below {p['day_rsi']:g} → S2++ half 100% for a day; below {p['deep_rsi']:g} → both halves {p['deep_pct']:g}% until "
                  f"RSI2 > {p['deep_exit_rsi']:g} or {p['deep_days']} closes"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open (S1+ {last['w1'] * 100:.0f}% · S2++ {last['w2'] * 100:.0f}%)"}]
        tiles = [{"k": "trend", "title": "In · trend part", "text": f"Basket breakout, calm, credit, SPY > SMA{p['spy_ma']}",
                  "hold": "60–100% MAGX by volatility", "color": STATE_COLOR["trend"]},
                 {"k": "deep", "title": "In · deep dip", "text": f"RSI2 < {p['deep_rsi']:g}, up to {p['deep_days']} closes", "hold": f"{p['deep_pct']:g}% MAGX",
                  "color": STATE_COLOR["deep"]},
                 {"k": "day", "title": "In · one-day dip", "text": f"RSI2 < {p['day_rsi']:g} (S2++ half only)", "hold": f"{p['day_pct'] * p['share2_pct'] / 100:g}% MAGX",
                  "color": STATE_COLOR["day"]},
                 {"k": "out", "title": "Out", "text": "No trend, no dip", "hold": "cash", "color": STATE_COLOR["out"]}]

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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "basket": num(r["b_c"]), "rsi2": num(r["rsi2"]),
                             "dc": "on" if r["dc_on"] else "off", "calm": "yes" if r["calm"] else "no", "credit": "ok" if r["credit"] else "weak",
                             "spy": "above" if r["spy_ok"] else "below", "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "basket", "label": "Basket", "fmt": "n1"}, {"k": "dc", "label": "Breakout"},
                    {"k": "calm", "label": "Calm"}, {"k": "credit", "label": "Credit"}, {"k": "spy", "label": f"SPY vs SMA{p['spy_ma']}"},
                    {"k": "rsi2", "label": "RSI2", "fmt": "n1"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = f"IN · {pct}% {p['trade']} · {STATE_TEXT[s]}" if pct > 0 else "OUT · cash"
        return {"ok": True, "state": s, "label": label, "target": self.target_w(last["w"]),
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": num(last["t_c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": num(last["t_c"]), "state_text": STATE_TEXT[s], "title": "Position · decided after each US close"}}

    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        _, bk = self.inputs(now)
        bk = bk.reindex(fr.index)
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
        fr = fr.assign(va=fr["b_vol"] * k, qa=fr["b_vol_q"] * k)
        sig = {"id": "signal", "title": "Mag 7 basket · 1D", "subtitle": f"Signal — equal weight {', '.join(self.basket())}, re-weighted each quarter (index)",
               "candles": [{"time": t[i], "open": round(float(bk["o"].iloc[i]), 3), "high": round(float(bk["h"].iloc[i]), 3),
                            "low": round(float(bk["l"].iloc[i]), 3), "close": round(float(bk["c"].iloc[i]), 3)} for i in range(len(fr))],
               "lines": [{"name": f"Previous {p['dc_entry']}-day high", "color": "#26A69A", "width": 1, "data": ln("dc_hi", 3)},
                         {"name": f"Previous {p['dc_exit']}-day low", "color": "#EF5350", "width": 1, "data": ln("dc_lo", 3)}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": [{"id": "vol", "title": "Basket volatility (% a year)", "height": 70,
                          "lines": [{"name": "Volatility", "color": "#F5C76B", "width": 2, "data": ln("va", 2)},
                                    {"name": f"Calm line ({p['calm_q']:g}th)", "color": "#26A69A", "width": 1, "data": ln("qa", 2)}], "hlines": []},
                         {"id": "rsi", "title": "Basket RSI2", "height": 60, "lines": [{"name": "RSI2", "color": "#F5C76B", "width": 1, "data": ln("rsi2", 2)}],
                          "hlines": [{"value": float(p["day_rsi"]), "label": f"{p['day_rsi']:g}"}, {"value": float(p["deep_rsi"]), "label": f"{p['deep_rsi']:g}"}]},
                         {"id": "credit", "title": f"Credit · LQD ÷ IEF, % vs its {p['credit_ma']}-day average", "height": 50,
                          "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("credit_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                          "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}],
               "markers": markers, "tv": None, "tv_symbol": None}
        trd = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "markers": markers, "panes": [], "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, trd], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"Signals from an equal-weight basket of {', '.join(self.basket())}, re-weighted each quarter.",
            f"Trend part: on when the basket closes above its previous {p['dc_entry']}-day high, off below its previous {p['dc_exit']}-day low; held only "
            f"while the basket is calm ({p['calm_q']:g}th percentile), LQD ÷ IEF is above its {p['credit_ma']}-day average and SPY is above its "
            f"{p['spy_ma']}-day average. Size: S1+ half {p['vt1_pct']:g}% ÷ MAGX volatility, S2++ half {p['vt2_pct']:g}% ÷ MAGX volatility (each at most 100%).",
            f"Out of the trend: basket RSI2 < {p['deep_rsi']:g} → both halves {p['deep_pct']:g}% until RSI2 > {p['deep_exit_rsi']:g} or {p['deep_days']} closes; "
            f"RSI2 < {p['day_rsi']:g} → the S2++ half {p['day_pct']:g}% for a day.",
            f"Held: {p['share1_pct']:g}% S1+ + {p['share2_pct']:g}% S2++. Orders at the next open."],
            "flow": f"Mag 7 basket + SPY + LQD ÷ IEF daily → {p['trade']} · cash",
            "tv": "Mag 7 basket: no TradingView symbol (an equal-weight index the bot builds); SPY: SMA 200; LQD/IEF: SMA 100",
            "rule": f"½ S1+ + ½ S2++: basket DC{p['dc_entry']}/{p['dc_exit']} + calm + credit + SPY>SMA{p['spy_ma']} (vol-sized); RSI2 dips; else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.read_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        data, bk = self.inputs(now)
        btr = {s: BT.daily_tr(s) for s in self.basket()}
        bk_tr = quarterly_basket(btr, BT.daily_tr("SPY").index)
        tr = model_from_basket(BT.daily_tr(sym), bk_tr, float(p["model_cost_pct"]) / 100).reindex(fr.index)
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
                "bench": {sym: tr.dropna(subset=["c"]), "QQQ": BT.daily_tr("QQQ")}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": "QQQ",
                "data_from": str(days[0]),
                "data_note": f"{', '.join(self.basket())}, SPY, LQD and IEF daily bars with dividends added back (signals) · {sym} daily total-return "
                             f"prices; {sym} before {listed}: modelled as 2 × the equal-weight basket (re-weighted each quarter) daily minus "
                             f"{p['model_cost_pct']:g}% a year"}

    def check_table(self, now, rows=12):
        """An independent recompute of RSI2 (Wilder, plain loop) and the breakout levels from the basket closes."""
        p = self.params
        fr = self.frame(now)
        c = fr["b_c"].tolist()
        n = len(c)
        au = ad = None
        rs = [None] * n
        for i in range(1, n):
            d = c[i] - c[i - 1]
            u, dn = max(d, 0.0), max(-d, 0.0)
            au = u if au is None else au + (u - au) / 2
            ad = dn if ad is None else ad + (dn - ad) / 2
            rs[i] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
        cols = ["Basket", "RSI2 · bot / check", f"{p['dc_entry']}-day high · bot / check", "Held %"]
        out, worst = [], 0.0
        e = int(p["dc_entry"])
        for i in range(n - rows, n):
            r = fr.iloc[i]
            hi = max(c[i - e:i])
            diff = max(abs(r["rsi2"] - rs[i]) / 100, abs(r["dc_hi"] - hi) / max(hi, 1e-9))
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(fr.index[i]).timestamp()), "vals": [c[i], f"{r['rsi2']:.2f} / {rs[i]:.2f}", f"{r['dc_hi']:,.2f} / {hi:,.2f}",
                        float(r["w"] * 100)], "ok": bool(diff < 1e-6)})
        return cols, out, worst
