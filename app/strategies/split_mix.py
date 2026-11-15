"""Split mix: the money split equally over several daily strategies that trade the same ETF (each leg a strategy of an existing
type with its own settings), rebalanced once a year. Research: "Strategy research and stress tests" round 2 split C for QLD
(15 Nov 2026, claude/round2-splits-beat-round1-nov-2026.md): a third each in QLD-A (Trend + volatility gate + dips),
QLD-B and QLD-C (IBD trend + calm + one-day RSI dips). Signal at the close, fill at the next open.

Each leg is a sub-account that follows its own strategy's target (the ETF, the gold ETF and cash). The sub-accounts start each
calendar year equal; in between each grows with what it holds, so the mix's target is the value-weighted average of the legs'
targets. It changes only when a leg's target changes or a new year starts: between, the account drifts as the sub-accounts
would, and the rebalance band catches a large drift. Every leg must trade the same ETF; legs may park differently (one in
cash, another half in gold), but in the same gold ETF and the same cash ETF. A leg may carry a "weight" (% of the money,
default equal): round 2 ROM split C is 67% / 33%.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import marketdata as md
from .base import TYPES, register, switch_dot
from .regime import RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

STATE_COLOR = {"trend": "#26A69A", "dip": "#F5C76B", "volatile": "#8E6BBF", "out": "#4A5263"}
STATE_TEXT = {"trend": "one or more legs in the trend", "dip": "only dip legs in", "volatile": "out · a leg's trend is up but held back",
              "out": "no leg in"}
LEG_COLORS = ["#FF9800", "#26A69A", "#5B8DEF", "#E46AA8"]


@register
class SplitMixStrategy(RegimeStrategy):
    type = "split_mix"
    label = "Split mix (the money split equally over several strategies on one ETF, rebalanced once a year)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: the money split over 2 to 4 strategies that trade the same ETF (equal or by weight), each with its "
                   "own rules; the parts are set back to equal once a year.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 5, "lots": 10, "exit_mode": "asap"}
    PARAMS = [
        {"key": "signal", "label": "Index (for the chart)", "kind": "symbol", "default": "QQQ", "group": "Symbols"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "QLD", "group": "Symbols",
         "help": "Every leg must trade this ETF"},
        {"key": "legs", "label": "Legs (JSON)", "kind": "text", "default": "[]", "group": "Legs",
         "help": 'A list of {"name", "type", "params", "weight"}: each leg is a strategy of that type with those settings; weight = % of '
                 'the money (optional, default equal)'},
        {"key": "rebalance_legs", "label": "Rebalance the legs", "kind": "select", "default": "yearly", "options": ["yearly", "daily"],
         "group": "Money", "help": "yearly = the research (back to the set shares on the first day of each year); daily = always the set shares"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 20.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade only when a holding drifts this far from its target"},
    ]

    @classmethod
    def merge_params(cls, given: dict) -> dict:
        if isinstance((given or {}).get("legs"), list):
            given = {**given, "legs": json.dumps(given["legs"])}
        out = super().merge_params(given)
        raw = out.get("legs")
        legs = raw if isinstance(raw, list) else json.loads(raw or "[]")
        if not isinstance(legs, list) or not 2 <= len(legs) <= 4:
            raise ValueError("Legs: a list of 2 to 4 strategies")
        clean = []
        for k, lg in enumerate(legs, 1):
            t = (lg or {}).get("type")
            if t not in TYPES or t == cls.type or TYPES[t].family != "regime":
                raise ValueError(f"Leg {k}: a daily strategy type (not {t})")
            inst = TYPES[t]({"id": f"leg{k}", "name": lg.get("name") or f"Leg {k}", "params": lg.get("params") or {}})
            if inst.params.get("trade") != out["trade"]:
                raise ValueError(f"Leg {k}: trades {inst.params.get('trade')}, not {out['trade']}")
            item = {"name": lg.get("name") or f"Leg {k}", "type": t, "params": inst.params}
            if lg.get("weight") not in (None, ""):
                try:
                    wgt = float(lg["weight"])
                except (TypeError, ValueError):
                    raise ValueError(f"Leg {k}: weight must be a number (% of the money)")
                if not 1 <= wgt <= 99:
                    raise ValueError(f"Leg {k}: weight between 1 and 99 (% of the money)")
                item["weight"] = wgt
            clean.append(item)
        if 0 < sum(1 for c in clean if "weight" in c) < len(clean):
            raise ValueError("Legs: give every leg a weight, or none (equal)")
        golds = {c["params"].get("gold_symbol") or "GLD" for c in clean if float(c["params"].get("gold_share_pct") or 0) > 0}
        cashes = {c["params"].get("cash_symbol") or "" for c in clean}
        if len(golds) > 1 or len(cashes) > 1:
            raise ValueError("Legs: every leg must park in the same gold ETF and the same cash ETF")
        out["legs"] = json.dumps(clean)
        r = str(out.get("rebalance_legs") or "yearly").strip().lower()
        if r not in ("yearly", "daily"):
            raise ValueError("Rebalance the legs: yearly or daily")
        out["rebalance_legs"] = r
        return out

    # ---------------------------------------------------------------- legs and symbols
    def legs(self):
        if not hasattr(self, "_legs"):
            self._legs = []
            for k, lg in enumerate(json.loads(self.params["legs"]), 1):
                inst = TYPES[lg["type"]]({"id": f"{self.id}#leg{k}", "name": lg["name"], "color": LEG_COLORS[(k - 1) % 4],
                                          "params": {**lg["params"], "cash_buffer_pct": self.params.get("cash_buffer_pct", 1.0)}})
                self._legs.append(inst)
        return self._legs

    def weights(self):
        """Each leg's share of the money at the start of each year (sums to 1)."""
        raw = json.loads(self.params["legs"])
        w = np.array([float(lg.get("weight") or 0) for lg in raw]) if all(lg.get("weight") for lg in raw) else np.ones(len(raw))
        return w / w.sum()

    def equal(self):
        w = self.weights()
        return bool(np.allclose(w, w[0]))

    def leg_share(self, k):
        return f"{self.weights()[k] * 100:.0f}%"

    def gold_share(self):
        """The money-weighted gold share of the parked money (for the text only; each leg parks by its own rule)."""
        return float(sum(w * (lg.gold_share() if hasattr(lg, "gold_share") else 0.0) for w, lg in zip(self.weights(), self.legs())))

    def gold_sym(self):
        for lg in self.legs():
            g = lg.gold_sym() if hasattr(lg, "gold_sym") else ""
            if g:
                return g
        return ""

    def read_symbols(self):
        out = [self.params["signal"], self.params["trade"]]
        for lg in self.legs():
            out += lg.history_symbols() if hasattr(lg, "history_symbols") else [lg.params.get("signal")]
        return list(dict.fromkeys(s for s in out if s))

    def data_needs(self):
        out = []
        for lg in self.legs():
            out += lg.data_needs()
        return list(dict.fromkeys(out + [(self.params["signal"], "1d"), (self.params["trade"], "1d")]))

    def history_symbols(self):
        return self.read_symbols()

    def bench_extra(self):
        s = self.params["signal"]
        return [s] if s != self.params["trade"] else []

    def trade_symbols(self):
        out = []
        for lg in self.legs():
            out += lg.trade_symbols()
        return list(dict.fromkeys(s for s in out if s))

    def benchmark_symbol(self):
        return self.params["trade"]

    def parking(self) -> dict:
        out = {}
        for w, lg in zip(self.weights(), self.legs()):
            for k, v in lg.parking().items():
                out[k] = round(out.get(k, 0.0) + w * v, 4)
        return out

    def cash_target(self):
        return self.parking()

    def park_text(self):
        texts = [lg.park_text() if hasattr(lg, "park_text") else "cash" for lg in self.legs()]
        return texts[0] if len(set(texts)) == 1 else "each leg's own parking (" + " · ".join(dict.fromkeys(texts)) + ")"

    # ---------------------------------------------------------------- the maths
    def frame(self, now) -> pd.DataFrame:
        p = self.params
        legs = self.legs()
        frs = []
        for lg in legs:
            f = lg.frame(now)
            lg.frame_cache = f                                  # each leg's reasons for the history (why)
            frs.append(f[f["state"] != ""])
        idx = frs[0].index
        for f in frs[1:]:
            idx = idx.intersection(f.index)
        if len(idx) < 30:
            raise md.DataError("Not enough history shared by the legs yet")
        trade, gold, cash = p["trade"], self.gold_sym(), self.cash_sym()
        n, K = len(idx), len(legs)
        W, G, Cs = np.zeros((n, K)), np.zeros((n, K)), np.zeros((n, K))
        st = np.empty((n, K), dtype=object)
        sz = np.zeros((n, K))
        for k, (lg, f) in enumerate(zip(legs, frs)):
            f = f.reindex(idx)
            states, sizes = f["state"].values, (f["size"].values if "size" in f.columns else np.full(n, np.nan))
            for i in range(n):
                t = lg.target_for(states[i], sizes[i]) if "size" in f.columns else lg.target_for(states[i])
                W[i, k] = t.get(trade, 0.0)
                G[i, k] = t.get(gold, 0.0) if gold else 0.0
                Cs[i, k] = t.get(cash, 0.0) if cash else 0.0
            st[:, k], sz[:, k] = states, np.nan_to_num(sizes)
        def rets(sym):
            if not sym:
                return np.zeros(n)
            x = md.daily_closed(sym, now)
            x = x[~x.index.duplicated(keep="last")]["c"].astype(float).reindex(idx).values
            return np.nan_to_num(np.r_[np.nan, x[1:] / x[:-1] - 1])     # a missing day counts as no change
        rt, rg, rc = rets(trade), rets(gold), rets(cash)
        years = np.array([d.year for d in pd.DatetimeIndex(idx).tz_convert("America/New_York")])
        yearly = p["rebalance_legs"] == "yearly"
        wts = self.weights()
        v = wts.copy()
        mix, mg, mc = np.zeros(n), np.zeros(n), np.zeros(n)
        for i in range(n):
            if i > 0:
                if years[i] != years[i - 1] or not yearly:
                    v = wts * v.sum()
                v = v * (1 + W[i - 1] * rt[i] + G[i - 1] * rg[i] + Cs[i - 1] * rc[i])
            mix[i], mg[i], mc[i] = (float((v * X[i]).sum() / v.sum()) for X in (W, G, Cs))
        held, hg, hc = mix.copy(), mg.copy(), mc.copy()
        for i in range(1, n):                                     # change only when a leg's target changes or a year starts
            if years[i] == years[i - 1] and (W[i] == W[i - 1]).all() and (G[i] == G[i - 1]).all() and (Cs[i] == Cs[i - 1]).all():
                held[i], hg[i], hc[i] = held[i - 1], hg[i - 1], hc[i - 1]
        state = np.array([""] * n, dtype=object)
        for i in range(n):
            row = list(st[i])
            state[i] = ("trend" if "trend" in row else "dip") if held[i] > 0.0005 else ("volatile" if "volatile" in row else "out")
        sig = md.daily_closed(p["signal"], now)
        sig = sig[~sig.index.duplicated(keep="last")].reindex(idx)
        fr = pd.DataFrame(index=idx)
        fr["o"], fr["h"], fr["l"], fr["c"] = sig["o"].values, sig["h"].values, sig["l"].values, sig["c"].values
        for k in range(K):
            fr[f"l{k + 1}_state"], fr[f"l{k + 1}_size"], fr[f"l{k + 1}_w"] = st[:, k], sz[:, k], W[:, k]
        fr["legs_in"] = (W > 0.0005).sum(axis=1)
        fr["size"] = np.round(held, 4)
        fr["gold_w"], fr["cash_w"] = np.round(hg, 4), np.round(hc, 4)
        fr["weight"] = fr["size"]
        fr["state"] = state
        self._targets = {pd.Timestamp(d).date(): self._target(fr["size"].iloc[i], fr["gold_w"].iloc[i], fr["cash_w"].iloc[i])
                         for i, d in enumerate(idx)}
        first = frs[0].reindex(idx)
        fr["sma_long"] = first["sma_long"].values if "sma_long" in first.columns else fr["c"].values
        fr["ma"] = fr["sma_long"]
        return fr

    def weight(self, state):
        return 1.0 if state in ("trend", "dip") else 0.0

    def cash_sym(self):
        return self.legs()[0].params.get("cash_symbol") or "" if self.legs() else ""

    def _target(self, w, g, c):
        t = {self.params["trade"]: round(float(w), 4)}
        if self.gold_sym():
            t[self.gold_sym()] = round(float(g), 4)
        if self.cash_sym():
            t[self.cash_sym()] = round(float(c), 4)
        return {k: v for k, v in t.items() if v > 0.0005}

    def hold_text(self, target):
        parts = [f"{v * 100:.0f}% {k}" for k, v in sorted(target.items(), key=lambda x: -x[1])]
        return (" + ".join(parts) + ", rest cash") if parts else "cash"

    def target_at(self, day, state=None, size=None):
        """The day's target from the last frame (the legs' targets, money-weighted): the backtest uses this, since the gold
        share depends on which legs are out and is not a function of the ETF share alone."""
        t = getattr(self, "_targets", {}).get(day)
        return t if t is not None else self.target_for(state, size)

    def target_for(self, state, size=None):
        """Fallback (no frame yet): size = the ETF's share (buffer already off); the rest parks like the legs, money-weighted."""
        buf = self.buffer()
        w = 0.0 if size is None else max(0.0, min(1.0 - buf, float(size)))
        park = self.parking()
        tot = sum(park.values())
        rest = max(0.0, (1 - buf) - w)
        return self._target(w, park.get(self.gold_sym(), 0.0) / (1 - buf) * rest if self.gold_sym() else 0.0,
                            park.get(self.cash_sym(), 0.0) / (1 - buf) * rest if self.cash_sym() and tot else 0.0)

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        return f"{h['kind']} · {self.name}\n{h['text']}\n{self.params['trade']} {h['from']} → {h['to']} of the money"

    def leg_word(self, state, w):
        return {"trend": f"in {w * 100:.0f}%", "dip": f"dip day {w * 100:.0f}%", "volatile": "held back", "out": "out"}.get(state, state or "—")

    def why(self, fr, i):
        parts = []
        for k, lg in enumerate(self.legs(), 1):
            a, z = fr[f"l{k}_state"].iloc[i - 1], fr[f"l{k}_state"].iloc[i]
            wa, wz = fr[f"l{k}_w"].iloc[i - 1], fr[f"l{k}_w"].iloc[i]
            if a != z or abs(wa - wz) > 0.0005:
                try:
                    reason = lg.why(lg.frame_cache, lg.frame_cache.index.get_loc(fr.index[i])) if hasattr(lg, "frame_cache") else ""
                except Exception:
                    reason = ""
                parts.append(f"{lg.name}: {self.leg_word(a, wa)} → {self.leg_word(z, wz)}" + (f" ({reason})" if reason else ""))
        head = f"{int(fr['legs_in'].iloc[i])} of {len(self.legs())} legs in"
        return head + (": " + "; ".join(parts) if parts else "")

    def evaluate(self, now):
        p = self.params
        legs = self.legs()
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        if fr.empty:
            return {"ok": False, "error": "Not enough history yet"}
        last = fr.iloc[-1]
        state, size = last["state"], float(last["size"])
        szv = fr["size"].values
        legsig = fr[[f"l{k}_w" for k in range(1, len(legs) + 1)]].values
        k0 = len(fr) - 1
        while k0 > 0 and (legsig[k0 - 1] == legsig[k0]).all():
            k0 -= 1
        hist, sts = [], fr["state"].values
        for i in range(max(1, len(fr) - 1500), len(fr)):
            if not (legsig[i] == legsig[i - 1]).all():
                up = szv[i] > szv[i - 1] + 1e-9
                hist.append({"t": self.close_ts(fr.index[i]), "kind": "BUY" if up else "SELL", "from": f"{szv[i - 1] * 100:.0f}%",
                             "to": f"{szv[i] * 100:.0f}%", "price": float(fr["c"].iloc[i]), "text": self.why(fr, i)})
        target = self.target_at(pd.Timestamp(fr.index[-1]).date(), state, size)
        checks, tiles = [], []
        for k, lg in enumerate(legs, 1):
            ev = lg.evaluate(now)
            w = float(last[f"l{k}_w"])
            checks.append({"k": f"Leg {k} · {lg.name}", "v": f"{ev.get('label', '—')}", "cls": "up" if w > 0.0005 else "",
                           "h": (lg.describe() or {}).get("rule", "")})
            for c in (ev.get("checks") or [])[:4]:
                checks.append({**c, "k": f"  {k} · {c['k']}"})
            tiles.append({"k": f"leg{k}", "title": f"Leg {k} · {lg.name}", "text": (lg.describe() or {}).get("rule", ""),
                          "hold": f"{self.leg_share(k - 1)} of the money · now {self.leg_word(last[f'l{k}_state'], w)}", "color": LEG_COLORS[(k - 1) % 4]})
        checks.append({"k": "Size", "v": f"{size * 100:.0f}% {p['trade']} · {int(last['legs_in'])} of {len(legs)} legs in",
                       "h": "Each leg is an equal part of the money, set back to equal " + ("each January" if p["rebalance_legs"] == "yearly" else "every day")})
        log_rows = []
        for i in range(len(fr) - 1, max(len(fr) - 31, 0), -1):
            r = fr.iloc[i]
            ch = i > 0 and not (legsig[i] == legsig[i - 1]).all()
            a0, a1 = (szv[i - 1] if i > 0 else szv[i]), szv[i]
            act = "no trade" if not ch else (f"buy to {a1 * 100:.0f}% {p['trade']} next open" if a1 > a0 else f"sell to {a1 * 100:.0f}% {p['trade']} next open")
            row = {"date": str(fr.index[i].date()), "close": float(r["c"]), "size": float(r["size"]) * 100, "legs": int(r["legs_in"]),
                   "state": r["state"], "action": act, "changed": bool(ch), "from": sts[i - 1] if i > 0 else None}
            for k in range(1, len(legs) + 1):
                row[f"l{k}"] = self.leg_word(r[f"l{k}_state"], float(r[f"l{k}_w"]))
            log_rows.append(row)
        log_cols = ([{"k": "close", "label": p["signal"], "fmt": "n2"}]
                    + [{"k": f"l{k}", "label": f"Leg {k}", "fmt": "text"} for k in range(1, len(legs) + 1)]
                    + [{"k": "legs", "label": "Legs in", "fmt": "n0"}, {"k": "size", "label": "Size %", "fmt": "n0"}])
        nin = int(last["legs_in"])
        label = (f"IN · {size * 100:.0f}% {p['trade']} ({nin} of {len(legs)} legs)" if size > 0.0005 else
                 "OUT · " + self.hold_text(target) + (" (held back)" if state == "volatile" else ""))
        return {"ok": True, "state": state, "label": label, "target": target,
                "bar_time": self.close_ts(fr.index[-1]), "signal_time": self.close_ts(fr.index[k0]), "price": float(last["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[-1].date()), "tiles": tiles, "log": log_rows, "log_cols": log_cols, "checks": checks,
                           "close": float(last["c"]), "sma_long": float(last["sma_long"]), "state_text": STATE_TEXT[state], "size": size,
                           "legs_in": nin, "title": "Position · decided after each US close"}}

    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now).iloc[-RANGE_DAYS.get(rng, 168):]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(col, digits=4, mult=1.0):
            v = fr[col].values.astype(float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(fr))]
        legs = self.legs()
        lw = fr[[f"l{k}_w" for k in range(1, len(legs) + 1)]].values
        sz, stv = fr["size"].values, fr["state"].values
        markers = []
        for i in range(1, len(fr)):
            if (lw[i] == lw[i - 1]).all():
                continue
            b = sz[i] > sz[i - 1] + 1e-9
            markers.append({"time": t[i], "position": "belowBar" if b else "aboveBar", "color": "#2962FF" if b else "#E040FB",
                            "shape": "arrowUp" if b else "arrowDown", "text": f"{'Buy' if b else 'Sell'} → {sz[i] * 100:.0f}%"})
        panes = [{"id": "legs", "title": "Each leg's share in " + p["trade"] + " (%)", "height": 110, "step": True,
                  "lines": [{"name": lg.name, "color": LEG_COLORS[k % 4], "width": 2, "data": ln(f"l{k + 1}_w", 1, 100)} for k, lg in enumerate(legs)],
                  "hlines": []},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 80, "step": True,
                  "lines": [{"name": "Size", "color": self.color, "width": 2, "area": True, "data": ln("size", 1, 100)}], "hlines": []}]
        sig = {"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Signal — open a leg's own chart in its settings to see its rules",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": [], "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(stv)],
               "panes": panes, "markers": markers, "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])}
        return {"charts": [sig], "states": STATE_COLOR}

    def share_word(self):
        if not self.equal():
            return " / ".join(self.leg_share(k) for k in range(len(self.legs())))
        return {2: "half", 3: "a third", 4: "a quarter"}.get(len(self.legs()), "an equal part")

    def describe(self):
        p = self.params
        legs = self.legs()
        share = self.share_word()
        each = f"{share} each" if self.equal() else share
        rules = [f"The money is split into {len(legs)} legs, {each}; each leg follows its own strategy and holds {p['trade']}, "
                 f"{self.park_text()} by its own rules:"]
        for k, lg in enumerate(legs, 1):
            rules.append(f"Leg {k} · {lg.name}: {(lg.describe() or {}).get('rule', '')}")
        rules += [f"The target is the legs' targets weighted by each leg's value, so {p['trade']} moves in steps of about "
                  + (f"{share} of the money" if self.equal() else "each leg's share") + " as legs go in and out.",
                  "The legs are set back to " + ("equal " if self.equal() else f"{share} ") + ("on the first trading day of each year." if p["rebalance_legs"] == "yearly" else "every day."),
                  "Orders start at the next market open, split into lots."]
        return {"rules": rules, "flow": f"{len(legs)} legs on {p['signal']} → {p['trade']} · {self.park_text()}",
                "tv": " · ".join(f"leg {k}: {(lg.describe() or {}).get('tv', '')}" for k, lg in enumerate(legs, 1)),
                "rule": f"{each}: " + " | ".join(lg.name for lg in legs) + f" → {p['trade']}, else {self.park_text()}"}

    def check_table(self, now, rows=12):
        """Each leg's own recompute (where its type has one) plus the mix's size rebuilt from the legs' targets."""
        fr = self.frame(now)
        fr = fr[fr["state"] != ""]
        bad = 0.0
        for lg in self.legs():
            if hasattr(lg, "check_table"):
                try:
                    _c, _r, w = lg.check_table(now, rows)
                    bad = max(bad, float(w or 0))
                except Exception:
                    bad = max(bad, 1.0)
        out = []
        for day in fr.index[-rows:]:
            r = fr.loc[day]
            ws = [float(r[f"l{k}_w"]) for k in range(1, len(self.legs()) + 1)]
            ok = (r["size"] > 0.0005) == (max(ws) > 0.0005) and bad < 1e-6
            out.append({"t": int(pd.Timestamp(day).timestamp()), "vals": [round(float(r["c"]), 2)] + [round(w * 100) for w in ws]
                        + [round(float(r["size"]) * 100), r["state"]], "ok": bool(ok)})
        cols = ["Close"] + [f"Leg {k} %" for k in range(1, len(self.legs()) + 1)] + ["Mix %", "State"]
        return cols, out, float(sum(0 if r["ok"] else 1 for r in out)) + bad
