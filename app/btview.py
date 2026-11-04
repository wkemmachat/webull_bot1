"""Backtest page (every strategy side by side) and the extra analyses of a strategy's Backtest tab.

overview(mode)  — the table, the charts' weekly series, correlations and your money, built from the yearly
                  expected-returns check (no backtest runs: the page opens at once). Gold and silver use the research's
                  10 years (OANDA prices, app/research/weekly_research.json) while on their default settings, because
                  Yahoo keeps only about 2 years of hourly metals prices.
extra(sid)      — from the strategy's own backtest: 2,000 reshuffled decades (range of outcomes) and its return in good and
                  bad markets (the index above / below its 200-day average).
stress(sid)     — the same backtest with higher fees and, for daily strategies, every order one day late.
"""
import hashlib
import json
import math
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest as BT, db, expected, ledger
from . import strategies as S

RESEARCH_WEEKLY = Path(__file__).parent / "research" / "weekly_research.json"
FULL_YEARS = 9.5              # a series this long counts as "10 years"
BOOT_PATHS, BOOT_BLOCK = 2000, 13
STRESS = [("fee 0.25% a side", {"cost": 0.0025}), ("fee 0.50% a side", {"cost": 0.0050}), ("every order 1 day late", {"delay": 1})]
_lock = threading.Lock()
_extra_cache: dict = {}
_stress_cache: dict = {}
_research = None


def research_weekly() -> dict:
    global _research
    if _research is None:
        try:
            _research = json.loads(RESEARCH_WEEKLY.read_text())
        except Exception:
            _research = {"strategies": {}}
    return _research


def group_of(s) -> str:
    syms = set(x for x in s.trade_symbols() if x)
    if s.type == "momentum_basket" or "stocks" in syms:
        return "stocks"
    for g, keys in (("usd", {"USD"}), ("qld", {"QLD"}), ("rom", {"ROM"}), ("gold", {"UGL", "GLD"}), ("silver", {"AGQ", "SLV"})):
        if syms & keys:
            return g
    return "other"


def _weekly(w0: str, wv: list) -> pd.Series:
    return pd.Series(wv, index=pd.date_range(w0, periods=len(wv), freq="W-FRI"), dtype=float)


def _cagr(v: pd.Series, weeks: int | None = None):
    if weeks:
        if len(v) <= weeks:
            return None
        v = v.iloc[-weeks - 1:]
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    if yrs <= 0 or v.iloc[0] <= 0:
        return None
    return ((v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1) * 100 if yrs >= 1 else (v.iloc[-1] / v.iloc[0] - 1) * 100


def _years_up(v: pd.Series):
    """Full calendar years in the series that made money: (up, of)."""
    up = n = 0
    for y in sorted(set(v.index.year)):
        prev, cur = v[v.index.year < y], v[v.index.year == y]
        if prev.empty or len(cur) < 48:
            continue
        n += 1
        up += int(cur.iloc[-1] > prev.iloc[-1])
    return up, n


def overview(mode: str) -> dict:
    view = expected.view(mode)
    rw = research_weekly()
    by_id = {s.id: s for s in S.all_instances()}
    rows, series = [], {}
    for r in view["strategies"]:
        s = by_id.get(r["id"])
        if not s:
            continue
        own = view["weekly"].get(s.id)
        c = r.get("check") or {}
        src, ser = "bot", None
        if own:
            ser = _weekly(own["w0"], own["wv"])
        short = ser is None or (ser.index[-1] - ser.index[0]).days / 365.25 < FULL_YEARS
        res = rw["strategies"].get(s.id)
        if short and res and expected._same_settings(s):
            ser, src = _weekly(res["w0"], res["wv"]), "research"
        b = r.get("basis") or {}
        if src == "research":
            r10, dd10 = b.get("cagr"), b.get("maxdd")
        elif ser is not None and not short:
            r10, dd10 = c.get("cagr"), c.get("maxdd")
        else:
            r10, dd10 = None, c.get("maxdd")
        yrs = round((ser.index[-1] - ser.index[0]).days / 365.25, 1) if ser is not None else None
        below = float((ser < ser.cummax() * (1 - 1e-9)).mean() * 100) if ser is not None else None
        up, of = _years_up(ser) if ser is not None else (0, 0)
        ret_dd = round(r10 / abs(dd10), 2) if r10 is not None and dd10 else None
        val = r["value"] or 0.0
        v = ledger.value(mode, s.id)
        dip = r.get("dip") or {}
        rows.append({
            "id": s.id, "name": s.name, "color": s.color, "group": group_of(s), "control": (s.row or {}).get("control"),
            "idle": r.get("idle"), "timeframe": s.timeframe, "etf": ", ".join(x for x in s.trade_symbols() if x and x != "stocks") or "stocks",
            "value": round(val, 2), "src": src, "years": yrs,
            "r1": round(_cagr(ser, 52), 1) if ser is not None and _cagr(ser, 52) is not None else None,
            "r3": round(_cagr(ser, 156), 1) if ser is not None and _cagr(ser, 156) is not None else None,
            "r10": r10, "dd10": dd10, "ret_dd": ret_dd, "up": up, "of": of,
            "below": round(below) if below is not None else None,
            "now": dip.get("depth"), "pct": dip.get("pct"), "zone": dip.get("zone"),
            "dip": dip or None,
            "worst_usd": round(val * abs(dd10) / 100, 2) if val > 0 and dd10 else None,
            "holdings": {k: round(p["value"], 2) for k, p in v["positions"].items()}, "cash": round(v["cash"], 2)})
        if ser is not None:
            series[s.id] = ser
    # one weekly calendar for the charts: the last 10 years of Fridays
    end = max((x.index[-1] for x in series.values()), default=pd.Timestamp.now().normalize())
    idx = pd.date_range(end=end, periods=523, freq="W-FRI")
    out_series = {}
    for sid, ser in series.items():
        x = ser.reindex(idx, method="ffill", limit=2)
        x[x.index < ser.index[0]] = np.nan
        out_series[sid] = [None if pd.isna(y) else float(f"{y:.5g}") for y in x.values]
    rets = pd.DataFrame({sid: pd.Series(v, index=idx, dtype=float).pct_change(fill_method=None) for sid, v in out_series.items()})
    cm = rets.corr(min_periods=26)
    ids = list(out_series)
    corr = {"ids": ids, "m": [[None if pd.isna(cm.loc[a, b]) else round(float(cm.loc[a, b]), 2) for b in ids] for a in ids]}
    funded = [r for r in rows if r["value"] > 0.5]
    total = sum(r["value"] for r in funded)
    by_sym = {}
    for r in funded:
        for k, x in r["holdings"].items():
            by_sym[k] = by_sym.get(k, 0) + x
        if r["cash"] > 0.5:
            by_sym["cash"] = by_sym.get("cash", 0) + r["cash"]
    return {"mode": mode, "rows": rows, "dates": [str(d.date()) for d in idx], "series": out_series, "corr": corr,
            "summary": {"total": round(total, 2), "n": len(funded), "worst_usd": round(sum(r["worst_usd"] or 0 for r in funded), 2),
                        "by_symbol": {k: round(x, 2) for k, x in sorted(by_sym.items(), key=lambda kv: -kv[1])}},
            "check": view.get("check"), "research_note": research_weekly().get("about")}


# ---------------------------------------------------------------- a strategy's extra analyses
def _window(r) -> pd.Series:
    s = r["series"]
    ser = pd.Series(s["strategy"], index=pd.to_datetime(s["t"], unit="s"), dtype=float).dropna()
    cut = ser.index[-1] - pd.DateOffset(years=10)
    return ser[ser.index >= cut] if ser.index[0] <= cut + pd.Timedelta(days=20) else ser


def bootstrap(ser: pd.Series, seed: int, paths: int = BOOT_PATHS, block: int = BOOT_BLOCK) -> dict | None:
    """The strategy's own weekly returns cut into `block`-week pieces and put back together at random: `paths` decades
    as long as the window. Percentile paths (every 2nd week) and the spread of yearly return and worst fall."""
    wk = ser.resample("W-FRI").last().dropna()
    r = (wk / wk.shift(1) - 1).dropna().values
    n = len(r)
    if n < block * 4:
        return None
    rng = np.random.default_rng(seed)
    k = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(paths, k))
    take = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(paths, -1)[:, :n]
    eq = np.cumprod(1 + r[take], axis=1) * 10000
    yrs = n / 52.18
    cagr = (eq[:, -1] / 10000) ** (1 / yrs) - 1
    mdd = (eq / np.maximum.accumulate(eq, axis=1) - 1).min(axis=1)
    q = np.percentile(eq, [10, 50, 90], axis=0)
    sel = list(range(1, n, 2)) + [n - 1]
    act = (wk / wk.iloc[0] * 10000).values
    p = lambda x: round(float(x) * 100, 1)
    return {"weeks": n, "years": round(yrs, 1), "paths": paths, "block": block,
            "x": [round((i + 1) / n, 4) for i in sel], "p10": [round(float(q[0][i]), 0) for i in sel],
            "p50": [round(float(q[1][i]), 0) for i in sel], "p90": [round(float(q[2][i]), 0) for i in sel],
            "actual": [round(float(x), 0) for x in act[::2]] + ([round(float(act[-1]), 0)] if (len(act) - 1) % 2 else []),
            "cagr": {"p10": p(np.percentile(cagr, 10)), "p50": p(np.percentile(cagr, 50)), "p90": p(np.percentile(cagr, 90))},
            "end": {"p10": round(float(np.percentile(eq[:, -1], 10))), "p50": round(float(np.percentile(eq[:, -1], 50))),
                    "p90": round(float(np.percentile(eq[:, -1], 90)))},
            "fall": {"p50": p(np.median(mdd)), "p10": p(np.percentile(mdd, 10))},
            "chance": {"loss": p((cagr < 0).mean()), "fall30": p((mdd < -0.30).mean()), "fall40": p((mdd < -0.40).mean()),
                       "fall50": p((mdd < -0.50).mean())}}


def regimes(r) -> dict | None:
    """Return a year while the strategy's index was above / below its 200-day average (the day before), next to simply
    holding the traded ETF, over the whole backtest."""
    s = r["series"]
    t = pd.to_datetime(s["t"], unit="s")
    strat = pd.Series(s["strategy"], index=t, dtype=float)
    idx_sym = r.get("index") if r.get("index") in s["bench"] else (r.get("main") if r.get("main") in s["bench"] else None)
    if not idx_sym:
        return None
    ix = pd.Series(s["bench"][idx_sym], index=t, dtype=float)
    held = pd.Series(s["bench"][r["main"]], index=t, dtype=float) if r.get("main") in s["bench"] else None
    up = (ix > ix.rolling(200).mean()).shift(1)
    ok = up.notna() & ix.rolling(200).mean().shift(1).notna()
    if ok.sum() < 250:
        return None
    rs = strat.pct_change()
    rh = held.pct_change() if held is not None else None

    def ann(ret, mask):
        x = ret[mask & ok].dropna()
        if len(x) < 40:
            return None
        return round((float(np.prod(1 + x.values)) ** (252 / len(x)) - 1) * 100, 1)
    good, bad = up.fillna(False).astype(bool), (~up.fillna(True).astype(bool))
    return {"index": idx_sym, "etf": r["main"], "from": str(t[ok.values.argmax()].date()),
            "good": ann(rs, good), "bad": ann(rs, bad), "hgood": ann(rh, good) if rh is not None else None,
            "hbad": ann(rh, bad) if rh is not None else None, "bad_share": round(float((bad & ok).sum() / ok.sum()) * 100, 1)}


def extra(sid: str) -> dict:
    r = BT.run(sid)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    key = (sid, r.get("generated_at"))
    with _lock:
        if key in _extra_cache:
            return _extra_cache[key]
    ser, src = _window(r), "bot"
    # gold/silver: Yahoo has ~2 years of hourly prices; on default settings shuffle the research's 10 years instead
    res = research_weekly()["strategies"].get(sid)
    s = S.get(sid)
    if res and s and (ser.index[-1] - ser.index[0]).days / 365.25 < FULL_YEARS and expected._same_settings(s):
        ser, src = _weekly(res["w0"], res["wv"]), "research"
    seed = int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16)
    out = {"ok": True, "from": str(ser.index[0].date()), "to": str(ser.index[-1].date()), "src": src,
           "boot": bootstrap(ser, seed), "regime": regimes(r)}
    with _lock:
        if len(_extra_cache) > 60:
            _extra_cache.clear()
        _extra_cache[key] = out
    return out


def _headline(r):
    st = r.get("stats") or {}
    k = "10Y" if "10Y" in st else "MAX"
    x = (st.get(k) or {}).get("strategy") or {}
    return k, x.get("cagr"), x.get("maxdd")


def stress(sid: str) -> dict:
    base = BT.run(sid)
    if not base.get("ok"):
        return {"ok": False, "error": base.get("error")}
    key = (sid, base.get("generated_at"))
    with _lock:
        if key in _stress_cache:
            return _stress_cache[key]
    k, c0, d0 = _headline(base)
    rows = [{"t": f"as tested · fee {base.get('cost_pct', 0.11):.2f}% a side", "cagr": c0, "maxdd": d0, "base": True}]
    s = S.get(sid)
    for label, kw in STRESS:
        if kw.get("delay") and s.family != "regime":
            rows.append({"t": label, "cagr": None, "maxdd": None, "na": "4-hour and weekly strategies: not tested here"})
            continue
        try:
            r = BT.run(sid, **kw)
            _, c, d = _headline(r) if r.get("ok") else (k, None, None)
        except Exception as e:                        # a failed variant never breaks the tab
            c = d = None
            label = f"{label} (failed: {str(e)[:80]})"
        rows.append({"t": label, "cagr": c, "maxdd": d})
    out = {"ok": True, "window": k, "rows": rows, "at": int(time.time())}
    with _lock:
        if len(_stress_cache) > 60:
            _stress_cache.clear()
        _stress_cache[key] = out
    return out
