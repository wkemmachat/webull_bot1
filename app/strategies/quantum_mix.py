"""2x quantum ETF: dip + trend + RSI legs with a Bitcoin check (QPUX, Defiance 2x Daily Long Pure Quantum). Research "QPUX: two
best strategies per window" (26 Nov 2026), round 3 SAFE version: the round-2 challenger with the Bitcoin filter on every leg.

After each US close, from daily bars (signal at the close, trade at the next open):
  basket   equal-weight basket of the quantum stocks (IONQ, RGTI, QBTS, QUBT): each day the average of their moves from the
           previous close (open, high, low and close), a stock counting from its `basket` start date
  btc_ok   Bitcoin's PREVIOUS UTC daily close (known before the US close) above the average of the last btc_ma such closes
  dip      basket IBS < dip_ibs_max and the basket above its SMA(dip_ma)                → held one day (next open to the open after)
  trend    QPUX above its SMA(trend_ma) and QQQ above its SMA(market_ma)                → size min(1, target_vol ÷ QPUX's 20-day
           volatility), resized on a move of size_band points
  rsi      QPUX RSI(2) < rsi_buy while above its SMA(trend_ma); sold on a close above its SMA(rsi_exit_ma)
  Safe     every leg needs btc_ok (btc_all = on); off = only the trend leg needs it (the round-3 pick)
  weight   min(100%, dip_weight × dip + trend_weight × trend size + rsi_weight × rsi) of the money in QPUX, the rest cash.
Before QPUX listed (7 Aug 2025) the backtest models it as 2 × the basket's daily move minus model_cost_pct a year (fitted on
real QPUX in the research), joined to QPUX's first real close.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"mixed": "#B084F5", "trend": "#26A69A", "dip": "#F5C76B", "rsi": "#5B8DEF", "btc_off": "#8E3B46", "out": "#4A5263"}
STATE_TEXT = {"mixed": "two or more legs in", "trend": "trend leg in", "dip": "one-day dip buy", "rsi": "RSI bounce buy",
              "btc_off": "out · Bitcoin below its average", "out": "out · no leg in"}
TV.update({"QPUX": "AMEX:QPUX", "BTC-USD": "BITSTAMP:BTCUSD"})


def parse_basket(text: str) -> dict:
    """'IONQ:2021-10-01,RGTI:2022-03-02' → {symbol: start date} (no date = from its first bar)."""
    out = {}
    for part in str(text or "").split(","):
        part = part.strip()
        if not part:
            continue
        sym, _, d = part.partition(":")
        out[sym.strip().upper()] = pd.Timestamp(d.strip()).tz_localize("UTC") if d.strip() else None
    return out


def basket_bars(stocks: dict, starts: dict, idx) -> pd.DataFrame:
    """Equal-weight basket: each day the average of the members' open / high / low / close measured from their previous close."""
    rel = {k: [] for k in ("o", "h", "l", "c")}
    for s, df in stocks.items():
        df = df[~df.index.duplicated(keep="last")].reindex(idx)
        p = df["c"].astype(float).shift(1)
        ok = df["c"].notna() & p.notna()
        st = starts.get(s)
        if st is not None:
            ok &= (idx > st)                                  # the first day counted is the one after its start (prev close in)
        for k in rel:
            rel[k].append((df[k].astype(float) / p - 1).where(ok))
    m = {k: pd.concat(v, axis=1).mean(axis=1) for k, v in rel.items()}
    n = pd.concat(rel["c"], axis=1).notna().sum(axis=1)
    c = (1 + m["c"].fillna(0)).cumprod() * 100
    prev = c.shift(1).fillna(100.0)
    out = pd.DataFrame(index=idx)
    out["o"], out["h"], out["l"], out["c"] = prev * (1 + m["o"]), prev * (1 + m["h"]), prev * (1 + m["l"]), c
    out["rc"], out["n"] = m["c"], n
    return out


def model_qpux(real: pd.DataFrame, bk: pd.DataFrame, cost_y: float) -> pd.DataFrame:
    """QPUX before its first real bar: 2 × the basket's move (open, high, low, close from the previous close) minus cost, joined
    to QPUX's first real close."""
    if real is None or real.empty:
        return real
    J = real.index[0]
    b = bk[(bk.index <= J) & (bk["n"] > 0)]
    if len(b) < 2:
        return real
    prev = b["c"].shift(1)
    ro, rh, rl, rc = (b[k] / prev - 1 for k in ("o", "h", "l", "c"))
    n = len(b)
    o, h, l, c = (np.empty(n) for _ in range(4))
    c[0] = o[0] = h[0] = l[0] = 100.0
    for i in range(1, n):
        o[i] = c[i - 1] * (1 + 2 * ro.iloc[i])
        c[i] = c[i - 1] * (1 + 2 * rc.iloc[i] - cost_y / 252)
        h[i] = max(c[i - 1] * (1 + 2 * rh.iloc[i]), o[i], c[i])
        l[i] = min(c[i - 1] * (1 + 2 * rl.iloc[i]), o[i], c[i])
    f = float(real["c"].iloc[0]) / c[-1]
    early = pd.DataFrame({"o": o * f, "h": h * f, "l": l * f, "c": c * f, "v": 0.0}, index=b.index)
    return pd.concat([early[early.index < J], real])


def rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    ad = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)


def signals(q: pd.DataFrame, bk: pd.DataFrame, mkt: pd.DataFrame, btc: pd.DataFrame, p) -> pd.DataFrame:
    """One row per US session (QPUX's days): the legs decided at that day's close, the weight held from the next open."""
    idx = q.index
    c = q["c"].astype(float)
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[k] = q[k].astype(float).values
    bk = bk.reindex(idx)
    rng = bk["h"] - bk["l"]
    fr["ibs"] = np.where(rng > 0, (bk["c"] - bk["l"]) / rng.where(rng > 0, 1.0), 0.5)
    fr["bc"] = bk["c"].values
    fr["bma"] = bk["c"].rolling(int(p["dip_ma"])).mean().values
    fr["sma"] = c.rolling(int(p["trend_ma"])).mean().values
    fr["sma_x"] = c.rolling(int(p["rsi_exit_ma"])).mean().values
    fr["vol"] = (c.pct_change(fill_method=None).rolling(int(p["vol_days"])).std() * np.sqrt(252)).values
    fr["rsi"] = rsi(c, int(p["rsi_len"])).values
    mc = mkt["c"].astype(float)
    fr["mc"] = mc.reindex(idx).values
    fr["mma"] = mc.rolling(int(p["market_ma"])).mean().reindex(idx).values
    b = btc["c"].astype(float)
    b = b[~b.index.duplicated(keep="last")]
    prev = b.shift(1)                                         # the US close of date d sees Bitcoin's close of d − 1 (UTC)
    bma = prev.rolling(int(p["btc_ma"])).mean()
    fr["btc"], fr["btc_ma"] = prev.reindex(idx).values, bma.reindex(idx).values
    ok = ~(np.isnan(fr["bma"].values) | np.isnan(fr["sma"].values) | np.isnan(fr["mma"].values) | np.isnan(fr["btc_ma"].values)
           | np.isnan(fr["vol"].values))
    fr["ok"] = ok
    btc_ok = (fr["btc"] > fr["btc_ma"]).values
    fr["btc_ok"] = btc_ok
    dip = (fr["ibs"] < float(p["dip_ibs_max"])).values & (fr["bc"] > fr["bma"]).values
    on = (fr["c"] > fr["sma"]).values & (fr["mc"] > fr["mma"]).values & btc_ok
    kv, band = float(p["target_vol_pct"]) / 100, float(p["size_band_pct"]) / 100
    tw, held = np.zeros(len(fr)), 0.0
    rl, inr = np.zeros(len(fr)), False
    cv, sx, sm, rv, vv = (fr[k].values for k in ("c", "sma_x", "sma", "rsi", "vol"))
    for i in range(len(fr)):
        want = min(1.0, kv / vv[i]) if ok[i] and on[i] and vv[i] > 0 else 0.0
        if want == 0 or held == 0 or abs(want - held) >= band - 1e-12:
            held = want
        tw[i] = held
        if inr and cv[i] > sx[i]:
            inr = False
        elif not inr and rv[i] < float(p["rsi_buy"]) and cv[i] > sm[i]:
            inr = True
        rl[i] = 1.0 if inr else 0.0
    dipw = dip.astype(float)
    if p.get("btc_all"):
        dipw, rl = dipw * btc_ok, rl * btc_ok
    fr["dip"], fr["trend"], fr["rsi_in"] = dipw * ok, tw * ok, rl * ok
    fr["w"] = np.minimum(1.0, float(p["dip_weight"]) * fr["dip"] + float(p["trend_weight"]) * fr["trend"]
                         + float(p["rsi_weight"]) * fr["rsi_in"])
    legs = (fr["dip"] > 0).astype(int) + (fr["trend"] > 0).astype(int) + (fr["rsi_in"] > 0).astype(int)
    fr["state"] = np.where(~ok, "", np.where(legs >= 2, "mixed", np.where(fr["trend"] > 0, "trend", np.where(fr["dip"] > 0, "dip",
                           np.where(fr["rsi_in"] > 0, "rsi", np.where(btc_ok, "out", "btc_off"))))))
    return fr


@register
class QuantumMixStrategy(RegimeStrategy):
    type = "quantum_mix"
    label = "2x quantum: dip + trend + RSI legs with a Bitcoin check"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: three legs on a 2x quantum ETF — a one-day buy after a weak close of the quantum-stock basket, a trend leg "
                   "(above its 50-day average with the Nasdaq-100 above its 200-day average, sized by volatility) and an RSI bounce "
                   "leg — each only while Bitcoin is above its 100-day average. Cash otherwise.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "QPUX", "group": "Symbols"},
        {"key": "basket", "label": "Basket (symbol:counted from)", "kind": "text", "default": "QUBT:2021-10-01,IONQ:2021-10-01,RGTI:2022-03-02,QBTS:2022-08-08",
         "group": "Symbols", "help": "Equal-weight basket for the dip leg (and the backtest's model of QPUX before it listed)"},
        {"key": "market", "label": "Market check", "kind": "symbol", "default": "QQQ", "group": "Symbols"},
        {"key": "btc", "label": "Bitcoin", "kind": "text", "default": "BTC-USD", "group": "Symbols"},
        {"key": "dip_weight", "label": "Dip leg weight", "kind": "float", "default": 0.4, "min": 0, "max": 1, "group": "Dip leg"},
        {"key": "dip_ibs_max", "label": "Dip: basket IBS below", "kind": "float", "default": 0.20, "min": 0.01, "max": 0.5, "group": "Dip leg"},
        {"key": "dip_ma", "label": "Dip: basket above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Dip leg"},
        {"key": "trend_weight", "label": "Trend leg weight", "kind": "float", "default": 0.5, "min": 0, "max": 1, "group": "Trend leg"},
        {"key": "trend_ma", "label": "Trend: above its average (days)", "kind": "int", "default": 50, "min": 5, "max": 300, "group": "Trend leg"},
        {"key": "market_ma", "label": "Market above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend leg"},
        {"key": "target_vol_pct", "label": "Trend size: volatility target (%)", "kind": "float", "default": 60.0, "min": 5, "max": 300,
         "group": "Trend leg", "help": "Size = this ÷ QPUX's 20-day volatility a year, at most 100% (usually about 30%)"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Trend leg"},
        {"key": "size_band_pct", "label": "Resize on a move of (points)", "kind": "float", "default": 5.0, "min": 1, "max": 50, "group": "Trend leg"},
        {"key": "rsi_weight", "label": "RSI leg weight", "kind": "float", "default": 0.25, "min": 0, "max": 1, "group": "RSI leg"},
        {"key": "rsi_len", "label": "RSI length", "kind": "int", "default": 2, "min": 2, "max": 14, "group": "RSI leg"},
        {"key": "rsi_buy", "label": "RSI: buy below", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "RSI leg"},
        {"key": "rsi_exit_ma", "label": "RSI: sell on a close above the average of (days)", "kind": "int", "default": 5, "min": 2, "max": 50,
         "group": "RSI leg"},
        {"key": "btc_ma", "label": "Bitcoin above its average of (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Bitcoin check"},
        {"key": "btc_all", "label": "Bitcoin check on every leg (Safe)", "kind": "bool", "default": True, "group": "Bitcoin check",
         "help": "Off = only the trend leg needs it (the research's round-3 pick)"},
        {"key": "model_cost_pct", "label": "Backtest: model cost before listing (% a year)", "kind": "float", "default": 21.3, "min": 0,
         "max": 100, "group": "Backtest"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 5.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade back to the target when the holding drifts this far from it"},
    ]

    # ---------------------------------------------------------------- symbols
    def basket(self):
        return parse_basket(self.params["basket"])

    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["market"], *self.basket()]))

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols() + [self.params["btc"]]]

    def history_symbols(self):
        return self.read_symbols() + [self.params["btc"]]

    def bench_extra(self):
        return [self.params["market"]]

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
    def inputs(self, now, model=False):
        p = self.params
        d = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            d[s] = df[~df.index.duplicated(keep="last")]
        btc = md.load(p["btc"], "1d")
        if btc is None or btc.empty:
            raise md.DataError(f"No daily bars of Bitcoin ({p['btc']})")
        btc = btc[btc.index <= pd.Timestamp(now.date()).tz_localize("UTC")]
        q = d[p["trade"]]
        mkt = d[p["market"]]
        idx = mkt.index if model else q.index
        bk = basket_bars({s: d[s] for s in self.basket()}, self.basket(), mkt.index)
        if model:
            q = model_qpux(q, bk, float(p["model_cost_pct"]) / 100)
            idx = q.index
        return q.reindex(idx).dropna(subset=["c"]), bk, mkt, btc

    def frame(self, now, model=False) -> pd.DataFrame:
        p = self.params
        q, bk, mkt, btc = self.inputs(now, model)
        fr = signals(q, bk, mkt, btc, p)
        if len(fr) < 30 or not fr["ok"].any():
            raise md.DataError(f"Need {int(p['dip_ma']) + 2} days of the basket, {int(p['trend_ma']) + 2} of {p['trade']}, "
                               f"{int(p['market_ma']) + 2} of {p['market']} and {int(p['btc_ma']) + 2} of Bitcoin")
        return fr

    # ---------------------------------------------------------------- live
    def target_w(self, w) -> dict:
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
        r, a = fr.iloc[i], fr.iloc[i - 1]
        bits = []
        if bool(r["btc_ok"]) != bool(a["btc_ok"]):
            bits.append(f"Bitcoin {'above' if r['btc_ok'] else 'below'} its {p['btc_ma']}-day average ({r['btc']:,.0f} vs {r['btc_ma']:,.0f})")
        if r["dip"] != a["dip"]:
            bits.append(f"dip buy (basket IBS {r['ibs']:.2f})" if r["dip"] else "dip buy sold")
        if r["trend"] != a["trend"]:
            if r["trend"] > 0 and a["trend"] == 0:
                bits.append(f"trend in at {r['trend'] * 100:.0f}% ({p['trade']} above its {p['trend_ma']}-day average)")
            elif r["trend"] == 0:
                why = (f"{p['trade']} below its {p['trend_ma']}-day average" if r["c"] <= r["sma"] else
                       f"{p['market']} below its {p['market_ma']}-day average" if r["mc"] <= r["mma"] else "Bitcoin check off")
                bits.append(f"trend out ({why})")
            else:
                bits.append(f"trend resized to {r['trend'] * 100:.0f}% (volatility {r['vol'] * 100:.0f}%)")
        if r["rsi_in"] != a["rsi_in"]:
            bits.append(f"RSI bounce buy (RSI {r['rsi']:.1f})" if r["rsi_in"] else f"RSI bounce sold (close above its {p['rsi_exit_ma']}-day average)")
        return f"{'; '.join(bits) or 'weight changed'} → {r['w'] * 100:.0f}% {p['trade']} from the next open"

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        w = fr["w"].values
        hist = []
        for i in range(max(1, len(fr) - 600), len(fr)):
            if abs(w[i] - w[i - 1]) > 1e-9:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if w[i] > w[i - 1] else "SELL", "from": fr["state"].iloc[i - 1],
                             "to": fr["state"].iloc[i], "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        k = len(fr) - 1
        while k > 0 and abs(w[k - 1] - w[k]) < 1e-9:
            k -= 1
        state = last["state"]
        pct = round(float(last["w"]) * 100)
        bpct = (last["btc"] / last["btc_ma"] - 1) * 100
        checks = [
            {"k": f"Bitcoin vs its {p['btc_ma']}-day average", "v": f"{last['btc']:,.0f} vs {last['btc_ma']:,.0f} · {bpct:+.1f}%",
             "cls": "up" if last["btc_ok"] else "dn",
             "h": ("Every leg needs it above" if p.get("btc_all") else "The trend leg needs it above") + " (the previous day's UTC close)"},
            {"k": "Dip leg · basket", "v": f"IBS {last['ibs']:.2f} · basket {(last['bc'] / last['bma'] - 1) * 100:+.1f}% vs its {p['dip_ma']}-day average",
             "cls": "warn" if last["dip"] else ("up" if last["bc"] > last["bma"] else "dn"),
             "h": f"Buy for one day when IBS < {p['dip_ibs_max']:g} while the basket is above its average · weight {p['dip_weight']:g}"},
            {"k": "Trend leg", "v": f"{p['trade']} {last['c']:,.2f} vs SMA{p['trend_ma']} {last['sma']:,.2f} · {p['market']} "
                                     f"{(last['mc'] / last['mma'] - 1) * 100:+.1f}% vs SMA{p['market_ma']} · size {last['trend'] * 100:.0f}%",
             "cls": "up" if last["trend"] > 0 else "dn",
             "h": f"Size = min(100%, {p['target_vol_pct']:g}% ÷ volatility {last['vol'] * 100:.0f}%) · weight {p['trend_weight']:g}"},
            {"k": "RSI leg", "v": f"RSI({p['rsi_len']}) {last['rsi']:.1f} · {'in' if last['rsi_in'] else 'out'}",
             "cls": "warn" if last["rsi_in"] else "",
             "h": f"In below {p['rsi_buy']:g} while above SMA{p['trend_ma']}; out on a close above SMA{p['rsi_exit_ma']} ({last['sma_x']:,.2f}) · "
                  f"weight {p['rsi_weight']:g}"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open", "h": "min(100%, the legs' weights added up); the rest cash"}]
        tiles = [{"k": "dip", "title": "Dip leg (1 day)", "text": f"Basket IBS < {p['dip_ibs_max']:g}, basket above SMA{p['dip_ma']}",
                  "hold": f"{p['dip_weight'] * 100:g}% {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "trend", "title": "Trend leg", "text": f"{p['trade']} above SMA{p['trend_ma']}, {p['market']} above SMA{p['market_ma']}",
                  "hold": f"{p['trend_weight'] * 100:g}% × {p['target_vol_pct']:g}% ÷ volatility", "color": STATE_COLOR["trend"]},
                 {"k": "rsi", "title": "RSI leg", "text": f"RSI({p['rsi_len']}) < {p['rsi_buy']:g} above SMA{p['trend_ma']}; out above SMA{p['rsi_exit_ma']}",
                  "hold": f"{p['rsi_weight'] * 100:g}% {p['trade']}", "color": STATE_COLOR["rsi"]},
                 {"k": "mixed", "title": "Two or more legs", "text": "The legs' weights add up (at most 100%)", "hold": f"up to 100% {p['trade']}",
                  "color": STATE_COLOR["mixed"]},
                 {"k": "btc_off", "title": "Out · Bitcoin check", "text": f"Bitcoin below its {p['btc_ma']}-day average", "hold": "cash",
                  "color": STATE_COLOR["btc_off"]},
                 {"k": "out", "title": "Out", "text": "No leg in", "hold": "cash", "color": STATE_COLOR["out"]}]

        def num(x):
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return None if x != x else x
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["c"]), "ibs": num(r["ibs"]), "trend": num(r["trend"] * 100),
                             "rsi": num(r["rsi"]), "btc": "on" if r["btc_ok"] else "off", "held": num(r["w"] * 100), "state": r["state"],
                             "action": ("no trade" if i == 0 or abs(w[i] - w[i - 1]) < 1e-9 else
                                        f"{'buy' if w[i] > w[i - 1] else 'sell'} to {w[i] * 100:.0f}% next open"),
                             "changed": bool(i > 0 and abs(w[i] - w[i - 1]) > 1e-9), "from": fr["state"].iloc[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "ibs", "label": "Basket IBS", "fmt": "n2"},
                    {"k": "trend", "label": "Trend %", "fmt": "n0"}, {"k": "rsi", "label": f"RSI({p['rsi_len']})", "fmt": "n1"},
                    {"k": "btc", "label": "Bitcoin"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        label = (f"IN · {pct}% {p['trade']} · {STATE_TEXT[state]}" if pct > 0 else f"OUT · cash · {STATE_TEXT[state].replace('out · ', '')}")
        return {"ok": True, "state": state, "label": label, "target": self.target_w(last["w"]),
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
            if w[i] > w[i - 1] + 1e-9:
                markers.append({"time": t[i], "position": "belowBar", "color": "#2962FF", "shape": "arrowUp", "text": f"→ {w[i] * 100:.0f}%"})
            elif w[i] < w[i - 1] - 1e-9:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#E040FB", "shape": "arrowDown", "text": f"→ {w[i] * 100:.0f}%"})
        panes = [{"id": "ibs", "title": "Basket IBS (dip leg)", "height": 70, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                  "hlines": [{"value": float(p["dip_ibs_max"]), "label": f"dip < {p['dip_ibs_max']:g}"}]},
                 {"id": "rsi", "title": f"RSI({p['rsi_len']}) (RSI leg)", "height": 70, "lines": [{"name": "RSI", "color": "#5B8DEF", "width": 1, "data": ln("rsi", 1)}],
                  "hlines": [{"value": float(p["rsi_buy"]), "label": f"buy < {p['rsi_buy']:g}"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                  "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)},
                            {"name": "Trend size", "color": "#26A69A", "width": 1, "data": ln("trend", 1, 100)}], "hlines": []}]
        sig = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — the trend and RSI legs are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [{"name": f"SMA {p['trend_ma']}", "color": "#FF9800", "width": 2, "data": ln("sma")},
                         {"name": f"SMA {p['rsi_exit_ma']}", "color": "#2962FF", "width": 1, "data": ln("sma_x")}],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(fr["state"].values)],
               "panes": panes, "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        charts = [sig]
        mk = md.daily_closed(p["market"], now)
        mk = mk[~mk.index.duplicated(keep="last")]
        mk = mk[mk.index.isin(fr.index)]
        if len(mk):
            mt = [int(pd.Timestamp(x).timestamp()) for x in mk.index]
            ma = fr["mma"].reindex(mk.index).values
            charts.append({"id": "market", "title": f"{p['market']} · 1D", "subtitle": f"Market check — the trend leg needs it above SMA{p['market_ma']}",
                           "candles": [{"time": mt[i], "open": round(float(mk["o"].iloc[i]), 4), "high": round(float(mk["h"].iloc[i]), 4),
                                        "low": round(float(mk["l"].iloc[i]), 4), "close": round(float(mk["c"].iloc[i]), 4)} for i in range(len(mk))],
                           "lines": [{"name": f"SMA {p['market_ma']}", "color": "#FF9800", "width": 2,
                                      "data": [{"time": mt[i], "value": round(float(ma[i]), 4)} if ma[i] == ma[i] else {"time": mt[i]} for i in range(len(mt))]}],
                           "markers": [], "panes": [], "tv": tv_url(p["market"]), "tv_symbol": TV.get(p["market"], p["market"])})
        b = md.load(p["btc"], "1d")
        if b is not None and not b.empty:
            b = b[~b.index.duplicated(keep="last")]
            bma = b["c"].astype(float).shift(1).rolling(int(p["btc_ma"])).mean()
            b = b[(b.index >= fr.index[0]) & (b.index <= pd.Timestamp(now.date()).tz_localize("UTC"))]
            bt = [int(pd.Timestamp(x).timestamp()) for x in b.index]
            bm = bma.reindex(b.index).values
            charts.append({"id": "btc", "title": "Bitcoin (BTC-USD) · daily, UTC", "subtitle": f"Bitcoin check — each US close uses the previous "
                           f"day's Bitcoin close against its {p['btc_ma']}-day average",
                           "candles": [{"time": bt[i], "open": round(float(b["o"].iloc[i]), 2), "high": round(float(b["h"].iloc[i]), 2),
                                        "low": round(float(b["l"].iloc[i]), 2), "close": round(float(b["c"].iloc[i]), 2)} for i in range(len(b))],
                           "lines": [{"name": f"SMA {p['btc_ma']} (of the previous closes)", "color": "#FF9800", "width": 2,
                                      "data": [{"time": bt[i], "value": round(float(bm[i]), 2)} if bm[i] == bm[i] else {"time": bt[i]} for i in range(len(bt))]}],
                           "markers": [], "panes": [], "tv": tv_url(p["btc"]), "tv_symbol": TV.get(p["btc"], p["btc"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        allb = bool(p.get("btc_all"))
        return {"rules": [
            f"After each US close: three legs on {p['trade']}; " + ("each needs" if allb else "the trend leg needs") +
            f" Bitcoin's previous daily close above its {p['btc_ma']}-day average.",
            f"Dip leg ({p['dip_weight']:g}): the equal-weight basket {', '.join(self.basket())} closes with IBS < {p['dip_ibs_max']:g} while "
            f"above its {p['dip_ma']}-day average → held one day.",
            f"Trend leg ({p['trend_weight']:g}): {p['trade']} above its {p['trend_ma']}-day average and {p['market']} above its {p['market_ma']}-day "
            f"average → size min(100%, {p['target_vol_pct']:g}% ÷ its {p['vol_days']}-day volatility).",
            f"RSI leg ({p['rsi_weight']:g}): RSI({p['rsi_len']}) < {p['rsi_buy']:g} while above its {p['trend_ma']}-day average; sold on a close "
            f"above its {p['rsi_exit_ma']}-day average.",
            f"Money in {p['trade']} = min(100%, the legs added up); the rest cash. Orders at the next open."],
            "flow": f"basket IBS + {p['trade']} SMA{p['trend_ma']} + {p['market']} SMA{p['market_ma']} + Bitcoin SMA{p['btc_ma']} → {p['trade']} · cash",
            "tv": f'{p["trade"]} daily: "Moving Average" {p["trend_ma"]} and {p["rsi_exit_ma"]}, "RSI" length {p["rsi_len"]}; '
                  f'{p["market"]}: "Moving Average" {p["market_ma"]}; BTCUSD daily: "Moving Average" {p["btc_ma"]}',
            "rule": f"{p['trade']}: {p['dip_weight']:g} × basket IBS dip + {p['trend_weight']:g} × trend (vol-sized) + {p['rsi_weight']:g} × RSI bounce, "
                    + ("all" if allb else "trend") + f" only while Bitcoin > SMA{p['btc_ma']}; else cash"}

    # ---------------------------------------------------------------- backtest (backtest.py calls this)
    def backtest_run(self, now, cost, delay=0):
        """Decided at the close, traded at the next open (delay: that many sessions later); traded back to the target when the
        holding drifts more than the rebalance band. QPUX before its listing is the model (model_qpux) on total-return bars."""
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        mk = BT.daily_tr(p["market"])
        stocks = {s: BT.daily_tr(s) for s in self.basket()}
        bk = basket_bars(stocks, self.basket(), mk.index)
        tr = model_qpux(BT.daily_tr(sym), bk, float(p["model_cost_pct"]) / 100)
        if tr is None or tr.empty:
            raise BT.BacktestError(f"No price history for {sym}")
        tr = tr.reindex(fr.index)
        ok = fr["ok"].values & tr["o"].notna().values & tr["c"].notna().values
        if not ok.any():
            raise BT.BacktestError("Not enough overlapping history yet")
        first = int(np.argmax(ok))
        idx = list(range(first, len(fr)))
        o_tr, c_tr = tr["o"].astype(float).values, tr["c"].astype(float).values
        W = fr["w"].values
        B = BT.Book(cost)
        buf, band = 1 - self.buffer(), self.rebalance_band()
        days, eq, expo, states = [], [], [], []
        cur, drift = 0.0, False
        for i in idx:
            j = i - 1 - delay
            d = fr.index[i].date()
            t_open = datetime.combine(d, dtime(9, 30), NY)
            if j >= first:
                want = float(W[j])
                if abs(want - cur) > 1e-9:
                    kind = "START" if not B.trades else ("BUY" if want > cur else "SELL")
                    try:
                        why = self.why(fr, j)
                    except Exception:
                        why = f"weight {cur * 100:.0f}% → {want * 100:.0f}%"
                    B.rebalance({sym: want * buf} if want > 0 else {}, {sym: o_tr[i]}, t_open, why, kind)
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
                "bench": {sym: tr.dropna(subset=["c"]), p["market"]: mk}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": p["market"],
                "data_from": str(days[0]),
                "data_note": f"{sym}, {p['market']}, the basket ({', '.join(self.basket())}) and Bitcoin daily bars · {sym} daily total-return "
                             f"prices; {sym} before {listed}: modelled as 2 × the basket's daily move minus {p['model_cost_pct']:g}% a year"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        """Recompute the last `rows` days the long way: the basket's IBS, QPUX's 50-day average and the Bitcoin check."""
        p = self.params
        fr = self.frame(now)
        q, bk, mkt, btc = self.inputs(now)
        qc = q["c"].astype(float).tolist()
        qpos = {d: i for i, d in enumerate(q.index)}
        b = btc["c"].astype(float)
        b = b[~b.index.duplicated(keep="last")]
        bl = b.tolist()
        bpos = {d: i for i, d in enumerate(b.index)}
        n, nb = int(p["trend_ma"]), int(p["btc_ma"])
        cols = ["Close", f"SMA{n} · bot / check", "Basket IBS · bot / check", "Bitcoin vs average · bot / check", "Held %"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            i = qpos[d]
            sma = sum(qc[i - n + 1:i + 1]) / n if i >= n - 1 else float("nan")
            h, l, c = bk.loc[d, "h"], bk.loc[d, "l"], bk.loc[d, "c"]
            ibs = (c - l) / (h - l) if h > l else 0.5
            j = bpos.get(d)
            ok_b = None
            if j is not None and j >= nb + 1:
                prev = bl[j - 1]
                avg = sum(bl[j - nb:j]) / nb
                ok_b = prev > avg
            diff = max(abs(r["sma"] - sma) / max(sma, 1e-9) if sma == sma else 0.0, abs(r["ibs"] - ibs),
                       0.0 if ok_b is None or ok_b == bool(r["btc_ok"]) else 1.0)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()),
                        "vals": [float(r["c"]), f"{r['sma']:,.3f} / {sma:,.3f}", f"{r['ibs']:.3f} / {ibs:.3f}",
                                 f"{'on' if r['btc_ok'] else 'off'} / {'—' if ok_b is None else ('on' if ok_b else 'off')}", float(r["w"] * 100)],
                        "ok": bool(diff < 1e-6)})
        return cols, out, worst
