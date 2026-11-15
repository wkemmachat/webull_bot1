"""Trend split: one leveraged ETF, the money split equally over three trend rules on the same index (one third each,
rebalanced once a year), each with a calm gate, a credit check and one-day IBS dips. Research: "Strategy research and stress
tests" round 3, USD split C (15 Nov 2026, claude/round3-overfitting-audit-and-stable-splits-nov-2026.md and
claude/usd-round3-vs-web-strategies-nov-2026.md). Signal at the close, fill at the next open.

After each US close, from daily bars, for each leg k = 1..3:
  up_k       index trend: close > SMA(n) or EMA(n), or ROC(n) = close ÷ close n days ago − 1 > 0
  calm_k     the index's vol_days-day standard deviation of daily changes is below its calm_q_k-th percentile over the last
             vol_lookback days, today included (calm_q = 0: always calm)
  credit     LQD ÷ IEF above the 100-day average of that ratio, on dividend-adjusted closes (investment-grade bonds holding up
             against Treasuries; one check shared by the legs, credit_ma = 0: off). Adjusted, as in the research: LQD pays more
             interest than IEF, so on plain closes the ratio slides every month and the check is off far more often (10 years:
             80% a year with plain closes, 93% adjusted, the research's figure).
  dip_k      NOT up_k and the dip symbol's IBS = (close − low) ÷ (high − low) < dip_ibs_max → hold the next day only
  in_k       (up_k and calm_k and credit) or dip_k
Each leg is a sub-account holding the ETF while in_k and cash otherwise. The three sub-accounts start each calendar year
equal; in between they drift with the ETF's daily moves, so the share in the ETF is the in-legs' part of the money:
  size = Σ value_k × in_k ÷ Σ value_k            (0, about ⅓, ⅔ or 100%)
With "every day" rebalancing, size = (number of legs in) ÷ 3 instead.
Every value is computed only on days where all the symbols the rule reads have a closed bar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as I
from .. import marketdata as md
from .base import register, switch_dot
from .regime import RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401
from .trend_dip import vol_gate
from .trend_gate import ibs_of

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "volatile": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"trend": "in · trend legs", "dip": "in · dip day", "volatile": "above the trend but held back (jumpy or credit)",
              "out": "out"}
LEGS = (1, 2, 3)
KINDS = ("SMA", "EMA", "ROC")


def _trend(c, kind, n):
    """(ready, up) for one leg's trend rule on closes c."""
    if kind == "ROC":
        prev = np.r_[np.full(n, np.nan), c[:-n]] if len(c) > n else np.full(len(c), np.nan)
        ok = ~np.isnan(prev)
        return ok, ok & (c > np.nan_to_num(prev, nan=np.inf))
    ma = I.ema(c, n) if kind == "EMA" else I.sma(c, n)
    ok = ~np.isnan(ma)
    return ok, ok & (c > np.nan_to_num(ma, nan=np.inf))


def _trend_line(c, kind, n):
    if kind == "ROC":
        return np.r_[np.full(n, np.nan), c[:-n]] if len(c) > n else np.full(len(c), np.nan)
    return I.ema(c, n) if kind == "EMA" else I.sma(c, n)


def adjusted_closes(sym, raw):
    """Dividend-adjusted closes on raw's days: Yahoo's total-return history scaled onto raw's closes by date; days newer than
    the adjusted history (today's close, before the once-a-day download) carry its last factor forward."""
    c = raw["c"].astype(float)
    try:
        from .. import backtest as BT
        tr = BT._raw_tr(sym)
    except Exception:
        tr = None
    if tr is None or tr.empty:
        return c.values
    rd = pd.Index(pd.DatetimeIndex(raw.index).tz_localize(None).normalize() if pd.DatetimeIndex(raw.index).tz is None
                  else pd.DatetimeIndex(raw.index).tz_convert("UTC").tz_localize(None).normalize())
    ti = pd.DatetimeIndex(tr.index)
    td = (ti.tz_convert("UTC").tz_localize(None) if ti.tz is not None else ti).normalize()
    trc = pd.Series(tr["c"].astype(float).values, index=td)
    trc = trc[~trc.index.duplicated(keep="last")]
    rc = pd.Series(c.values, index=rd)
    f = (trc / rc.reindex(trc.index)).dropna()
    f = f[(f > 0) & np.isfinite(f)]
    if f.empty:
        return c.values
    fac = f.reindex(rd).ffill().bfill().values
    return c.values * fac


def hold_between_changes(size, ins, years):
    """The target share changes only when a leg changes or a new year starts: between, the account drifts on its own (as the
    sub-accounts would), and the rebalance band catches a large drift. Without this the yearly-drift share would move a
    little every day and the bot would trade a few dollars every day."""
    out = np.array(size, dtype=float)
    for i in range(1, len(out)):
        if years[i] == years[i - 1] and (ins[i] == ins[i - 1]).all():
            out[i] = out[i - 1]
    return out


def split_sizes(ins, rets, years, yearly=True):
    """Share of the money in the ETF for each day. ins: (days × legs) bool, in at that close; rets: the ETF's close-to-close
    change on that day; years: calendar year of each day. Yearly: sub-accounts reset equal on the first day of each year,
    then drift (a leg in yesterday earns today's move). Every day: the plain share of legs in."""
    n, k = ins.shape
    if not yearly:
        return ins.sum(axis=1) / k
    v = np.ones(k) / k
    out = np.zeros(n)
    for i in range(n):
        if i > 0:
            if years[i] != years[i - 1]:
                v = np.full(k, v.sum() / k)                     # rebalanced at the year's last close (before today's move)
            r = rets[i] if rets[i] == rets[i] else 0.0
            v = v * (1 + r * ins[i - 1])
        tot = v.sum()
        out[i] = float((v * ins[i]).sum() / tot) if tot > 0 else 0.0
    return out


@register
class TrendSplitStrategy(RegimeStrategy):
    type = "trend_split"
    label = "Trend split (three trend rules on one ETF, a third each, calm + credit gates, IBS dips)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: the money split over three trend rules on the same index (SMA, EMA or ROC), each held while the index is "
                   "calm and credit (LQD ÷ IEF) is above its average, with one-day IBS dips below the trend; rebalanced once a year.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Read the trend from", "kind": "symbol", "default": "SMH", "group": "Symbols",
         "help": "Index ETF, daily bars"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "USD", "group": "Symbols",
         "help": "Leveraged ETF held by the legs that are in"},
        {"key": "cash_symbol", "label": "When out, hold", "kind": "symbol", "default": "", "group": "Symbols",
         "help": "Empty = plain cash (the research)"},
        {"key": "leg1_kind", "label": "Leg 1: trend rule", "kind": "select", "default": "SMA", "options": list(KINDS), "group": "Legs"},
        {"key": "leg1_days", "label": "Leg 1: days", "kind": "int", "default": 150, "min": 5, "max": 400, "group": "Legs"},
        {"key": "leg1_calm_q", "label": "Leg 1: calm percentile (0 = off)", "kind": "float", "default": 90.0, "min": 0, "max": 99,
         "group": "Legs"},
        {"key": "leg2_kind", "label": "Leg 2: trend rule", "kind": "select", "default": "ROC", "options": list(KINDS), "group": "Legs"},
        {"key": "leg2_days", "label": "Leg 2: days", "kind": "int", "default": 126, "min": 5, "max": 400, "group": "Legs"},
        {"key": "leg2_calm_q", "label": "Leg 2: calm percentile (0 = off)", "kind": "float", "default": 90.0, "min": 0, "max": 99,
         "group": "Legs"},
        {"key": "leg3_kind", "label": "Leg 3: trend rule", "kind": "select", "default": "EMA", "options": list(KINDS), "group": "Legs"},
        {"key": "leg3_days", "label": "Leg 3: days", "kind": "int", "default": 150, "min": 5, "max": 400, "group": "Legs"},
        {"key": "leg3_calm_q", "label": "Leg 3: calm percentile (0 = off)", "kind": "float", "default": 80.0, "min": 0, "max": 99,
         "group": "Legs"},
        {"key": "vol_days", "label": "Calm: volatility window (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Gates"},
        {"key": "vol_lookback", "label": "Calm: percentile over (days)", "kind": "int", "default": 252, "min": 60, "max": 756,
         "group": "Gates"},
        {"key": "credit_a", "label": "Credit check: bonds", "kind": "symbol", "default": "LQD", "group": "Gates",
         "help": "Investment-grade corporate bonds"},
        {"key": "credit_b", "label": "Credit check: against", "kind": "symbol", "default": "IEF", "group": "Gates",
         "help": "7–10 year Treasuries"},
        {"key": "credit_ma", "label": "Credit check: ratio above its SMA (days, 0 = off)", "kind": "int", "default": 100, "min": 0,
         "max": 400, "group": "Gates"},
        {"key": "dip_ibs_max", "label": "IBS dip below the trend: IBS below (0 = off)", "kind": "float", "default": 0.3, "min": 0,
         "max": 0.5, "group": "Dips", "help": "Per leg, on days its trend is off; held for the next day only"},
        {"key": "dip_ibs_symbol", "label": "IBS dip: read from", "kind": "symbol", "default": "SMH", "group": "Dips",
         "help": "Empty = the traded ETF"},
        {"key": "rebalance_legs", "label": "Rebalance the legs", "kind": "select", "default": "yearly",
         "options": ["yearly", "daily"], "group": "Money",
         "help": "yearly = the research (equal thirds on the first day of each year); daily = always (legs in) ÷ 3"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    @classmethod
    def merge_params(cls, given: dict) -> dict:
        out = super().merge_params(given)
        for k in LEGS:
            t = str(out.get(f"leg{k}_kind") or "").strip().upper()
            if t not in KINDS:
                raise ValueError(f"Leg {k}: trend rule SMA, EMA or ROC (not {out.get(f'leg{k}_kind')})")
            out[f"leg{k}_kind"] = t
        r = str(out.get("rebalance_legs") or "yearly").strip().lower()
        if r not in ("yearly", "daily"):
            raise ValueError("Rebalance the legs: yearly or daily")
        out["rebalance_legs"] = r
        return out

    # ---------------------------------------------------------------- symbols
    def gold_sym(self):
        return ""

    def gold_share(self):
        return 0.0

    def dip_sym(self):
        return self.params.get("dip_ibs_symbol") or self.params["trade"]

    def credit_on(self):
        p = self.params
        return int(p.get("credit_ma") or 0) > 0 and p.get("credit_a") and p.get("credit_b")

    def read_symbols(self):
        p = self.params
        out = [p["signal"], p["trade"]]
        if p["dip_ibs_max"] > 0:
            out.append(self.dip_sym())
        if self.credit_on():
            out += [p["credit_a"], p["credit_b"]]
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
        return [s for s in (p["trade"], p["cash_symbol"]) if s]

    def benchmark_symbol(self):
        return self.params["trade"]

    def parking(self) -> dict:
        p = self.params
        return {p["cash_symbol"]: round(1 - self.buffer(), 4)} if p["cash_symbol"] else {}

    def cash_target(self):
        return self.parking()

    def park_text(self):
        return self.params["cash_symbol"] or "cash"

    def leg_name(self, k):
        p = self.params
        kind, n = p[f"leg{k}_kind"], p[f"leg{k}_days"]
        return f"ROC{n} > 0" if kind == "ROC" else f"{kind}{n}"

    def leg_text(self, k):
        p = self.params
        q = p[f"leg{k}_calm_q"]
        gates = ([f"calm {q:g}"] if q > 0 else []) + (["credit OK"] if self.credit_on() else [])
        return f"{self.leg_name(k)}" + (f" · {' & '.join(gates)}" if gates else "")

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
        legs = {}
        for k in LEGS:
            ok, up = _trend(cs, p[f"leg{k}_kind"], p[f"leg{k}_days"])
            q = p[f"leg{k}_calm_q"]
            if q > 0:
                calm, vol, thr = vol_gate(cs, q, p["vol_days"], p["vol_lookback"])
                ok = ok & ~np.isnan(thr)
            else:
                calm, vol, thr = np.ones(len(cs), dtype=bool), np.full(len(cs), np.nan), np.full(len(cs), np.nan)
            legs[k] = {"ok": ok, "up": up & ok, "calm": calm, "vol": vol, "thr": thr, "line": _trend_line(cs, p[f"leg{k}_kind"], p[f"leg{k}_days"])}
        idx = sg.index
        for df in dfs.values():
            idx = idx.intersection(df.index)
        # credit: LQD ÷ IEF on their common days, above its own SMA
        if self.credit_on():
            a = pd.Series(adjusted_closes(p["credit_a"], dfs[p["credit_a"]]), index=dfs[p["credit_a"]].index)
            b = pd.Series(adjusted_closes(p["credit_b"], dfs[p["credit_b"]]), index=dfs[p["credit_b"]].index)
            cix = a.index.intersection(b.index)
            ratio = (a.reindex(cix) / b.reindex(cix)).values
            rma = I.sma(ratio, p["credit_ma"])
            cr_ok = pd.Series(~np.isnan(rma), index=cix)
            cr_up = pd.Series(~np.isnan(rma) & (ratio > np.nan_to_num(rma, nan=np.inf)), index=cix)
            cr_ratio, cr_ma = pd.Series(ratio, index=cix), pd.Series(rma, index=cix)
        need = max(max(p[f"leg{k}_days"] for k in LEGS), p["vol_lookback"] + p["vol_days"], int(p.get("credit_ma") or 0)) + 2
        if len(idx) < need:
            raise md.DataError(f"Need {need} daily bars of {', '.join(dfs)} on the same days, have {len(idx)}")
        pos = sg.index.get_indexer(idx)

        def on(x):
            return np.asarray(x)[pos]
        sig = sg.reindex(idx)
        c = on(cs)
        if self.credit_on():
            credit, credit_ok = cr_up.reindex(idx).fillna(False).values.astype(bool), cr_ok.reindex(idx).fillna(False).values.astype(bool)
            ratio_v, rma_v = cr_ratio.reindex(idx).values, cr_ma.reindex(idx).values
        else:
            credit, credit_ok = np.ones(len(c), dtype=bool), np.ones(len(c), dtype=bool)
            ratio_v, rma_v = np.full(len(c), np.nan), np.full(len(c), np.nan)
        ibs = ibs_of(dfs[self.dip_sym()].reindex(idx)) if p["dip_ibs_max"] > 0 else np.full(len(c), np.nan)
        fr = pd.DataFrame(index=idx)
        fr["o"], fr["h"], fr["l"], fr["c"] = sig["o"].values, sig["h"].values, sig["l"].values, c
        okall = credit_ok.copy()
        ins = np.zeros((len(c), len(LEGS)), dtype=bool)
        for j, k in enumerate(LEGS):
            L = legs[k]
            ok, up, calm = on(L["ok"]), on(L["up"]), on(L["calm"])
            okall &= ok
            trend = up & calm & credit
            dip = ok & ~up & (ibs < p["dip_ibs_max"]) if p["dip_ibs_max"] > 0 else np.zeros(len(c), dtype=bool)
            ins[:, j] = trend | dip
            fr[f"l{k}_line"], fr[f"l{k}_vol"], fr[f"l{k}_thr"] = on(L["line"]), on(L["vol"]) * 100, on(L["thr"]) * 100
            fr[f"l{k}_up"], fr[f"l{k}_calm"], fr[f"l{k}_trend"], fr[f"l{k}_dip"] = up, calm, trend, dip
        ins &= okall[:, None]
        tc = dfs[p["trade"]]["c"].astype(float).reindex(idx).values
        rets = np.r_[np.nan, tc[1:] / tc[:-1] - 1]
        years = np.array([d.year for d in pd.DatetimeIndex(idx).tz_convert("America/New_York")])
        size = hold_between_changes(split_sizes(ins, rets, years, yearly=p["rebalance_legs"] == "yearly"), ins, years)
        size = np.where(okall, np.round(size, 4), 0.0)
        anytrend = np.zeros(len(c), dtype=bool)
        anyup = np.zeros(len(c), dtype=bool)
        for k in LEGS:
            anytrend |= fr[f"l{k}_trend"].values
            anyup |= fr[f"l{k}_up"].values
        state = np.array([""] * len(c), dtype=object)
        for i in range(len(c)):
            if not okall[i]:
                continue
            state[i] = ("trend" if anytrend[i] else "dip") if size[i] > 0 else ("volatile" if anyup[i] else "out")
        fr["credit"], fr["credit_ratio"], fr["credit_ma"] = credit, ratio_v, rma_v
        fr["ibs"] = ibs
        fr["legs_in"] = ins.sum(axis=1)
        fr["size"] = size
        fr["weight"] = size
        fr["state"] = state
        fr["sma_long"] = fr["l1_line"]                                 # name used by other parts of the app (dip zones)
        fr["ma"] = fr["l1_line"]
        return fr

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def target_for(self, state, size=None):
        p, buf = self.params, self.buffer()
        s = 0.0 if size is None else max(0.0, min(1.0, float(size)))
        if s <= 0:
            return self.parking()
        t = {p["trade"]: round(s * (1 - buf), 4)}
        if p["cash_symbol"] and 1 - s > 0.0005:
            t[p["cash_symbol"]] = round((1 - s) * (1 - buf), 4)
        return {k: v for k, v in t.items() if v > 0}

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        p = self.params
        word = h["kind"]
        return f"{word} · {self.name}\n{h['text']}\n{p['trade']} {h['from']} → {h['to']} of the money"

    def leg_words(self, fr, i):
        p, r, out = self.params, fr.iloc[i], []
        for k in LEGS:
            if bool(r[f"l{k}_trend"]):
                out.append(f"{self.leg_name(k)} in")
            elif bool(r[f"l{k}_dip"]):
                out.append(f"{self.leg_name(k)} dip day")
            elif bool(r[f"l{k}_up"]):
                why = []
                if not bool(r[f"l{k}_calm"]):
                    why.append("jumpy")
                if not bool(r["credit"]):
                    why.append("credit weak")
                out.append(f"{self.leg_name(k)} held back ({', '.join(why)})")
            else:
                out.append(f"{self.leg_name(k)} out")
        return " · ".join(out)

    def why(self, fr, i):
        p = self.params
        r = fr.iloc[i]
        head = f"{int(r['legs_in'])} of 3 legs in"
        if any(bool(r[f"l{k}_dip"]) for k in LEGS):
            head += f" ({self.dip_sym()} IBS {r['ibs']:.2f} < {p['dip_ibs_max']:g}: dip legs hold the next day)"
        return f"{head}: {self.leg_words(fr, i)}"

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state, size = last["state"], float(last["size"])
        szv = fr["size"].values
        sig_size = np.where(fr["legs_in"].values > 0, 1, 0)
        n_in = fr["legs_in"].values
        k = len(fr) - 1
        while k > 0 and n_in[k - 1] == n_in[k]:
            k -= 1
        hist, sts = [], fr["state"].values
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if n_in[i] != n_in[i - 1]:
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if n_in[i] > n_in[i - 1] else "SELL",
                             "from": f"{szv[i - 1] * 100:.0f}%", "to": f"{szv[i] * 100:.0f}%", "price": float(fr["c"].iloc[i]),
                             "text": self.why(fr, i)})
        del sig_size
        target = self.target_for(state, size)
        checks = []
        for kk in LEGS:
            line = float(last[f"l{kk}_line"])
            kind = p[f"leg{kk}_kind"]
            if kind == "ROC":
                pct = (last["c"] / line - 1) * 100
                v = f"{pct:+.1f}% over {p[f'leg{kk}_days']} days"
            else:
                pct = (last["c"] / line - 1) * 100
                v = f"{last['c']:,.2f} vs {line:,.2f} · {pct:+.1f}%"
            q = p[f"leg{kk}_calm_q"]
            calm_txt = ""
            if q > 0:
                vv, vt = float(last[f"l{kk}_vol"]), float(last[f"l{kk}_thr"])
                calm_txt = f" · vol {vv:.2f}% vs p{q:g} {vt:.2f}% ({'calm' if vv < vt else 'jumpy'})"
            st = ("in · trend" if bool(last[f"l{kk}_trend"]) else "in · dip day" if bool(last[f"l{kk}_dip"])
                  else "held back" if bool(last[f"l{kk}_up"]) else "out")
            checks.append({"k": f"Leg {kk} · {self.leg_text(kk)}", "v": f"{st} · {v}{calm_txt}",
                           "cls": "up" if st.startswith("in") else "warn" if st == "held back" else "dn",
                           "h": (f"In while {p['signal']} closes above its {self.leg_name(kk)}" if kind != "ROC" else
                                 f"In while {p['signal']} is higher than {p[f'leg{kk}_days']} trading days ago")
                                + (" and is calm" if q > 0 else "") + (" and credit is OK" if self.credit_on() else "")})
        if self.credit_on():
            cr, cm = float(last["credit_ratio"]), float(last["credit_ma"])
            checks.append({"k": f"Credit · {p['credit_a']} ÷ {p['credit_b']}", "v": f"{cr:.4f} vs SMA{p['credit_ma']} {cm:.4f} · "
                           f"{'OK' if cr > cm else 'weak'}", "cls": "up" if cr > cm else "warn",
                           "h": "Trend legs hold only while corporate bonds keep up with Treasuries (dividend-adjusted ratio above its average)"})
        if p["dip_ibs_max"] > 0:
            v = float(last["ibs"])
            checks.append({"k": f"IBS · {self.dip_sym()}", "v": f"{v:.2f}", "cls": "warn" if v < p["dip_ibs_max"] else "",
                           "h": f"A leg whose trend is off buys {p['trade']} for one day when IBS < {p['dip_ibs_max']:g}"})
        checks.append({"k": "Size", "v": f"{size * 100:.0f}% {p['trade']} · {int(last['legs_in'])} of 3 legs in",
                       "h": "Each leg is a third of the money, rebalanced " + ("on the first day of each year" if p["rebalance_legs"] == "yearly" else "every day")})
        tiles = [{"k": "trend", "title": "In · trend legs", "text": "A leg is in while its trend is up, the index is calm and credit is OK",
                  "hold": f"{p['trade']}: the in-legs' share (about ⅓, ⅔ or all)", "color": STATE_COLOR["trend"]},
                 {"k": "dip", "title": "In · dip day", "text": f"Legs whose trend is off buy one day after {self.dip_sym()} IBS < {p['dip_ibs_max']:g}",
                  "hold": f"those legs' share in {p['trade']}", "color": STATE_COLOR["dip"]},
                 {"k": "volatile", "title": "Out · held back", "text": "Trend up but jumpy or credit weak", "hold": self.park_text(),
                  "color": STATE_COLOR["volatile"]},
                 {"k": "out", "title": "Out", "text": "No leg in", "hold": self.park_text(), "color": STATE_COLOR["out"]}]
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            a0, a1 = (szv[i - 1] if i > 0 else szv[i]), szv[i]
            ch = i > 0 and n_in[i] != n_in[i - 1]
            act = ("no trade" if not ch else f"buy to {a1 * 100:.0f}% {p['trade']} next open" if n_in[i] > n_in[i - 1]
                   else f"sell to {a1 * 100:.0f}% {p['trade']} next open")

            def num(x):
                return float(x) if x == x else None
            row = {"date": str(fr.index[i].date()), "close": float(r["c"]), "ibs": num(r["ibs"]), "credit": num(r["credit_ratio"]),
                   "legs": int(r["legs_in"]), "size": float(r["size"]) * 100, "state": r["state"], "action": act, "changed": bool(ch),
                   "from": sts[i - 1] if i > 0 else None}
            for kk in LEGS:
                row[f"l{kk}"] = ("in" if bool(r[f"l{kk}_trend"]) else "dip" if bool(r[f"l{kk}_dip"]) else "held" if bool(r[f"l{kk}_up"]) else "out")
            log_rows.append(row)
        log_cols = ([{"k": "close", "label": p["signal"], "fmt": "n2"}]
                    + [{"k": f"l{kk}", "label": self.leg_name(kk), "fmt": "text"} for kk in LEGS]
                    + ([{"k": "credit", "label": f"{p['credit_a']}/{p['credit_b']}", "fmt": "n4"}] if self.credit_on() else [])
                    + ([{"k": "ibs", "label": f"IBS {self.dip_sym()}", "fmt": "n2"}] if p["dip_ibs_max"] > 0 else [])
                    + [{"k": "legs", "label": "Legs in", "fmt": "n0"}, {"k": "size", "label": "Size %", "fmt": "n0"}])
        nin = int(last["legs_in"])
        label = (f"IN · {size * 100:.0f}% {p['trade']} ({nin} of 3 legs" + (", dip" if state == "dip" else "") + ")") if size > 0 else \
            (f"OUT · {self.park_text()} (held back)" if state == "volatile" else f"OUT · {self.park_text()}")
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": float(last["c"]), "sma_long": float(last["l1_line"]), "state_text": STATE_TEXT[state], "size": size,
                           "legs_in": nin, "title": "Position · decided after each US close"}}

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(fr))]

        n_in, stv, sz = fr["legs_in"].values, fr["state"].values, fr["size"].values
        markers = []
        for i in range(1, len(fr)):
            if not stv[i - 1]:
                continue
            if n_in[i] == n_in[i - 1]:
                if n_in[i] > 0 and stv[i] != stv[i - 1]:
                    markers.append(switch_dot(t[i], stv[i], STATE_COLOR))
                continue
            b = n_in[i] > n_in[i - 1]
            markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                            "shape": "arrowUp" if b else "arrowDown", "text": f"{'Buy' if b else 'Sell'} → {sz[i] * 100:.0f}%"})
        colors = ["#FF9800", "#26A69A", "#5B8DEF"]
        lines = [{"name": self.leg_name(k), "color": colors[j], "width": 2 if j == 0 else 1, "data": ln(f"l{k}_line")}
                 for j, k in enumerate(LEGS) if p[f"leg{k}_kind"] != "ROC"]
        panes = []
        qs = sorted({p[f"leg{k}_calm_q"] for k in LEGS if p[f"leg{k}_calm_q"] > 0})
        if qs:
            vl = [{"name": "Volatility", "color": "#8E6BBF", "width": 2, "data": ln(f"l{[k for k in LEGS if p[f'leg{k}_calm_q'] > 0][0]}_vol", 3)}]
            for q in qs:
                kq = [k for k in LEGS if p[f"leg{k}_calm_q"] == q][0]
                vl.append({"name": f"{q:g}th percentile", "color": "#FF9800" if q == qs[-1] else "#F5C76B", "width": 1, "data": ln(f"l{kq}_thr", 3)})
            panes.append({"id": "vol", "title": f"Volatility {p['vol_days']}d (% a day)", "height": 100, "lines": vl, "hlines": []})
        if self.credit_on():
            panes.append({"id": "credit", "title": f"Credit · {p['credit_a']} ÷ {p['credit_b']}", "height": 90,
                          "lines": [{"name": "Ratio", "color": "#20C997", "width": 2, "data": ln("credit_ratio", 5)},
                                    {"name": f"SMA {p['credit_ma']}", "color": "#FF9800", "width": 1, "data": ln("credit_ma", 5)}], "hlines": []})
        if p["dip_ibs_max"] > 0:
            panes.append({"id": "ibs", "title": f"IBS {self.dip_sym()} (close position in the day's range)", "height": 90,
                          "lines": [{"name": f"IBS {self.dip_sym()}", "color": "#F5C76B", "width": 1, "data": ln("ibs", 3)}],
                          "hlines": [{"value": p["dip_ibs_max"], "label": f"dip < {p['dip_ibs_max']:g}"}]})
        panes.append({"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                      "lines": [{"name": "Size", "color": self.color, "width": 2, "area": True, "data": ln("size", 1, 100)}], "hlines": []})
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — the three trend legs, volatility and IBS are read from this chart",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": lines, "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
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
        legs = "; ".join(f"leg {k}: {self.leg_text(k)}" for k in LEGS)
        rules = [f"After each US close, read {p['signal']}'s daily bar" + (f", {p['credit_a']} and {p['credit_b']}" if self.credit_on() else "")
                 + (f" and {self.dip_sym()}'s IBS" if p["dip_ibs_max"] > 0 and self.dip_sym() != p["signal"] else "") + ".",
                 f"The money is split into three legs, a third each: {legs}."]
        for k in LEGS:
            kind, n, q = p[f"leg{k}_kind"], p[f"leg{k}_days"], p[f"leg{k}_calm_q"]
            tr = (f"{p['signal']} closes above its {kind}{n}" if kind != "ROC" else f"{p['signal']} is higher than {n} trading days ago")
            rules.append(f"Leg {k} holds {p['trade']} while {tr}"
                         + (f", its {p['vol_days']}-day volatility is below its {q:g}th percentile of the last {p['vol_lookback']} days" if q > 0 else "")
                         + (f" and {p['credit_a']} ÷ {p['credit_b']} closes above its {p['credit_ma']}-day average" if self.credit_on() else "") + ".")
        if p["dip_ibs_max"] > 0:
            rules.append(f"A leg whose trend is off holds {p['trade']} for the next day only when {self.dip_sym()} closes with IBS = "
                         f"(close − low) ÷ (high − low) < {p['dip_ibs_max']:g}.")
        rules += [f"Otherwise a leg is in {self.park_text()}. The share in {p['trade']} is the in-legs' part of the money: about ⅓, ⅔ or all.",
                  "The legs are set back to a third each " + ("on the first trading day of each year." if p["rebalance_legs"] == "yearly" else "every day."),
                  "Orders start at the next market open, split into lots."]
        return {"rules": rules,
                "flow": f"{p['signal']} daily × 3 legs" + (f" + {p['credit_a']}/{p['credit_b']} credit" if self.credit_on() else "")
                        + f" → {p['trade']} · {self.park_text()}",
                "tv": " · ".join(f'leg {k}: "' + ("Rate Of Change" if p[f"leg{k}_kind"] == "ROC" else
                                                  "Moving Average" + (" Exponential" if p[f"leg{k}_kind"] == "EMA" else "")) + f'" length {p[f"leg{k}_days"]}'
                                 for k in LEGS) + f" on {p['signal']} daily; IBS = (close − low) / (high − low)"
                      + (f"; credit: {p['credit_a']}/{p['credit_b']} with SMA {p['credit_ma']}" if self.credit_on() else ""),
                "rule": f"⅓ each: {' | '.join(self.leg_text(k) for k in LEGS)}; 1-day dips after {self.dip_sym()} IBS < {p['dip_ibs_max']:g} "
                        f"below a leg's trend → {p['trade']}, else {self.park_text()}"}

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        """Recompute the last `rows` decisions the long way (plain loops) and compare legs in and size."""
        p = self.params
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        sg = md.daily_closed(p["signal"], now)
        sg = sg[~sg.index.duplicated(keep="last")]
        c = sg["c"].astype(float).tolist()
        n = len(c)
        spos = {d: i for i, d in enumerate(sg.index)}

        def ma_at(kind, L, i):
            if kind == "SMA":
                return sum(c[i - L + 1:i + 1]) / L if i >= L - 1 else float("nan")
            if kind == "ROC":
                return c[i - L] if i >= L else float("nan")
            a = 2.0 / (L + 1)
            e = sum(c[:L]) / L
            for j in range(L, i + 1):
                e = a * c[j] + (1 - a) * e
            return e if i >= L - 1 else float("nan")
        chg = [float("nan")] + [c[i] / c[i - 1] - 1 for i in range(1, n)]
        vd, lb = p["vol_days"], p["vol_lookback"]
        sd = [float("nan")] * n
        for i in range(vd, n):
            w = chg[i - vd + 1:i + 1]
            m = sum(w) / vd
            sd[i] = (sum((x - m) ** 2 for x in w) / (vd - 1)) ** 0.5

        def calm_at(i, q):
            if q <= 0:
                return True
            win = sd[i - lb + 1:i + 1] if i >= lb - 1 else []
            if len(win) < lb or any(x != x for x in win):
                return False
            srt = sorted(win)
            qq = (len(srt) - 1) * q / 100.0
            lo = int(qq)
            hi = min(lo + 1, len(srt) - 1)
            return sd[i] < srt[lo] + (srt[hi] - srt[lo]) * (qq - lo)
        cra = cr = None
        if self.credit_on():
            a, b = md.daily_closed(p["credit_a"], now), md.daily_closed(p["credit_b"], now)
            a, b = a[~a.index.duplicated(keep="last")], b[~b.index.duplicated(keep="last")]
            aa = dict(zip(a.index, adjusted_closes(p["credit_a"], a)))
            bb = dict(zip(b.index, adjusted_closes(p["credit_b"], b)))
            cix = a.index.intersection(b.index)
            cr = [float(aa[d]) / float(bb[d]) for d in cix]
            cra = {d: j for j, d in enumerate(cix)}
        dsrc = md.daily_closed(self.dip_sym(), now)
        dsrc = dsrc[~dsrc.index.duplicated(keep="last")]
        out = []
        for day in fr.index[-rows:]:
            i = spos[day]
            credit = True
            if cr is not None:
                j, L = cra[day], p["credit_ma"]
                credit = j >= L - 1 and cr[j] > sum(cr[j - L + 1:j + 1]) / L
            r = dsrc.loc[day]
            rg = float(r["h"]) - float(r["l"])
            ibs = round((float(r["c"]) - float(r["l"])) / rg, 4) if rg > 0 else 0.5
            nin = 0
            for k in LEGS:
                kind, L, q = p[f"leg{k}_kind"], p[f"leg{k}_days"], p[f"leg{k}_calm_q"]
                ref = ma_at(kind, L, i)
                up = ref == ref and c[i] > ref
                isin = (up and calm_at(i, q) and credit) or (not up and p["dip_ibs_max"] > 0 and ibs < p["dip_ibs_max"])
                nin += bool(isin)
            got = int(fr.loc[day, "legs_in"])
            out.append({"t": int(pd.Timestamp(day).timestamp()), "vals": [round(c[i], 2), got, nin, fr.loc[day, "state"]],
                        "ok": got == nin})
        cols = ["Close", "Legs in · bot", "Legs in · check", "State"]
        return cols, out, float(sum(0 if r["ok"] else 1 for r in out))
