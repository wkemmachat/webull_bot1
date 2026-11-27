"""Blend v (BIB, ProShares Ultra Nasdaq Biotechnology 2x). Research "BIB (2x Nasdaq Biotech): 2 best strategies" rounds 1–4
(26 Nov 2026): half rule S3v (rates), half rule S2+v (trend), each 0% or 100% of BIB.

After each US close (signal at the close, trade at the next open), from daily bars with dividends added back:
  credit   LQD ÷ IEF above its SMA(credit_ma)
  S3v hold credit AND the 10-year yield (^TNX) below its SMA(tnx_ma) AND TLT above its SMA(tlt_ma)
  S2+v hold XBI above its close mom_days ago AND credit AND SPY above its SMA(spy_ma) AND IWM above its SMA(iwm_ma)
  dips (a leg that is not holding):
    deep     BIB IBS < deep_ibs while XBI is above its SMA(xbi_ma) → hold until IBB closes above its previous high, deep_days
             closes, or XBI closes at or below its average (both legs)
    IBB day  IBB IBS < ibb_ibs and VIX closes above vix_min → one day (both legs)
    BIB day  BIB IBS < bib_ibs and VIX above vix_min → one day (S2+v only)
  held     share3 × S3v + share2 × S2+v
Before BIB listed (Apr 2010) the backtest models it as 2 × IBB minus model_cost_pct a year.
"""
from __future__ import annotations

from datetime import datetime, time as dtime

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import register
from .hk_crash import HkCrashStrategy
from .momentum_calm import model_2x
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"both": "#26A69A", "rates": "#5B8DEF", "trend": "#20C997", "deep": "#E8875A", "day": "#F5C76B", "out": "#4A5263"}
STATE_TEXT = {"both": "both legs hold", "rates": "S3v (rates) holds", "trend": "S2+v (trend) holds", "deep": "deep dip",
              "day": "one-day dip", "out": "out · cash"}
TV.update({"BIB": "AMEX:BIB", "IBB": "NASDAQ:IBB", "XBI": "AMEX:XBI", "^VIX": "CBOE:VIX", "^TNX": "CBOE:TNX"})


def ibs(df: pd.DataFrame) -> np.ndarray:
    h, l, c = (df[k].astype(float).values for k in ("h", "l", "c"))
    rng = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)


def deep_dip(start, gate, exit_up, max_days):
    """1 while a deep-dip trade is open: opens at a close where `start`; ends at a later close where `exit_up` (IBB above its
    previous high), where `gate` fails (checked every day of the trade), or max_days closes after it opened."""
    n = len(start)
    on = np.zeros(n, dtype=bool)
    open_, days = False, 0
    for i in range(n):
        if open_:
            days += 1
            if exit_up[i] or not gate[i] or days >= max_days:
                open_ = False
        if not open_ and start[i]:
            open_, days = True, 0
        on[i] = open_
    return on


def signals(tr: pd.DataFrame, data: dict, p) -> pd.DataFrame:
    idx = tr.index
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[f"t_{k}"] = tr[k].astype(float).values

    def col(sym, k="c"):
        return data[sym][k].astype(float)

    def sma(sym, n):
        return col(sym).rolling(int(n)).mean().reindex(idx).values

    fr["bib_ibs"] = ibs(data[p["trade"]].reindex(idx))
    ib = data["IBB"].reindex(idx)
    fr["ibb_ibs"] = ibs(ib)
    fr["ibb_c"], fr["ibb_ph"] = ib["c"].astype(float).values, ib["h"].astype(float).shift(1).values
    la = col("LQD") / col("IEF")
    fr["credit_pct"] = ((la / la.rolling(int(p["credit_ma"])).mean() - 1) * 100).reindex(idx).values
    for sym, key, n in (("^TNX", "tnx", p["tnx_ma"]), ("TLT", "tlt", p["tlt_ma"]), ("SPY", "spy", p["spy_ma"]),
                        ("IWM", "iwm", p["iwm_ma"]), ("XBI", "xbi", p["xbi_ma"])):
        fr[key], fr[key + "_ma"] = col(sym).reindex(idx).values, sma(sym, n)
    x = col("XBI")
    fr["xbi_mom"] = ((x / x.shift(int(p["mom_days"])) - 1) * 100).reindex(idx).values
    fr["vix"] = col("^VIX").reindex(idx).values
    need = ["credit_pct", "tnx_ma", "tlt_ma", "spy_ma", "iwm_ma", "xbi_ma", "xbi_mom", "vix", "ibb_ph"]
    ok = ~fr[need].isna().any(axis=1).values
    v = {k: fr[k].values for k in fr.columns}
    credit = ok & (v["credit_pct"] > 0)
    hold3 = credit & (v["tnx"] < v["tnx_ma"]) & (v["tlt"] > v["tlt_ma"])
    hold2 = credit & (v["xbi_mom"] > 0) & (v["spy"] > v["spy_ma"]) & (v["iwm"] > v["iwm_ma"])
    xbi_up = ok & (v["xbi"] > v["xbi_ma"])
    vix_hi = ok & (v["vix"] > float(p["vix_min"]))
    deep = deep_dip(ok & xbi_up & (v["bib_ibs"] < float(p["deep_ibs"])), xbi_up, v["ibb_c"] > v["ibb_ph"], int(p["deep_days"]))
    ibb_day = vix_hi & (v["ibb_ibs"] < float(p["ibb_ibs"]))
    bib_day = vix_hi & (v["bib_ibs"] < float(p["bib_ibs"]))
    w3 = np.where(hold3 | deep | ibb_day, 1.0, 0.0)
    w2 = np.where(hold2 | deep | ibb_day | bib_day, 1.0, 0.0)
    s3, s2 = float(p["share3_pct"]) / 100, float(p["share2_pct"]) / 100
    fr["w3"], fr["w2"] = np.where(ok, w3, 0.0), np.where(ok, w2, 0.0)
    fr["w"] = np.minimum(1.0, s3 * fr["w3"].values + s2 * fr["w2"].values)
    fr["credit"], fr["hold3"], fr["hold2"], fr["xbi_up"], fr["vix_hi"] = credit, hold3, hold2, xbi_up, vix_hi
    fr["deep"], fr["ibb_day"], fr["bib_day"], fr["ok"] = deep, ibb_day, bib_day, ok
    fr["state"] = np.where(~ok, "", np.where(hold3 & hold2, "both", np.where(hold3, "rates", np.where(hold2, "trend",
                           np.where(deep, "deep", np.where(ibb_day | bib_day, "day", "out"))))))
    return fr


@register
class RatesTrendBlendStrategy(RegimeStrategy):
    type = "rates_trend_blend"
    label = "Half rates rule, half trend rule, with IBS dips (2x biotech)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: half held while credit is healthy and rates are easing (10-year yield under its average, TLT above), half while "
                   "biotech and the market trend up; otherwise IBS dip buys (one-day ones only when VIX is above 20); cash else.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "BIB", "group": "Symbols"},
        {"key": "credit_ma", "label": "Credit: LQD ÷ IEF above its average (days)", "kind": "int", "default": 100, "min": 10, "max": 400, "group": "Both legs"},
        {"key": "tnx_ma", "label": "S3v: 10-year yield below its average (days)", "kind": "int", "default": 50, "min": 5, "max": 400, "group": "S3v (rates)"},
        {"key": "tlt_ma", "label": "S3v: TLT above its average (days)", "kind": "int", "default": 100, "min": 5, "max": 400, "group": "S3v (rates)"},
        {"key": "mom_days", "label": "S2+v: XBI above its close this many days ago", "kind": "int", "default": 252, "min": 20, "max": 504, "group": "S2+v (trend)"},
        {"key": "spy_ma", "label": "S2+v: SPY above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "S2+v (trend)"},
        {"key": "iwm_ma", "label": "S2+v: IWM above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "S2+v (trend)"},
        {"key": "deep_ibs", "label": "Deep dip: BIB IBS below", "kind": "float", "default": 0.05, "min": 0, "max": 0.5, "group": "Dips"},
        {"key": "xbi_ma", "label": "Deep dip only while XBI above its average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Dips"},
        {"key": "deep_days", "label": "Deep dip ends after (closes)", "kind": "int", "default": 5, "min": 1, "max": 30, "group": "Dips"},
        {"key": "vix_min", "label": "One-day dips only while VIX above", "kind": "float", "default": 20.0, "min": 0, "max": 80, "group": "Dips"},
        {"key": "ibb_ibs", "label": "One-day dip (both legs): IBB IBS below", "kind": "float", "default": 0.10, "min": 0, "max": 0.5, "group": "Dips"},
        {"key": "bib_ibs", "label": "One-day dip (S2+v leg): BIB IBS below", "kind": "float", "default": 0.20, "min": 0, "max": 0.5, "group": "Dips"},
        {"key": "share3_pct", "label": "Share in S3v (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Mix"},
        {"key": "share2_pct", "label": "Share in S2+v (%)", "kind": "float", "default": 50.0, "min": 0, "max": 100, "group": "Mix"},
        {"key": "model_cost_pct", "label": "Backtest: model cost before listing (% a year)", "kind": "float", "default": 3.0, "min": 0, "max": 30, "group": "Backtest",
         "help": "BIB before Apr 2010 = 2 × IBB minus this"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 10.0, "min": 1, "max": 50, "group": "Money"},
    ]
    SIGNALS = ["IBB", "XBI", "LQD", "IEF", "^TNX", "TLT", "SPY", "IWM", "^VIX"]
    RAW = ("^TNX", "^VIX")

    def read_symbols(self):
        return list(dict.fromkeys([self.params["trade"]] + self.SIGNALS))

    history_symbols = read_symbols

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols()]

    def bench_extra(self):
        return ["IBB"]

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
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            df = df[~df.index.duplicated(keep="last")]
            data[s] = df if s in self.RAW or s == p["trade"] else HkCrashStrategy.dividend_adjusted(s, df)
        tr = data[p["trade"]]
        if model:
            tr = model_2x(tr, data, {"IBB": 1.0}, data["IBB"].index, float(p["model_cost_pct"]) / 100)
            data[p["trade"]] = tr
        fr = signals(tr, data, p)
        if not fr["ok"].any():
            raise md.DataError("Need about 260 daily bars of the signals")
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
        bits = []
        if r["hold3"] and not a["hold3"]:
            bits.append("S3v holds (credit ok, 10-year yield under its average, TLT above)")
        elif a["hold3"] and not r["hold3"]:
            bits.append("S3v stops holding")
        if r["hold2"] and not a["hold2"]:
            bits.append("S2+v holds (XBI up over a year, credit ok, SPY and IWM above SMA200)")
        elif a["hold2"] and not r["hold2"]:
            bits.append("S2+v stops holding")
        if r["deep"] and not a["deep"]:
            bits.append(f"deep dip: BIB IBS {r['bib_ibs']:.2f} < {p['deep_ibs']:g}")
        elif a["deep"] and not r["deep"]:
            bits.append("deep dip ended")
        if r["ibb_day"]:
            bits.append(f"one-day dip: IBB IBS {r['ibb_ibs']:.2f}, VIX {r['vix']:.1f}")
        elif r["bib_day"]:
            bits.append(f"one-day dip (S2+v): BIB IBS {r['bib_ibs']:.2f}, VIX {r['vix']:.1f}")
        elif (a["ibb_day"] or a["bib_day"]) and not r["deep"]:
            bits.append("one-day dip sold")
        t = ", ".join(bits) or "no change"
        return t[0].upper() + t[1:] + f" · {p['trade']} {r['w'] * 100:.0f}% from the next open"

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

        def vs(a, b):
            return f"{(a / b - 1) * 100:+.1f}%"
        checks = [
            {"k": f"Credit · LQD ÷ IEF vs SMA{p['credit_ma']}", "v": f"{last['credit_pct']:+.2f}%", "cls": "up" if last["credit"] else "dn",
             "h": "Both legs need it to hold"},
            {"k": f"S3v · 10-year yield vs SMA{p['tnx_ma']} · TLT vs SMA{p['tlt_ma']}", "v": f"{last['tnx']:.2f}% ({vs(last['tnx'], last['tnx_ma'])}) · "
             f"TLT {vs(last['tlt'], last['tlt_ma'])} → {'holds' if last['hold3'] else 'no'}", "cls": "up" if last["hold3"] else "dn",
             "h": "Holds with credit ok, the yield below its average and TLT above its average"},
            {"k": f"S2+v · XBI {p['mom_days']}-day change · SPY, IWM vs SMA200", "v": f"XBI {last['xbi_mom']:+.1f}% · SPY {vs(last['spy'], last['spy_ma'])} · "
             f"IWM {vs(last['iwm'], last['iwm_ma'])} → {'holds' if last['hold2'] else 'no'}", "cls": "up" if last["hold2"] else "dn"},
            {"k": f"Deep dip · BIB IBS · XBI vs SMA{p['xbi_ma']}", "v": f"{last['bib_ibs']:.2f} · XBI {vs(last['xbi'], last['xbi_ma'])}"
             + (" · deep dip open" if last["deep"] else ""), "cls": "warn" if last["bib_ibs"] < float(p["deep_ibs"]) else "",
             "h": f"Starts below {p['deep_ibs']:g} while XBI is above its average; ends when IBB closes above its previous high, after "
                  f"{p['deep_days']} closes, or if XBI falls below its average"},
            {"k": "One-day dips · IBB IBS · BIB IBS · VIX", "v": f"{last['ibb_ibs']:.2f} · {last['bib_ibs']:.2f} · VIX {last['vix']:.1f}",
             "cls": "warn" if (last["ibb_day"] or last["bib_day"]) else "",
             "h": f"Only while VIX is above {p['vix_min']:g}: IBB IBS < {p['ibb_ibs']:g} → both legs; BIB IBS < {p['bib_ibs']:g} → the S2+v leg"},
            {"k": "Money in " + p["trade"], "v": f"{pct}% from the next open (S3v {last['w3'] * 100:.0f}% · S2+v {last['w2'] * 100:.0f}%)"}]
        tiles = [{"k": "both", "title": "In · both legs", "text": "Rates and trend rules hold", "hold": f"100% {p['trade']}", "color": STATE_COLOR["both"]},
                 {"k": "rates", "title": "In · S3v", "text": "Credit ok, yield falling, TLT up", "hold": f"{p['share3_pct']:g}% {p['trade']}", "color": STATE_COLOR["rates"]},
                 {"k": "trend", "title": "In · S2+v", "text": "XBI up a year, SPY and IWM above SMA200", "hold": f"{p['share2_pct']:g}% {p['trade']}",
                  "color": STATE_COLOR["trend"]},
                 {"k": "deep", "title": "In · deep dip", "text": f"BIB IBS < {p['deep_ibs']:g}, XBI above SMA{p['xbi_ma']}", "hold": f"100% {p['trade']}",
                  "color": STATE_COLOR["deep"]},
                 {"k": "day", "title": "In · one-day dip", "text": f"VIX > {p['vix_min']:g} and a weak close", "hold": f"50–100% {p['trade']}", "color": STATE_COLOR["day"]},
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
            log_rows.append({"date": str(fr.index[i].date()), "close": num(r["t_c"]), "bib_ibs": num(r["bib_ibs"]), "ibb_ibs": num(r["ibb_ibs"]),
                             "vix": num(r["vix"]), "credit": "ok" if r["credit"] else "weak", "s3": "holds" if r["hold3"] else "no",
                             "s2": "holds" if r["hold2"] else "no", "held": num(r["w"] * 100), "state": r["state"],
                             "action": "no trade" if abs(a0 - a1) < 1e-9 else f"{'buy' if a1 > a0 else 'sell'} to {a1 * 100:.0f}% next open",
                             "changed": bool(i > 0 and abs(a1 - a0) > 1e-9), "from": sts[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "bib_ibs", "label": "BIB IBS", "fmt": "n2"},
                    {"k": "ibb_ibs", "label": "IBB IBS", "fmt": "n2"}, {"k": "vix", "label": "VIX", "fmt": "n1"}, {"k": "credit", "label": "Credit"},
                    {"k": "s3", "label": "S3v"}, {"k": "s2", "label": "S2+v"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
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
        fr = fr.assign(tnx_pct=(fr["tnx"] / fr["tnx_ma"] - 1) * 100, tlt_pct=(fr["tlt"] / fr["tlt_ma"] - 1) * 100)
        ib = md.daily_closed("IBB", now)
        ib = HkCrashStrategy.dividend_adjusted("IBB", ib[~ib.index.duplicated(keep="last")]).reindex(fr.index)
        sig = {"id": "signal", "title": "IBB · 1D", "subtitle": "Signal — biotech 1x (dividends added back); BIB's own IBS is in its chart below",
               "candles": [{"time": t[i], "open": round(float(ib["o"].iloc[i]), 4), "high": round(float(ib["h"].iloc[i]), 4),
                            "low": round(float(ib["l"].iloc[i]), 4), "close": round(float(ib["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [],
               "ribbon": [{"time": t[i], "color": STATE_COLOR.get(x, "#2A2E39"), "state": x} for i, x in enumerate(fr["state"].values)],
               "panes": [{"id": "rates", "title": f"S3v · 10-year yield % vs SMA{p['tnx_ma']} (below 0 helps) · TLT % vs SMA{p['tlt_ma']}", "height": 70,
                          "lines": [{"name": "10-year yield", "color": "#EF5350", "width": 1, "data": ln("tnx_pct", 2)},
                                    {"name": "TLT", "color": "#26A69A", "width": 1, "data": ln("tlt_pct", 2)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "credit", "title": f"Credit · LQD ÷ IEF, % vs its {p['credit_ma']}-day average", "height": 50,
                          "lines": [{"name": "LQD ÷ IEF", "color": "#5B8DEF", "width": 1, "data": ln("credit_pct", 3)}], "hlines": [{"value": 0, "label": "0"}]},
                         {"id": "vix", "title": "VIX (one-day dips only above the line)", "height": 60,
                          "lines": [{"name": "VIX", "color": "#F5C76B", "width": 1, "data": ln("vix", 2)}],
                          "hlines": [{"value": float(p["vix_min"]), "label": f"{p['vix_min']:g}"}]},
                         {"id": "ibs", "title": "IBS · IBB", "height": 50, "lines": [{"name": "IBB IBS", "color": "#C77DFF", "width": 1, "data": ln("ibb_ibs", 3)}],
                          "hlines": [{"value": float(p["ibb_ibs"]), "label": f"{p['ibb_ibs']:g}"}]},
                         {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 60, "step": True,
                          "lines": [{"name": "Held", "color": self.color, "width": 2, "area": True, "data": ln("w", 1, 100)}], "hlines": []}],
               "markers": markers, "tv": tv_url("IBB"), "tv_symbol": TV.get("IBB", "IBB")}
        trd = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — its IBS starts the deep dip and the S2+v one-day dip",
               "candles": [{"time": t[i], "open": round(float(fr["t_o"].iloc[i]), 4), "high": round(float(fr["t_h"].iloc[i]), 4),
                            "low": round(float(fr["t_l"].iloc[i]), 4), "close": round(float(fr["t_c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "markers": markers,
               "panes": [{"id": "bibs", "title": f"IBS · {p['trade']}", "height": 60, "lines": [{"name": "IBS", "color": "#F5C76B", "width": 1, "data": ln("bib_ibs", 3)}],
                          "hlines": [{"value": float(p["bib_ibs"]), "label": f"{p['bib_ibs']:g}"}, {"value": float(p["deep_ibs"]), "label": f"{p['deep_ibs']:g}"}]}],
               "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        return {"charts": [sig, trd], "states": STATE_COLOR}

    def describe(self):
        p = self.params
        return {"rules": [
            f"S3v ({p['share3_pct']:g}%): hold {p['trade']} while LQD ÷ IEF is above its {p['credit_ma']}-day average, the 10-year yield is below its "
            f"{p['tnx_ma']}-day average and TLT is above its {p['tlt_ma']}-day average.",
            f"S2+v ({p['share2_pct']:g}%): hold while XBI is above its close {p['mom_days']} days ago, credit is healthy and SPY and IWM are above their "
            f"{p['spy_ma']}-day averages.",
            f"A leg that is not holding buys dips: BIB IBS < {p['deep_ibs']:g} while XBI is above its {p['xbi_ma']}-day average (held until IBB closes "
            f"above its previous high, {p['deep_days']} closes at most); IBB IBS < {p['ibb_ibs']:g} with VIX above {p['vix_min']:g} for one day; the S2+v leg "
            f"also BIB IBS < {p['bib_ibs']:g} with VIX above {p['vix_min']:g} for one day.",
            "Otherwise cash. Orders at the next open."],
            "flow": f"Credit, rates, IBB, XBI, SPY, IWM, VIX daily → {p['trade']} · cash",
            "tv": "LQD/IEF ratio SMA 100; TNX SMA 50; TLT SMA 100; XBI SMA 200 and 252-day change; SPY, IWM SMA 200; IBS = (close − low) / (high − low)",
            "rule": f"½ S3v (credit + yield < SMA{p['tnx_ma']} + TLT > SMA{p['tlt_ma']}) + ½ S2+v (XBI 1-yr up + credit + SPY, IWM > SMA200); IBS dips; else cash"}

    def backtest_run(self, now, cost, delay=0):
        from .. import backtest as BT
        p = self.params
        for s in self.read_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, model=True)
        sym = p["trade"]
        ibb = BT.daily_tr("IBB")
        tr = model_2x(BT.daily_tr(sym), {"IBB": ibb}, {"IBB": 1.0}, ibb.index, float(p["model_cost_pct"]) / 100).reindex(fr.index)
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
                "bench": {sym: tr.dropna(subset=["c"]), "IBB": ibb}, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": "IBB",
                "data_from": str(days[0]),
                "data_note": f"IBB, XBI, LQD, IEF, TLT, SPY and IWM daily bars with dividends added back, ^TNX and ^VIX daily closes (signals) · "
                             f"{sym} daily total-return prices; {sym} before {listed}: modelled as 2 × IBB daily minus {p['model_cost_pct']:g}% a year"}

    def check_table(self, now, rows=12):
        """An independent recompute of the 10-year yield's average and the two IBS values from the raw bars."""
        p = self.params
        fr = self.frame(now)
        tn = md.daily_closed("^TNX", now)
        tn = tn[~tn.index.duplicated(keep="last")]["c"].astype(float)
        cols = ["10-year yield", f"SMA{p['tnx_ma']} · bot / check", "IBB IBS · bot / check", "Held %"]
        out, worst = [], 0.0
        ib = md.daily_closed("IBB", now)
        ib = ib[~ib.index.duplicated(keep="last")]
        n = int(p["tnx_ma"])
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            past = [x for x in tn[tn.index <= d].tolist()[-n:]]
            ma = sum(past) / len(past)
            b = ib.loc[d]
            h, l, c = float(b["h"]), float(b["l"]), float(b["c"])
            ib_chk = (c - l) / (h - l) if h > l else 0.5
            diff = max(abs(r["tnx_ma"] - ma) / max(ma, 1e-9), abs(r["ibb_ibs"] - ib_chk))
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()), "vals": [float(r["tnx"]), f"{r['tnx_ma']:.4f} / {ma:.4f}", f"{r['ibb_ibs']:.3f} / {ib_chk:.3f}",
                        float(r["w"] * 100)], "ok": bool(diff < 1e-6)})
        return cols, out, worst
