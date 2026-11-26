"""Trend + Hang Seng crash buys (CWEB, 2x China internet). Research "CWEB (2x China internet): best buy/sell rules"
(26 Nov 2026), Pick 4+ (round 3 Pick 4 plus the round-4 trend trailing stop).

Three parts; the strategy holds the LARGEST of them, otherwise cash.
  Trend      decided after each US close, traded at the next open.
             KWEB Donchian: on at a close above the highest high of the prior `don_entry` days, off at a close below the lowest
             low of the prior `don_exit` days; AND FXI above its SMA(gate_ma). Size = target_vol ÷ CWEB's 20-day volatility
             (daily % changes, × √252), at most 100%; resized only on a move of size_band points.
             Trailing stop (trail_pct, 0 = off): from the first day of a trend run, track CWEB's highest close; a close
             trail_pct below it ends the trend part until the trend signal turns off and on again.
  Big crash  the Hang Seng closes big_drop_pct or more down (Hong Kong closes at 15:00 Bangkok, before the US open the same
             day): 100% CWEB at that day's US open. At the next open: sold if CWEB opens tp_pct or more above that day's open
             (the buy), otherwise held one more day and sold at the open two trading days after the buy.
  Small crash the Hang Seng closes between small_drop_pct and big_drop_pct down: a day limit buy for small_size_pct at
             small_limit_pct below CWEB's previous close (the order rests all day, it is not re-priced); a fill is sold at
             the next open.
The Hang Seng's move counts for the US session of the same calendar date (a day the US market is closed it does nothing).

One walk over the days (walk) gives every session's parts; the live target, the history, the chart and the backtest all
read it, so the backtest trades exactly what the bot trades.
"""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import marketdata as md
from .. import markethours as mh
from .base import register
from .regime import NY, RANGE_DAYS, TV, RegimeStrategy, tv_url  # noqa: F401

HKT = ZoneInfo("Asia/Hong_Kong")
HK_FINAL = dtime(16, 15)          # the Hang Seng's close is final after the closing auction (16:00–16:10 Hong Kong)
SYNTH_UNTIL = date(2018, 1, 2)    # research: CWEB traded too thinly before 2018; earlier prices = 2 × KWEB minus a drag
SYNTH_DRAG_Y = 0.053              # fitted on 2018–2026 in the research
STATE_COLOR = {"crash": "#EF5350", "small": "#F5C76B", "trend": "#26A69A", "stopped": "#8E3B46", "out": "#4A5263"}
STATE_TEXT = {"crash": "Hang Seng crash buy", "small": "small-crash buy (one day)", "trend": "trend on",
              "stopped": "trend on, trailing stop hit", "out": "out · cash"}
TV.update({"CWEB": "AMEX:CWEB", "KWEB": "AMEX:KWEB", "FXI": "AMEX:FXI", "^HSI": "HSI:HSI"})


def hk_close_ts(d) -> int:
    """When the Hang Seng's daily bar of date d is final (Hong Kong time 16:15)."""
    return int(datetime.combine(pd.Timestamp(d).date(), HK_FINAL, HKT).timestamp())


def hk_closed(hs: pd.DataFrame, now) -> pd.DataFrame:
    """Hang Seng daily bars whose close is final at `now`."""
    if hs is None or hs.empty:
        return hs
    today = pd.Timestamp(now.astimezone(HKT).date()).tz_localize("UTC")
    hs = hs[hs.index <= today]
    if len(hs) and hs.index[-1] == today and now.timestamp() < hk_close_ts(today):
        hs = hs.iloc[:-1]                                  # today's Hong Kong session is not final yet
    return hs


def synth_cweb(cw: pd.DataFrame, kw: pd.DataFrame, until=SYNTH_UNTIL, drag=SYNTH_DRAG_Y) -> pd.DataFrame:
    """CWEB's daily bars with the days before `until` built from KWEB: each day 2 × KWEB's move (open, high, low and close
    measured from KWEB's previous close) minus the drag, joined to CWEB's real close on `until`."""
    if cw is None or cw.empty or kw is None or kw.empty:
        return cw
    u = pd.Timestamp(until).tz_localize("UTC")
    if u not in cw.index or u not in kw.index or kw.index[0] >= u:
        return cw
    k = kw[kw.index <= u]
    kc = k["c"].astype(float).values
    n = len(k)
    o, h, l, c = (np.empty(n) for _ in range(4))
    c[0] = o[0] = h[0] = l[0] = 100.0
    for i in range(1, n):
        p = kc[i - 1]
        o[i] = c[i - 1] * (1 + 2 * (float(k["o"].iloc[i]) / p - 1))
        h[i] = c[i - 1] * (1 + 2 * (float(k["h"].iloc[i]) / p - 1))
        l[i] = c[i - 1] * (1 + 2 * (float(k["l"].iloc[i]) / p - 1))
        c[i] = c[i - 1] * (1 + 2 * (kc[i] / p - 1) - drag / 252)
    f = float(cw.loc[u, "c"]) / c[-1]
    early = pd.DataFrame({"o": o * f, "h": np.maximum(h, np.maximum(o, c)) * f, "l": np.minimum(l, np.minimum(o, c)) * f,
                          "c": c * f, "v": 0.0}, index=k.index)
    return pd.concat([early[early.index < u], cw[cw.index >= u]])


def signals(cw, kw, fx, hs, p) -> pd.DataFrame:
    """One row per US session (CWEB's days): CWEB's bar, the trend part decided at that day's close, and the Hang Seng's move
    that counts for that session. hs: Hang Seng closes (HK dates); a session with no Hang Seng bar of its date has no move."""
    idx = cw.index
    kwr = kw.reindex(idx)
    fxc = fx["c"].astype(float)
    fma = fxc.rolling(int(p["gate_ma"])).mean()
    ne, nx = int(p["don_entry"]), int(p["don_exit"])
    hi = kw["h"].astype(float).rolling(ne).max().shift(1).reindex(idx)
    lo = kw["l"].astype(float).rolling(nx).min().shift(1).reindex(idx)
    c = cw["c"].astype(float)
    vol = c.pct_change(fill_method=None).rolling(int(p["vol_days"])).std() * np.sqrt(252)
    hsc = hs["c"].astype(float) if hs is not None and not hs.empty else pd.Series(dtype=float)
    hret = (hsc / hsc.shift(1) - 1).reindex(idx)
    fr = pd.DataFrame(index=idx)
    for k in ("o", "h", "l", "c"):
        fr[k] = cw[k].astype(float).values
    fr["kc"] = kwr["c"].astype(float).values
    fr["hi"], fr["lo"] = hi.values, lo.values
    fr["fxc"] = fxc.reindex(idx).values
    fr["fxma"] = fma.reindex(idx).values
    fr["vol"] = vol.values
    fr["hs_ret"] = hret.values
    fr["hs_c"] = hsc.reindex(idx).values
    trail, band = float(p["trail_pct"]) / 100, float(p["size_band_pct"]) / 100
    kvol = float(p["target_vol_pct"]) / 100
    n = len(fr)
    don_a, on_a, raw_a, stop_a, peak_a, tw_a, ok_a = (np.zeros(n, dtype=bool), np.zeros(n, dtype=bool), np.zeros(n, dtype=bool),
                                                       np.zeros(n, dtype=bool), np.full(n, np.nan), np.zeros(n), np.zeros(n, dtype=bool))
    don, peak, stopped, held = False, np.nan, False, 0.0
    kc, hv, lv, fc, fm, cv, vv = (fr[k].values for k in ("kc", "hi", "lo", "fxc", "fxma", "c", "vol"))
    for i in range(n):
        ok = not (np.isnan(hv[i]) or np.isnan(lv[i]) or np.isnan(fm[i]) or np.isnan(vv[i]) or np.isnan(kc[i]))
        ok_a[i] = ok
        if not ok:
            continue
        if not don and kc[i] > hv[i]:
            don = True
        elif don and kc[i] < lv[i]:
            don = False
        raw = don and fc[i] > fm[i]
        on = raw
        if raw:
            if trail > 0:
                peak = cv[i] if np.isnan(peak) else max(peak, cv[i])
                if not stopped and cv[i] <= peak * (1 - trail):
                    stopped = True
            if stopped:
                on = False
        else:
            peak, stopped = np.nan, False
        want = min(1.0, kvol / vv[i]) if on and vv[i] > 0 else 0.0
        if want == 0 or held == 0 or abs(want - held) >= band - 1e-12:
            held = want
        don_a[i], raw_a[i], on_a[i], stop_a[i], peak_a[i], tw_a[i] = don, raw, on, stopped, peak, held
    fr["don"], fr["raw"], fr["on"], fr["stopped"], fr["peak"], fr["tw"], fr["ok"] = don_a, raw_a, on_a, stop_a, peak_a, tw_a, ok_a
    return fr


def walk(fr: pd.DataFrame, p) -> pd.DataFrame:
    """Each session's parts, in the order the day happens:
      trend     the trend weight decided at the previous close
      tp        the big-crash buy of the previous session was sold at this open (opened tp_pct above the buy)
      big       a big-crash buy is held during this session (bought at this open, or kept from the previous one)
      big_new   the Hang Seng crash of this date: bought at this open
      open_w    weight from this open (the largest part)
      small     a small-crash limit buy rests today (limit = previous close × (1 − small_limit_pct))
      fill      it filled (the day's low reached the limit while the weight was below small_size) at fill_px
      w         weight held at this close
    An open price of NaN (today, before the open) leaves the take-profit undecided (tp_wait): the buy is kept for now."""
    n = len(fr)
    tp, big_d, small_d = float(p["tp_pct"]) / 100, -float(p["big_drop_pct"]) / 100, -float(p["small_drop_pct"]) / 100
    ssz, lim = float(p["small_size_pct"]) / 100, float(p["small_limit_pct"]) / 100
    o, l, c, g, tw = (fr[k].values.astype(float) for k in ("o", "l", "c", "hs_ret", "tw"))
    cols = {k: np.zeros(n) for k in ("trend", "open_w", "w", "fill_px", "limit", "buy_open")}
    flags = {k: np.zeros(n, dtype=bool) for k in ("tp", "tp_wait", "big", "big_new", "small", "fill")}
    left, buy = 0, np.nan
    for i in range(n):
        cols["trend"][i] = tw[i - 1] if i > 0 else 0.0
        if left:
            if left == 2 and tp > 0 and np.isnan(o[i]):
                flags["tp_wait"][i] = True
                left = 1
            elif left == 2 and tp > 0 and o[i] >= buy * (1 + tp):
                left = 0
                flags["tp"][i] = True
            else:
                left -= 1
        gi = g[i]
        if not np.isnan(gi) and gi <= big_d + 1e-12:
            left, buy = 2, o[i]
            flags["big_new"][i] = True
        flags["big"][i] = left > 0
        cols["buy_open"][i] = buy if left else np.nan
        ow = max(cols["trend"][i], 1.0 if left else 0.0)
        cols["open_w"][i] = ow
        w = ow
        if not np.isnan(gi) and big_d < gi <= small_d + 1e-12 and i > 0 and ssz > 0:
            flags["small"][i] = True
            cols["limit"][i] = c[i - 1] * (1 - lim)
            if ow < ssz and not np.isnan(l[i]) and l[i] <= cols["limit"][i]:
                flags["fill"][i] = True
                cols["fill_px"][i] = min(o[i], cols["limit"][i])
                w = ssz
        cols["w"][i] = w
    out = pd.DataFrame(index=fr.index)
    for k, v in {**cols, **flags}.items():
        out[k] = v
    out["state"] = np.where(out["big"], "crash", np.where(out["fill"], "small",
                            np.where(out["trend"] > 0, "trend", np.where(fr["stopped"].shift(1, fill_value=False).values & fr["raw"].shift(1, fill_value=False).values, "stopped", "out"))))
    return out


@register
class HkCrashStrategy(RegimeStrategy):
    type = "hk_crash"
    label = "Trend + Hang Seng crash buys (China internet 2x)"
    family = "regime"
    timeframe = "1D"
    description = ("Daily: holds CWEB while KWEB breaks out (Donchian) and FXI is above its 200-day average, sized by volatility "
                   "with a trailing stop; buys 100% at the US open after a Hang Seng close 3% or more down (take-profit at the "
                   "next open, else sold two days later); a one-day limit buy after a smaller Hang Seng drop.")
    EXEC_DEFAULTS = {"start_mode": "asap", "interval_min": 1, "lots": 5, "exit_mode": "asap"}
    PARAMS = [
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "CWEB", "group": "Symbols",
         "help": "2x China internet ETF (its own volatility sizes the trend part)"},
        {"key": "signal", "label": "Breakout read from", "kind": "symbol", "default": "KWEB", "group": "Symbols"},
        {"key": "gate", "label": "Trend gate", "kind": "symbol", "default": "FXI", "group": "Symbols",
         "help": "The trend part needs this ETF above its average"},
        {"key": "hk_index", "label": "Crash index", "kind": "text", "default": "^HSI", "group": "Symbols",
         "help": "Hang Seng (Yahoo ^HSI); its close is known at 15:00 Bangkok, before the US open"},
        {"key": "don_entry", "label": "Breakout: close above the high of (days)", "kind": "int", "default": 20, "min": 5, "max": 100,
         "group": "Trend"},
        {"key": "don_exit", "label": "Off: close below the low of (days)", "kind": "int", "default": 15, "min": 3, "max": 100, "group": "Trend"},
        {"key": "gate_ma", "label": "Gate average (days)", "kind": "int", "default": 200, "min": 20, "max": 400, "group": "Trend"},
        {"key": "target_vol_pct", "label": "Size: volatility target (%)", "kind": "float", "default": 30.0, "min": 5, "max": 200,
         "group": "Trend", "help": "Trend size = this ÷ CWEB's 20-day volatility (a year), at most 100%"},
        {"key": "vol_days", "label": "Volatility over (days)", "kind": "int", "default": 20, "min": 5, "max": 100, "group": "Trend"},
        {"key": "size_band_pct", "label": "Resize on a move of (points)", "kind": "float", "default": 20.0, "min": 1, "max": 100, "group": "Trend"},
        {"key": "trail_pct", "label": "Trailing stop (% below the run's high, 0 = off)", "kind": "float", "default": 15.0, "min": 0,
         "max": 60, "group": "Trend", "help": "Trend part only; back in when the trend signal turns off and on again"},
        {"key": "big_drop_pct", "label": "Big crash: Hang Seng down at least (%)", "kind": "float", "default": 3.0, "min": 0.5, "max": 15,
         "group": "Crash buys"},
        {"key": "tp_pct", "label": "Take-profit at the next open (% above the buy, 0 = off)", "kind": "float", "default": 4.0, "min": 0,
         "max": 30, "group": "Crash buys", "help": "Otherwise the big-crash buy is sold at the open two trading days later"},
        {"key": "small_drop_pct", "label": "Small crash: Hang Seng down at least (%)", "kind": "float", "default": 1.75, "min": 0.25,
         "max": 15, "group": "Crash buys", "help": "Up to the big-crash level"},
        {"key": "small_size_pct", "label": "Small crash: buy (% of the money, 0 = off)", "kind": "float", "default": 40.0, "min": 0,
         "max": 100, "group": "Crash buys"},
        {"key": "small_limit_pct", "label": "Small crash: limit below the previous close (%)", "kind": "float", "default": 1.0, "min": 0,
         "max": 10, "group": "Crash buys"},
        {"key": "cash_buffer_pct", "label": "Cash buffer %", "kind": "float", "default": 1.0, "min": 0, "max": 20, "group": "Money"},
        {"key": "rebalance_band_pct", "label": "Rebalance band %", "kind": "float", "default": 5.0, "min": 1, "max": 50, "group": "Money",
         "help": "Between signals, trade back to the target when the holding drifts this far from it (the research kept the "
                 "trend part at its size every day; 5 points gives the same result with fewer trades)"},
    ]

    # ---------------------------------------------------------------- symbols
    def read_symbols(self):
        p = self.params
        return list(dict.fromkeys([p["trade"], p["signal"], p["gate"]]))

    def data_needs(self):
        return [(s, "1d") for s in self.read_symbols() + [self.params["hk_index"]]]

    def history_symbols(self):
        return self.read_symbols() + [self.params["hk_index"]]

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

    # ---------------------------------------------------------------- the days
    @staticmethod
    def dividend_adjusted(sym, df):
        """Daily bars with dividends added back, as in the research: each day scaled by Yahoo's total-return close ÷ its
        plain close (KWEB and FXI pay a dividend each December; on plain prices that drop looks like a fall, which moves the
        breakout and the 200-day average). Days newer than the stored total-return bars keep the latest factor; the
        total-return bars are downloaded again when they miss the last closed day (at most every 30 minutes)."""
        from .. import backtest as BT
        if df is None or df.empty:
            return df
        try:
            tr = BT._raw_tr(sym)
            if tr is not None and not tr.empty and tr.index[-1] < df.index[-1] and md.source() != "csv":
                k = f"hkx_tr_try:{sym}"
                import time as _t
                from .. import db
                if _t.time() - (db.get_state(k) or 0) > 1800:
                    db.set_state(k, int(_t.time()))
                    db.set_state(f"bt_upd:{sym}:1dtr", 0)          # stale: download again
                    tr = BT._raw_tr(sym)
        except Exception:
            tr = None
        if tr is None or tr.empty:
            return df
        f = (tr["c"].astype(float) / df["c"].astype(float).reindex(tr.index)).reindex(df.index)
        f = f.replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(1.0)
        out = df.copy()
        for k in ("o", "h", "l", "c"):
            out[k] = df[k].astype(float) * f
        return out

    def inputs(self, now, synth=False):
        p = self.params
        d = {}
        for s in self.read_symbols():
            df = md.daily_closed(s, now)
            if df is None or df.empty:
                raise md.DataError(f"No daily bars of {s}")
            d[s] = self.dividend_adjusted(s, df[~df.index.duplicated(keep="last")])
        hs = md.load(p["hk_index"], "1d")
        hs = hs[~hs.index.duplicated(keep="last")] if hs is not None and not hs.empty else hs
        if hs is None or hs.empty:
            raise md.DataError(f"No daily bars of the Hang Seng ({p['hk_index']})")
        hs = hk_closed(hs, now)
        cw = d[p["trade"]]
        if synth:
            cw = synth_cweb(cw, d[p["signal"]])
        return cw, d[p["signal"]], d[p["gate"]], hs

    def next_session(self, last_day, now) -> date | None:
        d = pd.Timestamp(last_day).date() + timedelta(days=1)
        for _ in range(10):
            if mh.is_trading_day(d):
                return d
            d += timedelta(days=1)
        return None

    def frame(self, now, synth=False, live=True) -> pd.DataFrame:
        """signals() over the closed US days, plus (live) a row for the next session: its Hang Seng move once Hong Kong has
        closed that date, and its open once the US session has started."""
        p = self.params
        cw, kw, fx, hs = self.inputs(now, synth)
        if live:
            nxt = self.next_session(cw.index[-1], now)
            if nxt is not None:
                t = pd.Timestamp(nxt).tz_localize("UTC")
                o = np.nan
                b = mh.session_bounds(nxt)
                if b and now >= b[0] + timedelta(seconds=60) and now.astimezone(NY).date() == nxt:
                    bar = md.today_bar(p["trade"])
                    if bar and bar.get("open"):
                        o = float(bar["open"])
                cw = pd.concat([cw, pd.DataFrame({"o": [o], "h": [np.nan], "l": [np.nan], "c": [np.nan], "v": [0.0]}, index=[t])])
        fr = signals(cw, kw, fx, hs, p)
        if len(fr) < 30 or not fr["ok"].any():
            raise md.DataError(f"Need {int(p['gate_ma']) + 2} daily bars of {p['gate']} and {int(p['don_entry']) + 2} of {p['signal']}")
        return fr

    # ---------------------------------------------------------------- live
    def target_w(self, w) -> dict:
        w = float(w)
        return {self.params["trade"]: round(min(w, 1.0) * (1 - self.buffer()), 4)} if w > 1e-9 else {}

    def target_for(self, state, size=None):
        return self.target_w(size if size is not None else (1.0 if state in ("crash",) else 0.0))

    def is_buy_signal(self, sig: dict) -> bool:
        return sig.get("kind") == "BUY"

    def signal_message(self, h):
        return f"{h['kind']} · {self.name}\n{h['text']}"

    def _events(self, fr, W, upto):
        """Decisions as they happen: at a US close (trend, end of a crash buy), at the Hang Seng's close (crash buys), at an
        open (take-profit). Weight = what the strategy wants from the next trade on."""
        p = self.params
        ev, cur = [], 0.0
        idx = fr.index
        for i in range(1, upto):
            d = idx[i]
            # Hong Kong closed: crash buy for today's open / small-crash limit for today
            if W["big_new"].iloc[i]:
                want = W["open_w"].iloc[i]
                ev.append({"t": hk_close_ts(d), "kind": "BUY", "w": want, "state": "crash",
                           "text": f"Hang Seng closed {fr['hs_ret'].iloc[i] * 100:+.2f}% (≤ −{p['big_drop_pct']:g}%): buy 100% {p['trade']} at "
                                   f"today's US open"})
                cur = want
            elif W["small"].iloc[i] and W["open_w"].iloc[i] < float(p["small_size_pct"]) / 100:
                ev.append({"t": hk_close_ts(d), "kind": "LIMIT", "w": cur, "state": "small",
                           "text": f"Hang Seng closed {fr['hs_ret'].iloc[i] * 100:+.2f}%: limit buy {p['small_size_pct']:g}% {p['trade']} at "
                                   f"${W['limit'].iloc[i]:,.2f} (1% under the previous close), today only"})
            if W["tp"].iloc[i]:
                want = W["open_w"].iloc[i]
                b = mh.session_bounds(d.date())
                ev.append({"t": int(b[0].timestamp()) + 60 if b else hk_close_ts(d), "kind": "SELL", "w": want, "state": "trend" if want else "out",
                           "text": f"Take-profit: {p['trade']} opened {(fr['o'].iloc[i] / W['buy_open'].iloc[i - 1] - 1) * 100:+.1f}% above the "
                                   f"crash buy (≥ {p['tp_pct']:g}%): sell the crash part now"})
                cur = want
            if W["fill"].iloc[i]:
                cur = W["w"].iloc[i]
            # the US close: the weight wanted from the next open
            if i + 1 < len(fr):
                carry = 1.0 if W["big_new"].iloc[i] else 0.0      # a crash bought today is kept at least to the next open
                want = max(fr["tw"].iloc[i], carry)
                if abs(want - cur) > 1e-9 and fr["ok"].iloc[i]:
                    kind = "BUY" if want > cur else "SELL"
                    ev.append({"t": self.close_ts(d), "kind": kind, "w": want, "state": self._state_of(fr, i, want),
                               "text": self.close_why(fr, W, i, cur, want)})
                    cur = want
        return ev

    def _state_of(self, fr, i, want):
        if want <= 0:
            return "stopped" if fr["raw"].iloc[i] and fr["stopped"].iloc[i] else "out"
        return "trend" if fr["tw"].iloc[i] >= want - 1e-9 else "crash"

    def close_why(self, fr, W, i, cur, want):
        p = self.params
        r, a = fr.iloc[i], fr.iloc[i - 1]
        bits = []
        if r["tw"] != a["tw"]:
            if r["tw"] > 0 and a["tw"] == 0:
                bits.append(f"trend on: {p['signal']} {r['kc']:,.2f} above its {p['don_entry']}-day high {r['hi']:,.2f} and {p['gate']} "
                            f"above SMA{p['gate_ma']} · size {r['tw'] * 100:.0f}% ({p['target_vol_pct']:g}% ÷ volatility {r['vol'] * 100:.0f}%)")
            elif r["tw"] == 0 and r["raw"] and r["stopped"]:
                bits.append(f"trailing stop: {p['trade']} {r['c']:,.2f} is {p['trail_pct']:g}% or more below the run's high {r['peak']:,.2f}")
            elif r["tw"] == 0 and not r["don"]:
                bits.append(f"trend off: {p['signal']} {r['kc']:,.2f} below its {p['don_exit']}-day low {r['lo']:,.2f}")
            elif r["tw"] == 0:
                bits.append(f"trend off: {p['gate']} {r['fxc']:,.2f} below SMA{p['gate_ma']} {r['fxma']:,.2f}")
            else:
                bits.append(f"trend resized to {r['tw'] * 100:.0f}% (volatility {r['vol'] * 100:.0f}%)")
        trend = " · from the next open" if bits else ""
        if W["big"].iloc[i] and not W["big_new"].iloc[i]:
            bits.append("crash buy held 2 days: sold at the next open")
        if W["fill"].iloc[i]:
            bits.append("small-crash buy sold at the next open")
        return ("; ".join(bits) or f"weight {cur * 100:.0f}% → {want * 100:.0f}% from the next open") + (trend if len(bits) == 1 else "")

    def evaluate(self, now):
        p = self.params
        fr = self.frame(now)
        W = walk(fr, p)
        n = len(fr)
        live = n - 1                                        # the next (or running) session
        last = n - 2                                        # the last closed US day
        ok = fr["ok"].values
        if not ok[last]:
            return {"ok": False, "error": "Not enough history yet"}
        r, wl = fr.iloc[last], W.iloc[live]
        hk_known = not np.isnan(fr["hs_ret"].iloc[live])
        ssz = float(p["small_size_pct"]) / 100
        want = float(wl["open_w"])
        rest = None
        nxt = fr.index[live].date()
        b = mh.session_bounds(nxt)
        if wl["small"] and want < ssz:
            want = ssz
            if b:
                rest = {p["trade"]: {"limit": round(float(wl["limit"]), 2), "until": int(b[1].timestamp()),
                                     "why": f"Hang Seng {fr['hs_ret'].iloc[live] * 100:+.2f}%: small-crash limit buy"}}
        target = self.target_w(want)
        if wl["big"]:
            state = "crash"
        elif wl["small"] and rest:
            state = "small"
        elif wl["trend"] > 0:
            state = "trend"
        elif r["raw"] and r["stopped"]:
            state = "stopped"
        else:
            state = "out"
        evs = self._events(fr, W, n)
        hist, prev_state = [], "out"
        for e in evs:
            hist.append({"t": e["t"], "kind": e["kind"] if e["kind"] != "LIMIT" else "BUY", "from": prev_state, "to": e["state"], "price": None,
                         "text": e["text"]})
            prev_state = e["state"]
        hist = hist[-400:]
        prev_t = [e["t"] for e in evs]
        bar_time = self.close_ts(fr.index[last])
        if hk_known:
            bar_time = max(bar_time, hk_close_ts(fr.index[live]))
        if wl["tp"]:
            bar_time = max(bar_time, int(b[0].timestamp()) + 60 if b else bar_time)
        sig_t = max([t for t in prev_t if t <= bar_time] or [bar_time])
        when = f"{nxt:%a %d %b}"
        hs_txt = (f"{fr['hs_ret'].iloc[live] * 100:+.2f}% ({fr['hs_c'].iloc[live]:,.0f})" if hk_known
                  else "not closed yet (Hong Kong closes 15:00 Bangkok)")
        tw = float(r["tw"])
        checks = [
            {"k": f"{p['signal']} breakout", "v": f"{'on' if r['don'] else 'off'} · close {r['kc']:,.2f} · {p['don_entry']}-day high {r['hi']:,.2f} · "
             f"{p['don_exit']}-day low {r['lo']:,.2f}", "cls": "up" if r["don"] else "dn",
             "h": f"On at a close above the {p['don_entry']}-day high, off at a close below the {p['don_exit']}-day low"},
            {"k": f"{p['gate']} vs SMA{p['gate_ma']}", "v": f"{r['fxc']:,.2f} vs {r['fxma']:,.2f} · {(r['fxc'] / r['fxma'] - 1) * 100:+.1f}%",
             "cls": "up" if r["fxc"] > r["fxma"] else "dn", "h": "The trend part needs it above"},
            {"k": f"Size · {p['trade']} {p['vol_days']}-day volatility", "v": f"{r['vol'] * 100:.0f}% a year → trend size {tw * 100:.0f}%",
             "h": f"min(100%, {p['target_vol_pct']:g}% ÷ volatility); resized only on a move of {p['size_band_pct']:g} points"}]
        if float(p["trail_pct"]) > 0:
            if r["raw"]:
                checks.append({"k": "Trailing stop", "v": ("hit · out until the trend turns off and on again" if r["stopped"] else
                                                           f"high {r['peak']:,.2f} · stop at {r['peak'] * (1 - float(p['trail_pct']) / 100):,.2f}"),
                               "cls": "dn" if r["stopped"] else "", "h": f"A close {p['trail_pct']:g}% below the run's highest close ends the trend part"})
            else:
                checks.append({"k": "Trailing stop", "v": "not armed (trend off)", "h": f"{p['trail_pct']:g}% below the highest close of a trend run"})
        checks.append({"k": f"Hang Seng · {when}", "v": hs_txt,
                       "cls": "dn" if hk_known and fr["hs_ret"].iloc[live] <= -float(p["small_drop_pct"]) / 100 else "",
                       "h": f"≤ −{p['big_drop_pct']:g}%: buy 100% at the US open; −{p['small_drop_pct']:g}% to −{p['big_drop_pct']:g}%: "
                            f"limit buy {p['small_size_pct']:g}% at 1% under the previous close"})
        if wl["big"]:
            bo = W["buy_open"].iloc[live]
            if wl["big_new"]:
                txt = f"buy 100% at the open of {when}"
            elif wl["tp_wait"]:
                txt = (f"bought at {W['buy_open'].iloc[last]:,.2f}: sold at the open if it opens at or above "
                       f"{W['buy_open'].iloc[last] * (1 + float(p['tp_pct']) / 100):,.2f}, else at the next open")
            else:
                txt = f"held today (bought at {bo:,.2f}); sold at the next open"
            checks.append({"k": "Crash buy", "v": txt, "cls": "warn"})
        elif wl["tp"]:
            checks.append({"k": "Crash buy", "v": f"take-profit: opened {fr['o'].iloc[live]:,.2f}, sold at this open", "cls": "up"})
        if rest:
            checks.append({"k": "Small-crash limit", "v": f"buy {p['small_size_pct']:g}% at ${rest[p['trade']]['limit']:,.2f}, {when} only",
                           "cls": "warn", "h": "One order, not re-priced; cancelled at the close if not filled; a fill is sold at the next open"})
        tiles = [{"k": "trend", "title": "In · trend", "text": f"{p['signal']} breakout ({p['don_entry']}/{p['don_exit']}) and {p['gate']} above "
                  f"SMA{p['gate_ma']}", "hold": f"{p['target_vol_pct']:g}% ÷ volatility in {p['trade']} (≤100%)", "color": STATE_COLOR["trend"]},
                 {"k": "crash", "title": "In · Hang Seng crash", "text": f"Hang Seng closed ≤ −{p['big_drop_pct']:g}%: bought at the US open; "
                  f"sold at the next open if up {p['tp_pct']:g}%, else the open after", "hold": f"100% {p['trade']}", "color": STATE_COLOR["crash"]},
                 {"k": "small", "title": "In · small crash (1 day)", "text": f"Hang Seng −{p['small_drop_pct']:g}% to −{p['big_drop_pct']:g}%: limit "
                  f"1% under the previous close, sold at the next open", "hold": f"{p['small_size_pct']:g}% {p['trade']}", "color": STATE_COLOR["small"]},
                 {"k": "stopped", "title": "Out · trailing stop", "text": f"{p['trade']} closed {p['trail_pct']:g}% under the run's high",
                  "hold": "cash (crash buys still count)", "color": STATE_COLOR["stopped"]},
                 {"k": "out", "title": "Out", "text": "No trend, no crash", "hold": "cash", "color": STATE_COLOR["out"]}]
        if float(p["trail_pct"]) <= 0:
            tiles = [t for t in tiles if t["k"] != "stopped"]

        def num(x):
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return None if x != x else x
        log_rows = []
        for i in range(last, max(last - 30, 0), -1):
            rr, ww = fr.iloc[i], W.iloc[i]
            act = []
            if ww["big_new"]:
                act.append("crash buy at the open")
            if ww["tp"]:
                act.append("take-profit at the open")
            if ww["small"]:
                act.append("limit filled" if ww["fill"] else "limit not filled")
            log_rows.append({"date": str(fr.index[i].date()), "close": num(rr["c"]), "kc": num(rr["kc"]), "fx": num(rr["fxc"]),
                             "hs": num(rr["hs_ret"] * 100), "trend": num(rr["tw"] * 100), "held": num(ww["w"] * 100),
                             "state": ww["state"], "action": ", ".join(act) or "—",
                             "changed": bool(i > 0 and abs(W["w"].iloc[i] - W["w"].iloc[i - 1]) > 1e-9), "from": W["state"].iloc[i - 1] if i > 0 else None})
        log_cols = [{"k": "close", "label": p["trade"], "fmt": "n2"}, {"k": "kc", "label": p["signal"], "fmt": "n2"},
                    {"k": "fx", "label": p["gate"], "fmt": "n2"}, {"k": "hs", "label": "Hang Seng %", "fmt": "n2"},
                    {"k": "trend", "label": "Trend %", "fmt": "n0"}, {"k": "held", "label": "Held %", "fmt": "n0"}]
        pct = round(want * 100)
        label = {"crash": f"IN · {pct}% {p['trade']} · Hang Seng crash buy",
                 "small": f"LIMIT · {p['small_size_pct']:g}% {p['trade']} at ${rest[p['trade']]['limit']:,.2f} today" if rest else "",
                 "trend": f"IN · {pct}% {p['trade']} · trend", "stopped": "OUT · cash · trailing stop",
                 "out": "OUT · cash"}[state]
        return {"ok": True, "state": state, "label": label, "target": target, "rest": rest,
                "bar_time": bar_time, "signal_time": sig_t, "price": num(r["c"]),
                "checks": checks, "history": hist, "next_check": self.next_check(now),
                "detail": {"date": str(fr.index[last].date()), "next_session": str(nxt), "tiles": tiles, "log": log_rows, "log_cols": log_cols,
                           "checks": checks, "close": num(r["c"]), "state_text": STATE_TEXT[state],
                           "title": "Position · trend decided after each US close, crash buys after Hong Kong's close"}}

    def next_check(self, now):
        """The next moment something can change: Hong Kong's close (crash buys), the US open (take-profit), the US close."""
        ts = []
        d = now.astimezone(HKT).date()
        for k in range(0, 5):
            t = hk_close_ts(d + timedelta(days=k))
            if t > now.timestamp():
                ts.append(t)
                break
        b = mh.next_open(now)
        if b:
            ts.append(int(b.timestamp()) + 60)
        u = super().next_check(now)
        if u:
            ts.append(u)
        return min(ts) if ts else None

    # ---------------------------------------------------------------- chart
    def chart(self, now, rng="8M"):
        p = self.params
        fr = self.frame(now, live=False)
        W = walk(fr, p)
        k0 = -RANGE_DAYS.get(rng, 168)
        fr, W = fr.iloc[k0:], W.iloc[k0:]
        t = [int(pd.Timestamp(x).timestamp()) for x in fr.index]

        def ln(arr, digits=4, mult=1.0):
            v = np.asarray(arr, dtype=float)
            return [{"time": t[i], "value": round(float(v[i]) * mult, digits)} if not np.isnan(v[i]) else {"time": t[i]} for i in range(len(t))]

        w = W["w"].values
        markers = []
        for i in range(len(fr)):
            if W["big_new"].iloc[i]:
                markers.append({"time": t[i], "position": "belowBar", "color": "#EF5350", "shape": "arrowUp", "text": "Crash buy"})
            if W["tp"].iloc[i]:
                markers.append({"time": t[i], "position": "aboveBar", "color": "#26A69A", "shape": "arrowDown", "text": "Take-profit"})
            if W["fill"].iloc[i]:
                markers.append({"time": t[i], "position": "belowBar", "color": "#F5C76B", "shape": "circle", "text": "Limit filled"})
            if i > 0 and fr["tw"].iloc[i - 1] != (fr["tw"].iloc[i - 2] if i > 1 else fr["tw"].iloc[i - 1]):
                up = fr["tw"].iloc[i - 1] > fr["tw"].iloc[i - 2]
                markers.append({"time": t[i], "position": "belowBar" if up else "aboveBar", "color": "#2962FF" if up else "#E040FB",
                                "shape": "arrowUp" if up else "arrowDown", "text": "Trend " + ("in" if up else "out")})
        hs = fr["hs_ret"].values * 100
        panes = [{"id": "hs", "title": "Hang Seng daily move (%) · same-date US session", "height": 90,
                  "lines": [{"name": "Hang Seng %", "color": "#F5C76B", "width": 1, "data": ln(hs, 2)}],
                  "hlines": [{"value": -float(p["small_drop_pct"]), "label": f"small −{p['small_drop_pct']:g}%"},
                             {"value": -float(p["big_drop_pct"]), "label": f"big −{p['big_drop_pct']:g}%"}]},
                 {"id": "size", "title": f"Money in {p['trade']} (%)", "height": 70, "step": True,
                  "lines": [{"name": "Held at the close", "color": self.color, "width": 2, "area": True, "data": ln(w, 1, 100)},
                            {"name": "Trend part", "color": "#26A69A", "width": 1, "data": ln(W["trend"].values, 1, 100)}], "hlines": []}]
        lines = []
        if float(p["trail_pct"]) > 0:
            lines.append({"name": f"Trailing stop ({p['trail_pct']:g}%)", "color": "#8E3B46", "width": 1,
                          "data": ln(fr["peak"].values * (1 - float(p["trail_pct"]) / 100), 4)})
        sig = {"id": "trade", "title": f"{p['trade']} · 1D", "subtitle": "Traded — volatility, the trailing stop and crash fills are read here",
               "candles": [{"time": t[i], "open": round(float(fr["o"].iloc[i]), 4), "high": round(float(fr["h"].iloc[i]), 4),
                            "low": round(float(fr["l"].iloc[i]), 4), "close": round(float(fr["c"].iloc[i]), 4)} for i in range(len(fr))],
               "lines": lines, "ribbon": [{"time": t[i], "color": STATE_COLOR.get(s, "#2A2E39"), "state": s} for i, s in enumerate(W["state"].values)],
               "panes": panes, "markers": markers, "tv": tv_url(p["trade"]), "tv_symbol": TV.get(p["trade"], p["trade"])}
        _, kw, fx, _ = self.inputs(now)                      # dividend-adjusted, like the lines
        kw = kw[kw.index.isin(fr.index)]
        charts = [sig]
        if len(kw):
            kt = [int(pd.Timestamp(x).timestamp()) for x in kw.index]
            hi, lo = fr["hi"].reindex(kw.index).values, fr["lo"].reindex(kw.index).values

            def ln2(v):
                return [{"time": kt[i], "value": round(float(v[i]), 4)} if v[i] == v[i] else {"time": kt[i]} for i in range(len(kt))]
            charts.append({"id": "signal", "title": f"{p['signal']} · 1D", "subtitle": "Breakout — the Donchian channel is read from this chart "
                                                                                     "(dividends added back)",
                           "candles": [{"time": kt[i], "open": round(float(kw["o"].iloc[i]), 4), "high": round(float(kw["h"].iloc[i]), 4),
                                        "low": round(float(kw["l"].iloc[i]), 4), "close": round(float(kw["c"].iloc[i]), 4)} for i in range(len(kw))],
                           "lines": [{"name": f"{p['don_entry']}-day high", "color": "#26A69A", "width": 1, "data": ln2(hi)},
                                     {"name": f"{p['don_exit']}-day low", "color": "#EF5350", "width": 1, "data": ln2(lo)}],
                           "markers": [], "panes": [], "tv": tv_url(p["signal"]), "tv_symbol": TV.get(p["signal"], p["signal"])})
        fx = fx[fx.index.isin(fr.index)]
        if len(fx):
            ft = [int(pd.Timestamp(x).timestamp()) for x in fx.index]
            ma = fr["fxma"].reindex(fx.index).values
            charts.append({"id": "gate", "title": f"{p['gate']} · 1D", "subtitle": f"Gate — the trend part needs it above SMA{p['gate_ma']} (dividends added back)",
                           "candles": [{"time": ft[i], "open": round(float(fx["o"].iloc[i]), 4), "high": round(float(fx["h"].iloc[i]), 4),
                                        "low": round(float(fx["l"].iloc[i]), 4), "close": round(float(fx["c"].iloc[i]), 4)} for i in range(len(fx))],
                           "lines": [{"name": f"SMA {p['gate_ma']}", "color": "#FF9800", "width": 2,
                                      "data": [{"time": ft[i], "value": round(float(ma[i]), 4)} if ma[i] == ma[i] else {"time": ft[i]} for i in range(len(ft))]}],
                           "markers": [], "panes": [], "tv": tv_url(p["gate"]), "tv_symbol": TV.get(p["gate"], p["gate"])})
        return {"charts": charts, "states": STATE_COLOR}

    def describe(self):
        p = self.params
        rules = [f"After each US close: trend on while {p['signal']} has broken out (a close above its prior {p['don_entry']}-day high; off at a "
                 f"close below its prior {p['don_exit']}-day low) and {p['gate']} closes above its {p['gate_ma']}-day average.",
                 f"Trend size = {p['target_vol_pct']:g}% ÷ {p['trade']}'s {p['vol_days']}-day volatility (a year), at most 100%; resized only on a "
                 f"move of {p['size_band_pct']:g} points. Traded at the next US open."]
        if float(p["trail_pct"]) > 0:
            rules.append(f"Trailing stop on the trend part: a close {p['trail_pct']:g}% below the highest close since the trend run began ends it "
                         "until the trend signal turns off and on again.")
        rules += [f"After Hong Kong's close (15:00 Bangkok): the Hang Seng down {p['big_drop_pct']:g}% or more → 100% {p['trade']} at that day's "
                  f"US open; sold at the next open if {p['trade']} opens {p['tp_pct']:g}% or more above the buy, otherwise at the open after.",
                  f"Hang Seng down {p['small_drop_pct']:g}% to {p['big_drop_pct']:g}% → a limit buy for {p['small_size_pct']:g}% at "
                  f"{p['small_limit_pct']:g}% under {p['trade']}'s previous close, that day only; a fill is sold at the next open.",
                  "The strategy holds the largest of the parts; otherwise cash."]
        return {"rules": rules,
                "flow": f"{p['signal']} breakout + {p['gate']} SMA{p['gate_ma']} + Hang Seng close → {p['trade']} · cash",
                "tv": f'{p["signal"]} daily: "Donchian Channels" length {p["don_entry"]} (and {p["don_exit"]} for the exit); '
                      f'{p["gate"]} daily: "Moving Average" length {p["gate_ma"]}; HSI daily change',
                "rule": f"{p['trade']}: {p['signal']} breakout and {p['gate']} > SMA{p['gate_ma']} (size {p['target_vol_pct']:g}% ÷ vol, "
                        f"{p['trail_pct']:g}% trailing stop); Hang Seng ≤ −{p['big_drop_pct']:g}% → 100% at the US open "
                        f"(take-profit {p['tp_pct']:g}% next open, else 2 days); −{p['small_drop_pct']:g}% → {p['small_size_pct']:g}% "
                        f"limit 1 day; else cash"}

    # ---------------------------------------------------------------- backtest (backtest.py calls this)
    def backtest_run(self, now, cost, delay=0):
        """The research's way of trading, on the bot's own data: trend changes at the next open; a big-crash buy at the open
        of the Hang Seng's date; the take-profit at the next open; a small-crash limit fills when the day's low reaches it,
        at the limit (or the open, if lower). delay (stress test): every decision used `delay` sessions later."""
        from .. import backtest as BT
        p = self.params
        for s in self.history_symbols():
            BT.ensure_signal_history(s)
        fr = self.frame(now, synth=True, live=False)
        W = walk(fr, p)
        tr = BT.daily_tr(p["trade"])
        ktr = BT.daily_tr(p["signal"])
        tr = synth_cweb(tr, ktr)
        if tr is None or tr.empty:
            raise BT.BacktestError(f"No price history for {p['trade']}")
        tr = tr.reindex(fr.index)
        ok = fr["ok"].values & tr["o"].notna().values & tr["c"].notna().values
        first = int(np.argmax(ok))
        idx = list(range(first, len(fr)))
        if len(idx) < 30:
            raise BT.BacktestError("Not enough overlapping history yet")
        o_tr, c_tr, l_tr = (tr[k].astype(float).values for k in ("o", "c", "l"))
        B = BT.Book(cost)
        sym = p["trade"]
        buf = 1 - self.buffer()
        band = self.rebalance_band()
        days, eq, expo, states = [], [], [], []
        cur, drift = 0.0, False
        for i in idx:
            j = i - delay
            d = fr.index[i].date()
            t_open = datetime.combine(d, dtime(9, 30), NY)
            if j >= first:
                ow = float(W["open_w"].iloc[j])
                if abs(ow - cur) > 1e-9:
                    why = self._bt_why(fr, W, j, cur, ow)
                    kind = "START" if not B.trades else ("BUY" if ow > cur else "SELL")
                    B.rebalance({sym: ow * buf} if ow > 0 else {}, {sym: o_tr[i]}, t_open, why, kind)
                    cur = ow
                elif drift and cur > 0:
                    B.rebalance({sym: cur * buf}, {sym: o_tr[i]}, t_open,
                                f"rebalance: the holding drifted more than {band * 100:g} points from its target", "REBALANCE")
                if W["small"].iloc[j] and cur < float(p["small_size_pct"]) / 100 - 1e-9 and i > 0:
                    lim = c_tr[i - 1] * (1 - float(p["small_limit_pct"]) / 100)
                    if l_tr[i] <= lim:
                        px = min(o_tr[i], lim)
                        ssz = float(p["small_size_pct"]) / 100
                        B.rebalance({sym: ssz * buf}, {sym: px}, t_open + timedelta(minutes=1),
                                    f"Hang Seng {fr['hs_ret'].iloc[j] * 100:+.2f}%: limit buy {p['small_size_pct']:g}% filled at "
                                    f"{(px / c_tr[i - 1] - 1) * 100:+.1f}% vs the previous close", "BUY")
                        cur = ssz
            v = B.value({sym: c_tr[i]})
            aw = B.weights({sym: c_tr[i]}).get(sym, 0.0)
            drift = abs(aw - cur * buf) > band
            days.append(d)
            eq.append(v)
            expo.append(aw)
            states.append(W["state"].iloc[j] if j >= first else "out")
        bench = {sym: tr.dropna(subset=["c"]), p["signal"]: ktr}
        return {"days": days, "eq": eq, "expo": expo, "trades": B.trades, "fees": B.fees, "state": states,
                "built": {sym: str(SYNTH_UNTIL)} if fr.index[first].date() < SYNTH_UNTIL else {},
                "bench": bench, "rf": BT.daily_tr(BT.RF_SYMBOL), "main": sym, "index": p["signal"], "data_from": str(days[0]),
                "data_note": f"{p['signal']}, {p['gate']} daily bars (trend) · Hang Seng daily closes (crash buys, same-date US session) · "
                             f"{sym} daily total-return prices; {sym} before {SYNTH_UNTIL}: built from 2 × {p['signal']} minus "
                             f"{SYNTH_DRAG_Y * 100:.1f}% a year (it traded too thinly before 2018)"}

    def _bt_why(self, fr, W, j, cur, ow):
        p = self.params
        if W["big_new"].iloc[j]:
            return f"Hang Seng {fr['hs_ret'].iloc[j] * 100:+.2f}%: crash buy at the US open"
        if W["tp"].iloc[j]:
            return f"take-profit: opened ≥ {p['tp_pct']:g}% above the crash buy"
        if W["big"].iloc[j - 1] if j > 0 else False:
            if not W["big"].iloc[j]:
                return "crash buy sold (2 days)"
        if j > 0 and W["fill"].iloc[j - 1] and ow < W["w"].iloc[j - 1]:
            return "small-crash buy sold at the next open"
        try:
            return self.close_why(fr, W, j - 1, cur, ow).replace(" · from the next open", "").replace(" from the next open", "")
        except Exception:
            return f"weight {cur * 100:.0f}% → {ow * 100:.0f}%"

    # ---------------------------------------------------------------- health check: independent recompute
    def check_table(self, now, rows=12):
        """Recompute the last `rows` days the long way: Donchian channel, the FXI average and the Hang Seng move."""
        p = self.params
        fr = self.frame(now, live=False)
        cw, kw, fx, hs = self.inputs(now)
        kh = kw["h"].astype(float).tolist()
        kpos = {d: i for i, d in enumerate(kw.index)}
        fc = fx["c"].astype(float).tolist()
        fpos = {d: i for i, d in enumerate(fx.index)}
        hc = hs["c"].astype(float).tolist()
        hpos = {d: i for i, d in enumerate(hs.index)}
        ne, nx, nm = int(p["don_entry"]), int(p["don_exit"]), int(p["gate_ma"])
        cols = ["Close", f"{ne}-day high · bot / check", f"SMA{nm} · bot / check", "Hang Seng % · bot / check", "Trend on"]
        out, worst = [], 0.0
        for d in fr.index[-rows:]:
            r = fr.loc[d]
            k, f = kpos.get(d), fpos.get(d)
            hi = max(kh[k - ne:k]) if k is not None and k >= ne else float("nan")
            ma = sum(fc[f - nm + 1:f + 1]) / nm if f is not None and f >= nm - 1 else float("nan")
            h = hpos.get(d)
            hr = (hc[h] / hc[h - 1] - 1) * 100 if h is not None and h > 0 else float("nan")
            diffs = [abs(r["hi"] - hi) / max(hi, 1e-9) if hi == hi and r["hi"] == r["hi"] else 0.0,
                     abs(r["fxma"] - ma) / max(ma, 1e-9) if ma == ma and r["fxma"] == r["fxma"] else 0.0,
                     abs(r["hs_ret"] * 100 - hr) / 100 if hr == hr and r["hs_ret"] == r["hs_ret"] else (0.0 if (hr != hr) == (r["hs_ret"] != r["hs_ret"]) else 1.0)]
            diff = max(diffs)
            worst = max(worst, diff)
            out.append({"t": int(pd.Timestamp(d).timestamp()),
                        "vals": [float(r["c"]), f"{r['hi']:,.2f} / {hi:,.2f}", f"{r['fxma']:,.2f} / {ma:,.2f}",
                                 f"{r['hs_ret'] * 100:+.2f} / {hr:+.2f}" if hr == hr else "— / —", "yes" if r["on"] else "no"], "ok": bool(diff < 1e-6)})
        return cols, out, worst
