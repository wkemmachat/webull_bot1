"""Check the rule: for each strategy (and each leg of a split) the rule written out, small charts of exactly the numbers the
rule compares, one lane per condition, and a per-day check. The lanes are recomputed here from the charted numbers
(price vs line, volatility vs gate, ...) and the "rule says" lane is combined from them; the "bot is in" lane is the bot's own
decision. The two lanes must match on every day; a day where they differ is shown in red.

Shape returned to the page:
  {"t": [unix close times], "views": [{id, label, rule, tv: [lines], charts: [...], lanes: [...], checks: [...]}],
   "series": {key: {"v": [...], "d": decimals}}}
  chart  = {title, height, lines: [{key, name, color, width?, dash?, step?}], hlines: [{value, label}], shade: {key, color, label}?}
  lane   = {key, label, kind: "cond" | "rule" | "bot"}
  check  = {k, t: "text with {series key} placeholders", ok: series key}
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

RANGE_DAYS = {"3M": 63, "8M": 168, "1Y": 252, "2Y": 504}
C_PRICE, C_LINE, C_LINE2, C_GATE, C_THR, C_DIP, C_MKT = "text", "#FF9800", "#5B8DEF", "#8E6BBF", "#EF5350", "#F5C76B", "#20C997"


def _num(x, d):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, d)


class View:
    def __init__(self, out, vid, label, rule):
        self.out, self.vid = out, vid
        self.v = {"id": vid, "label": label, "rule": rule, "tv": [], "charts": [], "lanes": [], "checks": []}
        out["views"].append(self.v)

    def s(self, key, arr, d=2):
        k = f"{self.vid}.{key}"
        self.out["series"][k] = {"v": [_num(x, d) for x in np.asarray(arr, dtype=float)], "d": d}
        return k

    def b(self, key, arr):
        k = f"{self.vid}.{key}"
        self.out["series"][k] = {"v": [1 if bool(x) else 0 for x in np.asarray(arr)], "d": 0}
        return k

    def chart(self, title, lines, height=110, hlines=None, shade=None, note=""):
        self.v["charts"].append({"title": title, "height": height, "lines": lines, "hlines": hlines or [], "shade": shade, "note": note})

    def lane(self, key, label, kind="cond"):
        self.v["lanes"].append({"key": key, "label": label, "kind": kind})

    def check(self, k, t, ok, need=""):
        """k: the condition, need: what it takes (plain words), t: that day's numbers ({series key} placeholders)."""
        self.v["checks"].append({"k": k, "need": need, "t": t, "ok": ok})


def _tail(fr, n):
    fr = fr[fr["state"] != ""]
    return fr.iloc[-n:]


def _rule_vs_bot(v, rule, bot):
    rk = v.b("rule", rule)
    bk = v.b("bot", bot)
    v.lane(rk, "Rule says: in", "rule")
    v.lane(bk, "Bot is in", "bot")
    return rk, bk


# ---------------------------------------------------------------- trend_gate (SSO, RXL, ROM legs, QLD leg A)
def trend_gate_view(out, s, full, n, vid="main", label=None, idx=None):
    p = s.params
    sig, trade = p["signal"], p["trade"]
    full = full[full["state"] != ""]
    fr = full.reindex(idx) if idx is not None else full.iloc[-n:]
    c, ma = full["c"].values, full["ma"].values
    mt = p["ma_type"]
    # trend recomputed from the charted lines
    if mt == "XEMA":
        up_full = full["fast"].values > ma
    elif mt == "ICHI":
        top, bot = np.fmax(full["cloud_a"].values, full["cloud_b"].values), np.fmin(full["cloud_a"].values, full["cloud_b"].values)
        up_full, on = np.zeros(len(c), dtype=bool), bool(full["up"].iloc[0])
        for i in range(len(c)):
            if np.isnan(top[i]):
                on = False
            elif c[i] > top[i]:
                on = True
            elif c[i] < bot[i]:
                on = False
            up_full[i] = on
    else:
        up_full = c > ma
    up = pd.Series(up_full, index=full.index).reindex(fr.index).fillna(False).values.astype(bool)
    rule_txt = s.describe().get("rule", "")
    v = View(out, vid, label or s.name, rule_txt)
    kc = v.s("c", fr["c"])
    # 1 trend chart
    if mt == "XEMA":
        kf, km = v.s("fast", fr["fast"]), v.s("ma", fr["ma"])
        v.chart(f"{sig} · trend: EMA{p['fast_days']} above EMA{p['ma_days']}", [
            {"key": kc, "name": sig, "color": C_PRICE, "width": 1}, {"key": kf, "name": f"EMA{p['fast_days']}", "color": C_LINE2, "width": 2},
            {"key": km, "name": f"EMA{p['ma_days']}", "color": C_LINE, "width": 2}], 150)
        kg = v.s("macd", fr["fast"] - fr["ma"])
        v.chart(f"MACD line ({p['fast_days']}/{p['ma_days']}) · in the trend above 0", [{"key": kg, "name": "EMA fast − EMA slow", "color": C_LINE2, "width": 2}],
                80, hlines=[{"value": 0, "label": "0"}])
        trend_t, need0 = f"EMA{p['fast_days']} {{{kf}}} vs EMA{p['ma_days']} {{{km}}}", f"EMA{p['fast_days']} above EMA{p['ma_days']}"
        tv0 = f'{sig} daily · "MACD": fast {p["fast_days"]}, slow {p["ma_days"]} (EMA) · in while the MACD line is above 0'
    elif mt == "ICHI":
        ka, kb = v.s("ca", fr["cloud_a"]), v.s("cb", fr["cloud_b"])
        kt, kbo = v.s("ctop", np.fmax(fr["cloud_a"].values, fr["cloud_b"].values)), v.s("cbot", np.fmin(fr["cloud_a"].values, fr["cloud_b"].values))
        v.chart(f"{sig} · trend: above the Ichimoku cloud ({p['ichi_tenkan']}/{p['ichi_kijun']}/{p['ma_days']})", [
            {"key": kc, "name": sig, "color": C_PRICE, "width": 1}, {"key": ka, "name": "Cloud span A", "color": "#26A69A", "width": 1},
            {"key": kb, "name": "Cloud span B", "color": "#EF5350", "width": 1}], 150, shade={"key": "cloud", "a": ka, "b": kb},
            note="On when it closes above the cloud, off when it closes below it, unchanged inside it")
        trend_t = f"{sig} {{{kc}}} · cloud {{{kbo}}} – {{{kt}}}"
        need0 = f"{sig} closes above the cloud to turn on, below it to turn off"
        tv0 = (f'{sig} daily · "Ichimoku Cloud": Conversion Line {p["ichi_tenkan"]}, Base Line {p["ichi_kijun"]}, Leading Span B {p["ma_days"]}, '
               f'Lagging Span {p["ichi_shift"] + 1}')
    else:
        km = v.s("ma", fr["ma"])
        nm = f"Close {p['ma_days']} days ago" if mt == "ROC" else f"{mt}{p['ma_days']}"
        v.chart(f"{sig} · trend: close above {nm if mt != 'ROC' else 'its close ' + str(p['ma_days']) + ' days ago'}", [
            {"key": kc, "name": sig, "color": C_PRICE, "width": 1}, {"key": km, "name": nm, "color": C_LINE, "width": 2}], 150)
        trend_t = f"{sig} {{{kc}}} vs {nm if mt != 'ROC' else str(p['ma_days']) + ' days ago'} {{{km}}}"
        need0 = f"{sig} above {nm}" if mt != "ROC" else f"{sig} above its close {p['ma_days']} days ago"
        tv0 = (f'{sig} daily · "Rate Of Change" length {p["ma_days"]}: in while above 0' if mt == "ROC" else
               f'{sig} daily · "Moving Average{" Exponential" if mt == "EMA" else ""}" length {p["ma_days"]}')
    v.v["tv"].append(tv0)
    ku = v.b("up", up)
    v.lane(ku, "Trend up")
    v.check("Trend", trend_t, ku, need0)
    gate = up.copy()
    # 2 gates
    if p["vol_gate_q"] > 0:
        kv, kt2 = v.s("vol", fr["vol"], 2), v.s("thr", fr["vol_thr"], 2)
        calm = fr["vol"].values < fr["vol_thr"].values
        kca = v.b("calm", calm)
        v.chart(f"Calm gate · {sig} {p['vol_days']}-day volatility below its {p['vol_gate_q']:g}th percentile", [
            {"key": kv, "name": "Volatility % a day", "color": C_GATE, "width": 2}, {"key": kt2, "name": f"{p['vol_gate_q']:g}th percentile", "color": C_THR, "width": 1, "dash": True}],
            90, shade={"key": kca, "when": 0, "color": "#8E6BBF", "label": "jumpy"})
        v.lane(kca, "Calm")
        v.check("Calm", f"{{{kv}}}% vs gate {{{kt2}}}%", kca, f"{p['vol_days']}-day volatility below its {p['vol_gate_q']:g}th percentile")
        v.v["tv"].append(f"Volatility: no TradingView indicator draws the {p['vol_gate_q']:g}th-percentile line; use this chart")
        gate &= calm
    if s.credit_on():
        kr, km2 = v.s("cr", fr["credit_ratio"], 4), v.s("cm", fr["credit_ma"], 4)
        okc = fr["credit_ratio"].values > fr["credit_ma"].values
        kok = v.b("credit", okc)
        v.chart(f"Credit check · {p['credit_a']} ÷ {p['credit_b']} above its SMA{p['credit_ma']} (dividend-adjusted)", [
            {"key": kr, "name": "Ratio", "color": C_MKT, "width": 2}, {"key": km2, "name": f"SMA{p['credit_ma']}", "color": C_LINE, "width": 1}],
            80, shade={"key": kok, "when": 0, "color": "#EF5350", "label": "credit weak"})
        v.lane(kok, "Credit OK")
        v.check("Credit", f"{{{kr}}} vs SMA{p['credit_ma']} {{{km2}}}", kok, f"{p['credit_a']} ÷ {p['credit_b']} above its SMA{p['credit_ma']}")
        v.v["tv"].append(f'Credit: chart "{p["credit_a"]}/{p["credit_b"]}" with a {p["credit_ma"]}-day Moving Average (TradingView uses plain prices, so it reads a little lower)')
        gate &= okc
    if p.get("mkt_symbol"):
        kmc, kmm = v.s("mc", fr["mkt_c"]), v.s("mm", fr["mkt_ma"])
        okm = fr["mkt_c"].values > fr["mkt_ma"].values
        kmk = v.b("mkt", okm)
        v.chart(f"Market check · {p['mkt_symbol']} above its SMA{p['mkt_ma_days']}", [
            {"key": kmc, "name": p["mkt_symbol"], "color": C_PRICE, "width": 1}, {"key": kmm, "name": f"SMA{p['mkt_ma_days']}", "color": C_LINE, "width": 2}],
            80, shade={"key": kmk, "when": 0, "color": "#EF5350", "label": "below"})
        v.lane(kmk, f"{p['mkt_symbol']} OK")
        v.check("Market", f"{p['mkt_symbol']} {{{kmc}}} vs SMA{p['mkt_ma_days']} {{{kmm}}}", kmk, f"{p['mkt_symbol']} above its SMA{p['mkt_ma_days']}")
        v.v["tv"].append(f'{p["mkt_symbol"]} daily · "Moving Average" length {p["mkt_ma_days"]}')
        gate &= okm
    # 3 dips
    e = p.get("dip_entry", "RSI")
    ph = p.get("dip_exit", "SMA") == "PREVHIGH"
    exit_t = (f"sold on a close above the previous day's high or after {p['dip_max_days']} days" if ph else f"sold on a close above SMA{p['exit_ma']}")
    trade_on = fr["rsi_on"].values.astype(bool)
    ktr = None
    if s.dips_on():
        ktr = v.b("trade", trade_on)
        if e == "IBS":
            ki = v.s("sibs", fr["sig_ibs"], 2)
            v.chart(f"Dip trade · opens below the trend when {sig} IBS < {p['entry_ibs_max']:g}, {exit_t}", [
                {"key": ki, "name": f"IBS {sig}", "color": C_DIP, "width": 1}], 80, hlines=[{"value": p["entry_ibs_max"], "label": f"buy < {p['entry_ibs_max']:g}"}],
                shade={"key": ktr, "when": 1, "color": "#F5C76B", "label": "dip trade open"})
            v.check("Dip trade", f"IBS {{{ki}}}", ktr, f"trend off and {sig} IBS < {p['entry_ibs_max']:g} opens it; {exit_t}")
        elif e == "3DOWN":
            full_c = full["c"].values
            run = np.zeros(len(full_c))
            for i in range(1, len(full_c)):
                run[i] = run[i - 1] + 1 if full_c[i] < full_c[i - 1] else 0
            kd = v.s("down", pd.Series(run, index=full.index).reindex(fr.index).values, 0)
            v.chart(f"Dip trade · opens below the trend on the 3rd lower close in a row, {exit_t}", [
                {"key": kd, "name": "Lower closes in a row", "color": C_DIP, "width": 2, "step": True}], 70, hlines=[{"value": 3, "label": "3"}],
                shade={"key": ktr, "when": 1, "color": "#F5C76B", "label": "dip trade open"})
            v.check("Dip trade", f"{{{kd}}} lower closes in a row", ktr, f"trend off and the 3rd lower close in a row opens it; {exit_t}")
        else:
            kr2 = v.s("rsi", fr["rsi"], 1)
            v.chart(f"Dip trade · opens below the trend when RSI({p['rsi_len']}) < {p['rsi_buy']:g}, {exit_t}", [
                {"key": kr2, "name": f"RSI({p['rsi_len']})", "color": C_DIP, "width": 1}], 80, hlines=[{"value": p["rsi_buy"], "label": f"buy < {p['rsi_buy']:g}"}],
                shade={"key": ktr, "when": 1, "color": "#F5C76B", "label": "dip trade open"})
            v.check("Dip trade", f"RSI({p['rsi_len']}) {{{kr2}}}", ktr, f"trend off and RSI({p['rsi_len']}) < {p['rsi_buy']:g} opens it; {exit_t}")
            v.v["tv"].append(f'{sig} daily · "Relative Strength Index" length {p["rsi_len"]}')
        if not ph:
            kx = v.s("sx", fr["sma_exit"])
            v.v["checks"][-1]["t"] += f" · SMA{p['exit_ma']} {{{kx}}}"
        v.lane(ktr, "Dip trade open")
    one = np.zeros(len(fr), dtype=bool)
    if p["dip_ibs_max"] > 0:
        kdi = v.s("dibs", fr["ibs_dip"], 2)
        hit = ~up & (fr["ibs_dip"].values < p["dip_ibs_max"])
        kh = v.b("ibs1", hit)
        v.chart(f"One-day dip · below the trend, {s.dip_sym()} IBS < {p['dip_ibs_max']:g} → hold the next day", [
            {"key": kdi, "name": f"IBS {s.dip_sym()}", "color": C_DIP, "width": 1}], 70, hlines=[{"value": p["dip_ibs_max"], "label": f"< {p['dip_ibs_max']:g}"}],
            shade={"key": kh, "when": 1, "color": "#F5C76B", "label": "one-day dip"})
        v.lane(kh, f"One-day dip ({s.dip_sym()} IBS)")
        v.check("One-day dip", f"{s.dip_sym()} IBS {{{kdi}}}", kh, f"trend off and {s.dip_sym()} IBS < {p['dip_ibs_max']:g}")
        one |= hit
    r1 = float(p.get("rsi_1d_buy") or 0)
    if r1 > 0:
        kr3 = v.s("rsi", fr["rsi"], 1)
        hit = ~up & (fr["rsi"].values < r1)
        kh2 = v.b("rsi1", hit)
        v.chart(f"One-day dip · below the trend, RSI({p['rsi_len']}) < {r1:g} → hold the next day", [
            {"key": kr3, "name": f"RSI({p['rsi_len']})", "color": "#E46AA8", "width": 1}], 70, hlines=[{"value": r1, "label": f"< {r1:g}"}],
            shade={"key": kh2, "when": 1, "color": "#F5C76B", "label": "one-day dip"})
        v.lane(kh2, f"One-day dip (RSI < {r1:g})")
        v.check("One-day dip", f"RSI({p['rsi_len']}) {{{kr3}}}", kh2, f"trend off and RSI({p['rsi_len']}) < {r1:g}")
        v.v["tv"].append(f'{sig} daily · "Relative Strength Index" length {p["rsi_len"]} (line at {r1:g})')
        one |= hit
    if p["jumpy_ibs_max"] > 0:
        one |= fr["jumpy_hit"].values.astype(bool)
    if s.sized():
        kz = v.s("size", fr["size"] * 100, 0)
        v.chart(f"Size · min(100%, {p['target_vol_pct']:g}% ÷ {trade} {p['size_vol_days']}-day volatility) on trend days, 100% on dips", [
            {"key": kz, "name": f"Money in {trade} %", "color": s.color, "width": 2, "step": True}], 60)
    rule = (gate | trade_on | one)
    bot = np.isin(fr["state"].values, ["trend", "dip"])
    _rule_vs_bot(v, rule, bot)
    v.v["tv"].append("IBS = (close − low) ÷ (high − low): no built-in indicator; read it from the daily bar")
    return v


# ---------------------------------------------------------------- ibd_gate (QLD legs B and C)
def ibd_gate_view(out, s, full, n, vid="main", label=None, idx=None):
    p = s.params
    sig = p["signal"]
    full = full[full["state"] != ""]
    fr = full.reindex(idx) if idx is not None else full.iloc[-n:]
    v = View(out, vid, label or s.name, s.describe().get("rule", ""))
    kc = v.s("c", fr["c"])
    mode = p["trend_mode"]
    ibd = fr["ibd_up"].values.astype(bool)
    lines = [{"key": kc, "name": sig, "color": C_PRICE, "width": 1}]
    if mode != "IBD":
        ks = v.s("sma", fr["sma"])
        lines.append({"key": ks, "name": f"SMA{p['ma_days']}", "color": C_LINE, "width": 2})
    kib = v.b("ibd", ibd)
    v.chart(f"{sig} · trend: " + ("IBD market direction up" if mode == "IBD" else f"IBD market direction up OR close above SMA{p['ma_days']}"),
            lines, 150, shade={"key": kib, "when": 0, "color": "#EF5350", "label": "IBD correction"})
    kdc = v.s("dc", fr["dcount"], 0)
    v.chart(f"IBD · distribution days counted (a correction starts at {p['ibd_dist']}; a follow-through day ends it)", [
        {"key": kdc, "name": "Distribution days", "color": "#EF5350", "width": 2, "step": True}], 80, hlines=[{"value": p["ibd_dist"], "label": str(p["ibd_dist"])}],
        shade={"key": kib, "when": 0, "color": "#EF5350", "label": "correction"},
        note=(f"Distribution day: {sig} down ≥ {p['ibd_down_pct']:g}% on higher volume; counted for {p['ibd_window']} sessions or until "
              f"{sig} is {p.get('ibd_expire_pct', 5):g}% above it. Follow-through: day {p['ibd_ftd_day']}+ of a rally, up ≥ {p['ibd_ftd_pct']:g}% on higher volume"))
    v.lane(kib, "IBD direction up")
    v.check("IBD", f"{{{kdc}}} distribution days counted", kib, f"no correction: fewer than {p['ibd_dist']} distribution days, or a follow-through day since")
    if mode == "IBD":
        up = ibd
    else:
        above = fr["c"].values > fr["sma"].values
        ka = v.b("above", above)
        v.lane(ka, f"Above SMA{p['ma_days']}")
        v.check(f"SMA{p['ma_days']}", f"{sig} {{{kc}}} vs SMA{p['ma_days']} {{{ks}}}", ka, f"{sig} above SMA{p['ma_days']} (either this or IBD up)")
        up = (ibd | above) if mode == "SMA|IBD" else above
        ku = v.b("up", up)
        v.lane(ku, "Trend up (either)")
    kv, kt = v.s("vol", fr["vol"], 2), v.s("thr", fr["vol_thr"], 2)
    calm = fr["vol"].values < fr["vol_thr"].values if p["vol_gate_q"] > 0 else np.ones(len(fr), dtype=bool)
    kca = v.b("calm", calm)
    if p["vol_gate_q"] > 0:
        v.chart(f"Calm gate · {sig} {p['vol_days']}-day volatility below its {p['vol_gate_q']:g}th percentile", [
            {"key": kv, "name": "Volatility % a day", "color": C_GATE, "width": 2}, {"key": kt, "name": f"{p['vol_gate_q']:g}th percentile", "color": C_THR, "width": 1, "dash": True}],
            90, shade={"key": kca, "when": 0, "color": "#8E6BBF", "label": "jumpy"})
        v.lane(kca, "Calm")
        v.check("Calm", f"{{{kv}}}% vs gate {{{kt}}}%", kca, f"{p['vol_days']}-day volatility below its {p['vol_gate_q']:g}th percentile")
    trend = up & calm
    kr = v.s("rsi", fr["rsi"], 1)
    cap = (fr["vol_y"].values < p["dip_vol_cap_pct"]) if p["dip_vol_cap_pct"] > 0 else np.ones(len(fr), dtype=bool)
    dip = ~trend & (fr["rsi"].values < p["rsi_buy"]) & cap if p["rsi_buy"] > 0 else np.zeros(len(fr), dtype=bool)
    kd = v.b("dip", dip)
    v.chart(f"One-day dip · when not in the trend, RSI({p['rsi_len']}) < {p['rsi_buy']:g}" + (f" and {sig}'s volatility under {p['dip_vol_cap_pct']:g}% a year" if p["dip_vol_cap_pct"] > 0 else "")
            + " → hold the next day", [{"key": kr, "name": f"RSI({p['rsi_len']})", "color": C_DIP, "width": 1}], 70,
            hlines=[{"value": p["rsi_buy"], "label": f"< {p['rsi_buy']:g}"}], shade={"key": kd, "when": 1, "color": "#F5C76B", "label": "one-day dip"})
    v.lane(kd, "One-day dip")
    dtxt = f"RSI({p['rsi_len']}) {{{kr}}}"
    dneed = f"not in the trend and RSI({p['rsi_len']}) < {p['rsi_buy']:g}"
    if p["dip_vol_cap_pct"] > 0:
        kvy = v.s("vy", fr["vol_y"], 0)
        dtxt += f" · volatility {{{kvy}}}% a year"
        dneed += f" and volatility under {p['dip_vol_cap_pct']:g}% a year"
    v.check("One-day dip", dtxt, kd, dneed)
    if float(p["target_vol_pct"] or 0) > 0:
        kz = v.s("size", fr["size"] * 100, 0)
        v.chart(f"Size · min(99%, {p['target_vol_pct']:g}% ÷ {p['trade']} {p['size_vol_days']}-day volatility), resized on a {p['size_band_pct']:g}-point move", [
            {"key": kz, "name": f"Leg's money in {p['trade']} %", "color": s.color, "width": 2, "step": True}], 60)
    _rule_vs_bot(v, trend | dip, np.isin(fr["state"].values, ["trend", "dip"]))
    v.v["tv"] += [f'{sig} daily' + (f' · "Moving Average" length {p["ma_days"]}' if mode != "IBD" else ""),
                  "IBD market direction: no TradingView indicator; use the distribution-day chart",
                  f'"Relative Strength Index" length {p["rsi_len"]} (line at {p["rsi_buy"]:g})']
    return v


VIEWS = {"trend_gate": trend_gate_view, "ibd_gate": ibd_gate_view}


# ---------------------------------------------------------------- trend_split (USD)
def trend_split(out, s, now, n):
    from .strategies.trend_split import LEGS
    p = s.params
    sig = p["signal"]
    fr = _tail(s.frame(now), n)
    kc = None
    mix = View(out, "mix", "Mix", "Each leg is a third of the money; the share in " + p["trade"] + " is the part whose legs are in (about ⅓, ⅔ or all).")
    for k in LEGS:
        kind, days, q = p[f"leg{k}_kind"], p[f"leg{k}_days"], p[f"leg{k}_calm_q"]
        nm = f"{kind}{days}"
        v = View(out, f"l{k}", f"Leg {k} · {nm}", f"Leg {k} is in when {sig} is above its {'close ' + str(days) + ' days ago' if kind == 'ROC' else nm}"
                 + (f", {sig} is calm ({q:g}th percentile)" if q > 0 else "") + (" and credit is OK" if s.credit_on() else "")
                 + f"; below it, for one day after {s.dip_sym()} IBS < {p['dip_ibs_max']:g}.")
        kc = v.s("c", fr["c"])
        kl = v.s("line", fr[f"l{k}_line"])
        lname = f"its close {days} days ago" if kind == "ROC" else nm
        v.chart(f"{sig} · trend: close above {lname}", [{"key": kc, "name": sig, "color": C_PRICE, "width": 1},
                                                       {"key": kl, "name": lname[0].upper() + lname[1:] if kind == "ROC" else lname, "color": C_LINE, "width": 2}], 150)
        up = fr["c"].values > fr[f"l{k}_line"].values
        ku = v.b("up", up)
        v.lane(ku, "Trend up")
        v.check("Trend", f"{sig} {{{kc}}} vs {nm if kind != 'ROC' else str(days) + ' days ago'} {{{kl}}}", ku, f"{sig} above {lname}")
        gate = up.copy()
        if q > 0:
            kv, kt = v.s("vol", fr[f"l{k}_vol"], 2), v.s("thr", fr[f"l{k}_thr"], 2)
            calm = fr[f"l{k}_vol"].values < fr[f"l{k}_thr"].values
            kca = v.b("calm", calm)
            v.chart(f"Calm gate · {sig} {p['vol_days']}-day volatility below its {q:g}th percentile", [
                {"key": kv, "name": "Volatility % a day", "color": C_GATE, "width": 2}, {"key": kt, "name": f"{q:g}th percentile", "color": C_THR, "width": 1, "dash": True}],
                90, shade={"key": kca, "when": 0, "color": "#8E6BBF", "label": "jumpy"})
            v.lane(kca, "Calm")
            v.check("Calm", f"{{{kv}}}% vs gate {{{kt}}}%", kca, f"{p['vol_days']}-day volatility below its {q:g}th percentile")
            gate &= calm
        if s.credit_on():
            kr, km = v.s("cr", fr["credit_ratio"], 4), v.s("cm", fr["credit_ma"], 4)
            okc = fr["credit_ratio"].values > fr["credit_ma"].values
            kok = v.b("credit", okc)
            v.chart(f"Credit check · {p['credit_a']} ÷ {p['credit_b']} above its SMA{p['credit_ma']} (dividend-adjusted)", [
                {"key": kr, "name": "Ratio", "color": C_MKT, "width": 2}, {"key": km, "name": f"SMA{p['credit_ma']}", "color": C_LINE, "width": 1}],
                80, shade={"key": kok, "when": 0, "color": "#EF5350", "label": "credit weak"})
            v.lane(kok, "Credit OK")
            v.check("Credit", f"{{{kr}}} vs SMA{p['credit_ma']} {{{km}}}", kok, f"{p['credit_a']} ÷ {p['credit_b']} above its SMA{p['credit_ma']}")
            gate &= okc
        dip = np.zeros(len(fr), dtype=bool)
        if p["dip_ibs_max"] > 0:
            ki = v.s("ibs", fr["ibs"], 2)
            dip = ~up & (fr["ibs"].values < p["dip_ibs_max"])
            kd = v.b("dip", dip)
            v.chart(f"One-day dip · below the trend, {s.dip_sym()} IBS < {p['dip_ibs_max']:g} → hold the next day", [
                {"key": ki, "name": f"IBS {s.dip_sym()}", "color": C_DIP, "width": 1}], 70, hlines=[{"value": p["dip_ibs_max"], "label": f"< {p['dip_ibs_max']:g}"}],
                shade={"key": kd, "when": 1, "color": "#F5C76B", "label": "one-day dip"})
            v.lane(kd, "One-day dip")
            v.check("One-day dip", f"{s.dip_sym()} IBS {{{ki}}}", kd, f"trend off and {s.dip_sym()} IBS < {p['dip_ibs_max']:g}")
        bot = fr[f"l{k}_trend"].values.astype(bool) | fr[f"l{k}_dip"].values.astype(bool)
        _rule_vs_bot(v, gate | dip, bot)
        v.v["tv"] = [(f'{sig} daily · "Rate Of Change" length {days}: up while above 0' if kind == "ROC" else
                      f'{sig} daily · "Moving Average{" Exponential" if kind == "EMA" else ""}" length {days}'),
                     f'Credit: chart "{p["credit_a"]}/{p["credit_b"]}" with a {p["credit_ma"]}-day Moving Average (plain prices read a little lower)',
                     "Volatility percentile and IBS: no built-in indicator; use these charts"]
        lk = mix.b(f"in{k}", bot)
        mix.lane(lk, f"Leg {k} · {nm} in")
        mix.check(f"Leg {k}", "", lk, nm)
    kz = mix.s("size", fr["size"] * 100, 0)
    kn = mix.s("n", fr["legs_in"], 0)
    mix.check("Money", f"{{{kz}}}% in {p['trade']} · {{{kn}}} of 3 legs in", None, "the legs that are in")
    mix.chart(f"Money in {p['trade']} · the legs that are in, each a third (set back to a third every January)", [
        {"key": kz, "name": f"Money in {p['trade']} %", "color": s.color, "width": 2, "step": True}], 100)
    mix.chart("Legs in", [{"key": kn, "name": "Legs in (0–3)", "color": C_LINE, "width": 2, "step": True}], 60)
    mix.v["tv"] = ["Pick a leg to see its own indicators"]
    out["views"].insert(0, out["views"].pop(out["views"].index(mix.v)))
    out["t"] = [int(pd.Timestamp(x).timestamp()) for x in fr.index]


# ---------------------------------------------------------------- split_mix (QLD, ROM)
def split_mix(out, s, now, n):
    p = s.params
    fr = _tail(s.frame(now), n)              # also fills each leg's frame_cache
    legs = s.legs()
    w = s.weights()
    mix = View(out, "mix", "Mix", f"The money is split {s.share_word()}{' each' if s.equal() else ''}; the mix holds each leg's own target, "
               f"weighted by each leg's value. The legs are set back to their shares every January.")
    for k, lg in enumerate(legs, 1):
        fn = VIEWS.get(lg.type)
        if fn is None:
            continue
        lv = fn(out, lg, lg.frame_cache, n, vid=f"l{k}", label=f"Leg {k} · {s.leg_share(k - 1)} · {lg.name}", idx=fr.index)
        lv.v["rule"] = f"{s.leg_share(k - 1)} of the money. " + lv.v["rule"]
        ins = fr[f"l{k}_w"].values > 0.0005
        lk = mix.b(f"in{k}", ins)
        mix.lane(lk, f"Leg {k} in")
        mix.check(f"Leg {k}", "", lk, lg.name)
    lines = [{"key": mix.s(f"w{k}", fr[f"l{k}_w"] * 100, 0), "name": f"Leg {k} (own target)", "color": ["#FF9800", "#26A69A", "#5B8DEF", "#E46AA8"][(k - 1) % 4],
              "width": 1, "step": True} for k in range(1, len(legs) + 1)]
    mix.chart(f"Each leg's own target in {p['trade']} (% of that leg's money)", lines, 90)
    kz = mix.s("size", fr["size"] * 100, 0)
    mlines = [{"key": kz, "name": f"Money in {p['trade']} %", "color": s.color, "width": 2, "step": True}]
    if "gold_w" in fr.columns and s.gold_sym():
        mlines.append({"key": mix.s("gold", fr["gold_w"] * 100, 0), "name": f"{s.gold_sym()} %", "color": "#F2C14E", "width": 1, "step": True})
    mix.chart(f"The mix · money in {p['trade']}" + (f" and {s.gold_sym()}" if s.gold_sym() else ""), mlines, 90)
    mix.check("Money", f"{{{kz}}}% in {p['trade']}" + (f" · {{{mlines[1]['key']}}}% in {s.gold_sym()}" if len(mlines) > 1 else ""), None, "each leg's own target, weighted by its value")
    mix.v["tv"] = ["Pick a leg to see its own indicators"]
    out["views"].insert(0, out["views"].pop(out["views"].index(mix.v)))
    out["t"] = [int(pd.Timestamp(x).timestamp()) for x in fr.index]
    del w


def build(s, now, rng="8M"):
    """Check-the-rule data for a strategy, or None when its type has none."""
    n = RANGE_DAYS.get(rng, 168)
    out = {"t": [], "views": [], "series": {}, "strategy": s.id, "range": rng}
    if s.type == "trend_split":
        trend_split(out, s, now, n)
    elif s.type == "split_mix":
        split_mix(out, s, now, n)
    elif s.type in VIEWS:
        full = s.frame(now)
        fr = _tail(full, n)
        VIEWS[s.type](out, s, full, n, idx=fr.index)
        out["t"] = [int(pd.Timestamp(x).timestamp()) for x in fr.index]
    else:
        return None
    for v in out["views"]:                                   # days where the rule and the bot disagree
        rk = next((ln["key"] for ln in v["lanes"] if ln["kind"] == "rule"), None)
        bk = next((ln["key"] for ln in v["lanes"] if ln["kind"] == "bot"), None)
        if rk and bk:
            a, b = out["series"][rk]["v"], out["series"][bk]["v"]
            v["mismatch"] = sum(1 for x, y in zip(a, b) if x != y)
    return out
