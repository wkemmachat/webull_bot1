"""Expected returns of the money in the strategies.

Per strategy: the research's yearly return (app/research/expected.json) minus a planning haircut (default 30%) is the
*typical* case. The weak / good cases (about 1 period in 10 below / above) come from the strategy's own volatility in the
bot's backtest, and the mix of strategies uses their correlations, so spreading money lowers the range. The total is the
sum of each strategy's own money growing at its own rate (each strategy is its own sub-account, never rebalanced).

Once a year the bot re-runs every strategy's backtest (the "check"), stores the volatility, worst/best 12 months and the
backtest's 10-year return next to the research, and sends LINE. The research numbers themselves are reviewed by hand
(update expected.json; docs and the Dashboard follow).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import db, ledger, notify
from . import strategies as S

log = logging.getLogger("expected")
FILE = Path(__file__).parent / "research" / "expected.json"
STATE = "expected_check"
Z = 1.2816                      # 10th / 90th percentile of a normal distribution
HORIZONS = (1, 2, 3)
CHECK_EVERY_DAYS = 365
EARLY_MONTHS = 3
_file_cache: dict = {}
_job = {"running": False, "started": None, "error": None, "done": None}
_job_lock = threading.Lock()


# ---------------------------------------------------------------- the research file
def load_file() -> dict:
    m = FILE.stat().st_mtime
    if _file_cache.get("m") != m:
        _file_cache.update(m=m, d=json.loads(FILE.read_text(encoding="utf-8")))
    return _file_cache["d"]


def haircut() -> float:
    """Planning haircut as a fraction (0.30 = take 30% off the research return)."""
    v = db.get_setting("expected_haircut_pct")
    try:
        pct = float(v) if v not in (None, "") else float(load_file().get("haircut_pct", 30))
    except ValueError:
        pct = 30.0
    return min(max(pct, 0.0), 90.0) / 100


def set_haircut(pct: float):
    pct = float(pct)
    if not 0 <= pct <= 90:
        raise ValueError("Pick a haircut between 0% and 90%")
    db.set_settings({"expected_haircut_pct": str(round(pct, 1))})


def get_plan() -> dict | None:
    """The ratio you planned in the panel's ratio planner (saved on the server, shared by every device)."""
    p = db.get_json_setting("expected_plan", None)
    return p if isinstance(p, dict) and p.get("pct") else None


def set_plan(pct: dict | None, total=None) -> dict | None:
    """pct: {strategy id: percent}; empty / None clears the saved ratio."""
    if not pct:
        db.set_settings({"expected_plan": ""})
        return None
    known = {s.id for s in S.all_instances()}
    clean = {}
    for sid, v in pct.items():
        if sid not in known:
            raise ValueError(f"Unknown strategy: {sid}")
        v = float(v)
        if not 0 <= v <= 100:
            raise ValueError("Each ratio must be between 0% and 100%")
        if v > 0:
            clean[sid] = round(v, 2)
    tot = sum(clean.values())
    if tot <= 0:
        raise ValueError("Give at least one strategy a ratio above 0%")
    if tot > 100.05:
        raise ValueError(f"The ratios add up to {tot:.1f}%; keep them at 100% or less")
    plan = {"pct": clean, "total": round(float(total), 2) if total else None, "saved_at": int(time.time())}
    db.set_settings({"expected_plan": plan})
    return plan


def review_info() -> dict:
    F = load_file()
    every = int(F.get("review_every_days", 365))
    rev = date.fromisoformat(F["reviewed"])
    today = datetime.now(timezone.utc).date()
    nxt = date.fromordinal(rev.toordinal() + every)
    return {"reviewed": F["reviewed"], "next": nxt.isoformat(), "due": today >= nxt, "every_days": every,
            "log": F.get("log", [])}


def _same_settings(s) -> bool:
    from .strategies import DEFAULTS
    seed = next((d for d in DEFAULTS if d[0] == s.id), None)
    return bool(seed) and type(s).merge_params(seed[4]) == s.params and s.row.get("type") == seed[1]


def basis(s, chk: dict | None) -> dict | None:
    """Where the strategy's expected yearly return comes from: the research (default settings) or, for a strategy with
    its own settings or without research, the bot's own backtest from the latest check."""
    spec = load_file()["strategies"].get(s.id)
    if spec and spec.get("expect") and _same_settings(s):
        e = spec["expect"]
        return {"cagr": e["cagr"], "maxdd": e.get("maxdd"), "basis": e.get("basis", "research"), "period": e.get("period"),
                "note": e.get("note"), "reviewed": spec.get("reviewed"), "doc": spec.get("doc"),
                "source": (spec.get("research") or {}).get("source")}
    c = (chk or {}).get("strategies", {}).get(s.id) or {}
    cg = c.get("cagr10") if c.get("cagr10") is not None else c.get("cagr_max")
    if c.get("ok") and cg is not None:
        why = "your own settings differ from the research" if spec else "no research for this strategy"
        return {"cagr": cg, "maxdd": c.get("maxdd10"), "basis": "bot backtest", "period": f"{c.get('from')} – {c.get('to')}",
                "note": f"From the bot's own backtest ({why}).", "reviewed": _day(chk.get("at")),
                "doc": spec.get("doc") if spec else None, "source": "Bot backtest"}
    return None


def _day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else None


# ---------------------------------------------------------------- the maths
def ranges(mu: float, sig: float | None) -> dict:
    """Total return over 1/2/3 years: typical (median) and weak/good (10th/90th percentile), as fractions."""
    out = {}
    for n in HORIZONS:
        lg = n * math.log1p(mu)
        r = {"typical": math.exp(lg) - 1, "a_year": mu}
        if sig is not None:
            r["weak"] = math.exp(lg - Z * sig * math.sqrt(n)) - 1
            r["good"] = math.exp(lg + Z * sig * math.sqrt(n)) - 1
        out[n] = r
    return out


def portfolio(items: list, corr: dict | None) -> dict | None:
    """items: [{id, amount, mu, sig}] (fractions). Each strategy's money grows on its own; the range uses the mix's
    volatility (weights × volatilities × correlations)."""
    its = [x for x in items if (x.get("amount") or 0) > 0.005 and x.get("mu") is not None]
    tot = sum(x["amount"] for x in its)
    if tot <= 0:
        return None
    ids = (corr or {}).get("ids") or []
    M = (corr or {}).get("m") or []
    w = {x["id"]: x["amount"] / tot for x in its}
    have_sig = all(x.get("sig") is not None for x in its)
    var = None
    if have_sig:
        var = 0.0
        for a in its:
            for b in its:
                if a["id"] == b["id"]:
                    rho = 1.0
                elif a["id"] in ids and b["id"] in ids:
                    rho = M[ids.index(a["id"])][ids.index(b["id"])]
                else:
                    rho = 0.5
                var += w[a["id"]] * w[b["id"]] * a["sig"] * b["sig"] * rho
    sp = math.sqrt(max(var, 0.0)) if var is not None else None
    out = {"amount": round(tot, 2), "vol": sp, "periods": {}}
    for n in HORIZONS:
        g = sum(w[x["id"]] * (1 + x["mu"]) ** n for x in its)
        r = {"typical": g - 1, "a_year": g ** (1 / n) - 1, "usd": tot * g}
        if sp is not None:
            r["weak"] = g * math.exp(-Z * sp * math.sqrt(n)) - 1
            r["good"] = g * math.exp(Z * sp * math.sqrt(n)) - 1
            r["weak_usd"], r["good_usd"] = tot * (1 + r["weak"]), tot * (1 + r["good"])
        out["periods"][n] = r
    out["a_year"] = sum(w[x["id"]] * x["mu"] for x in its)
    return out


def mix_fall(items: list, chk: dict | None) -> dict | None:
    """Worst fall of today's split in the backtest, on weekly closes over the weeks every funded strategy has data."""
    its = [x for x in items if (x.get("amount") or 0) > 0.005]
    st = (chk or {}).get("strategies", {})
    sers = {}
    for x in its:
        c = st.get(x["id"]) or {}
        if not c.get("ok") or not c.get("wv"):
            return None
        idx = pd.date_range(c["w0"], periods=len(c["wv"]), freq="W-FRI")
        sers[x["id"]] = pd.Series(c["wv"], index=idx)
    if not sers:
        return None
    df = pd.DataFrame(sers).dropna()
    if len(df) < 26:
        return None
    tot = sum(x["amount"] for x in its)
    v = sum(df[x["id"]] / df[x["id"]].iloc[0] * x["amount"] / tot for x in its)
    dd = v / v.cummax() - 1
    worst_each = [(st[x["id"]].get("maxdd10") or 0) * x["amount"] / tot for x in its]
    return {"maxdd": round(float(dd.min()) * 100, 1), "from": str(df.index[0].date()), "to": str(df.index[-1].date()),
            "at": str(dd.idxmin().date()), "all_at_once": round(sum(worst_each), 1)}


# ---------------------------------------------------------------- real vs expected
def _flows(mode, sid):
    rows = db.rows("SELECT kind, strategy, other, COALESCE(done_amount, amount) a, COALESCE(done_at, t) t FROM money "
                   "WHERE mode=? AND status='done' AND kind IN ('add','withdraw','move') AND (strategy=? OR other=?) ORDER BY t",
                   (mode, sid, sid))
    out = []
    for r in rows:
        a = float(r["a"] or 0)
        if r["kind"] == "add" and r["strategy"] == sid:
            out.append((r["t"], a))
        elif r["kind"] == "withdraw" and r["strategy"] == sid:
            out.append((r["t"], -a))
        elif r["kind"] == "move":
            if r["strategy"] == sid:
                out.append((r["t"], -a))
            elif r["other"] == sid:
                out.append((r["t"], a))
    return out


def track(mode, sid, mu, sig, value_now, now_ts=None) -> dict | None:
    """What the money put in would be worth now at the expected rate (and its weak/good range) vs its real value."""
    if mu is None:
        return None
    flows = _flows(mode, sid)
    if not flows:
        return None
    now_ts = now_ts or time.time()
    exp = weak = good = net = 0.0
    for t, a in flows:
        yrs = max(0.0, (now_ts - t) / (365.25 * 86400))
        lg = yrs * math.log1p(mu)
        exp += a * math.exp(lg)
        net += a
        if sig is not None:
            s = Z * sig * math.sqrt(yrs)
            weak += a * math.exp(lg - s)               # one market scenario for every flow
            good += a * math.exp(lg + s)
    months = (now_ts - flows[0][0]) / (30.44 * 86400)
    if months < EARLY_MONTHS:
        status = "early"
    elif value_now >= exp:
        status = "ahead"
    elif sig is None or value_now >= weak:
        status = "behind"
    else:
        status = "below"
    out = {"since": _day(flows[0][0]), "months": round(months, 1), "net_in": round(net, 2), "value": round(value_now, 2),
           "expected": round(exp, 2), "status": status,
           "real_ret": (value_now / net - 1) if net > 0 else None, "exp_ret": (exp / net - 1) if net > 0 else None}
    if sig is not None:
        out["weak"], out["good"] = round(weak, 2), round(good, 2)
    return out


TRACK_TEXT = {"early": "Too early to judge (under 3 months)", "ahead": "Ahead of the expected return",
              "behind": "Behind the expected return, inside the normal range", "below": "Below the weak case: worth a look"}


# ---------------------------------------------------------------- the yearly check
def _one(s, now=None) -> dict:
    from . import backtest
    try:
        r = backtest.run(strat=s, now=now)
    except Exception as e:                                   # a check never crashes the bot
        return {"ok": False, "error": str(e)[:300]}
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    ser = pd.Series(r["series"]["strategy"], index=pd.to_datetime(r["series"]["t"], unit="s"), dtype=float).dropna()
    try:                                                      # worst fall / longest underwater for the strategy cards
        from . import perf
        dd = perf.drawdowns([x.date() for x in ser.index], list(ser.values), top=1)
        if dd:
            db.set_state(f"ddsum:{s.id}", {"at": int(time.time()), "worst": dd["worst"], "longest": dd["longest"], "from": dd["from"]})
    except Exception as e:
        log.warning("drawdown summary %s: %s", s.id, e)
    ser = ser[ser.index >= ser.index[-1] - pd.DateOffset(years=10)]
    wk = ser.resample("W-FRI").last().ffill().dropna()      # one value every Friday, no gaps (dates are rebuilt from w0)
    if len(wk) < 20:
        return {"ok": False, "error": "less than 20 weeks of backtest"}
    lr = np.log(wk).diff().dropna()
    y12 = (wk / wk.shift(52) - 1).dropna()
    st = r["stats"]
    ten = st.get("10Y", {}).get("strategy") or {}
    mx = st.get("MAX", {}).get("strategy") or {}
    first = st.get("10Y") and "10Y" or "MAX"
    return {"ok": True, "from": str(ser.index[0].date()), "to": str(ser.index[-1].date()), "years": round((ser.index[-1] - ser.index[0]).days / 365.25, 1),
            "vol": round(float(lr.std() * math.sqrt(52)) * 100, 2), "cagr10": ten.get("cagr"), "cagr_max": mx.get("cagr"),
            "maxdd10": (st[first]["strategy"] or {}).get("maxdd"),
            "worst12": round(float(y12.min()) * 100, 1) if len(y12) else None,
            "best12": round(float(y12.max()) * 100, 1) if len(y12) else None,
            "w0": str(wk.index[0].date()), "wv": [round(float(x), 2) for x in wk.values]}


def _corr(res: dict) -> dict:
    sers = {}
    for sid, c in res.items():
        if c.get("ok"):
            idx = pd.date_range(c["w0"], periods=len(c["wv"]), freq="W-FRI")
            sers[sid] = np.log(pd.Series(c["wv"], index=idx)).diff()
    ids = list(sers)
    if not ids:
        return {"ids": [], "m": []}
    C = pd.DataFrame(sers).corr(min_periods=26).reindex(index=ids, columns=ids).fillna(0.5).values
    np.fill_diagonal(C, 1.0)
    vals, vecs = np.linalg.eigh((C + C.T) / 2)                # keep the matrix valid (no negative variance)
    C = vecs @ np.diag(np.clip(vals, 1e-6, None)) @ vecs.T
    d = np.sqrt(np.diag(C))
    C = C / np.outer(d, d)
    return {"ids": ids, "m": [[round(float(x), 3) for x in row] for row in C]}


def fingerprint() -> str:
    """Changes when the backtest fee or any strategy's settings change: the stored check is then out of date."""
    from . import backtest
    raw = json.dumps([round(backtest.cost_setting(), 6), sorted([s.id, s.type, s.params] for s in S.all_instances())],
                     sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def stale() -> bool:
    chk = db.get_state(STATE)
    return bool(chk) and chk.get("fp") != fingerprint()


def refresh(by="manual", send_line=True, now=None) -> dict:
    from . import backtest
    fp = fingerprint()
    res = {s.id: _one(s, now) for s in S.all_instances()}
    prev = db.get_state(STATE) or {}
    out = {"at": int(time.time()), "by": by, "strategies": res, "corr": _corr(res), "fp": fp,
           "cost_pct": round(backtest.cost_setting() * 100, 4)}
    db.set_state(STATE, out)
    hist = db.get_state("expected_check_log") or []
    hist.append({"at": out["at"], "by": by, "cagr10": {k: v.get("cagr10") for k, v in res.items() if v.get("ok")}})
    db.set_state("expected_check_log", hist[-20:])
    msg = summary_text(out, prev)
    db.add_event("info", "strategy", "Expected returns: yearly check done" if by == "yearly" else "Expected returns: check done", msg)
    if send_line:
        notify.send("review", msg, title="Expected returns check")
    return out


def summary_text(chk, prev=None) -> str:
    h = haircut()
    lines, flag = [], []
    for s in S.all_instances():
        c = chk["strategies"].get(s.id) or {}
        b = basis(s, chk)
        if not c.get("ok"):
            lines.append(f"• {s.name}: backtest failed ({c.get('error')})")
            continue
        bt = c.get("cagr10") if c.get("cagr10") is not None else c.get("cagr_max")
        plan = b["cagr"] * (1 - h) if b else None
        was = ((prev or {}).get("strategies", {}).get(s.id) or {}).get("cagr10")
        t = f"• {s.name}: research {b['cagr']:.1f}% → plan {plan:.1f}%, bot backtest now {bt:.1f}% a year" if b and bt is not None else f"• {s.name}: bot backtest {bt}%"
        if was is not None and bt is not None:
            t += f" (last check {was:.1f}%)"
        lines.append(t)
        if plan is not None and bt is not None and bt < plan:
            flag.append(s.name)
    rv = review_info()
    head = f"Planning haircut {h * 100:.0f}%. Research reviewed {rv['reviewed']}" + (" — review due" if rv["due"] else f", next review {rv['next']}") + "."
    tail = (f"\nBelow the planning number: {', '.join(flag)}. Ask Claude for the yearly review of these strategies."
            if flag else "\nEvery strategy's backtest is at or above its planning number.")
    return head + "\n" + "\n".join(lines) + tail


def start_check(by="manual", send_line=True) -> dict:
    with _job_lock:
        if _job["running"]:
            return status()
        _job.update(running=True, started=int(time.time()), error=None)

    def run():
        try:
            refresh(by, send_line)
            _job["done"] = int(time.time())
        except Exception as e:
            log.exception("expected-returns check")
            _job["error"] = str(e)[:300]
            db.add_event("error", "strategy", "Expected-returns check failed", str(e)[:300])
        finally:
            _job["running"] = False
    threading.Thread(target=run, name="expected-check", daemon=True).start()
    return status()


def status() -> dict:
    chk = db.get_state(STATE) or {}
    return {"running": _job["running"], "started": _job["started"], "error": _job["error"], "at": chk.get("at"), "by": chk.get("by"),
            "cost_pct": chk.get("cost_pct"), "stale": bool(chk) and chk.get("fp") != fingerprint()}


def recheck_if_stale() -> bool:
    """Re-run the check (no LINE) when the fee or a strategy's settings changed since the last one."""
    if stale() and not _job["running"]:
        start_check("settings changed", send_line=False)
        return True
    return False


def daily(now=None):
    """Once a day: run the first check (no LINE) or the yearly one; remind once a month while the review is due."""
    chk = db.get_state(STATE)
    if not chk:
        start_check("first", send_line=False)
    elif time.time() - chk.get("at", 0) > CHECK_EVERY_DAYS * 86400:
        start_check("yearly", send_line=True)
    rv = review_info()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if rv["due"] and db.get_state("expected_remind") != month:
        db.set_state("expected_remind", month)
        notify.send("review", f"The yearly review of the expected returns is due (last reviewed {rv['reviewed']}). "
                              "Ask Claude: \"do the yearly expected-return review\" — it re-checks the research numbers "
                              "and updates the documents.", title="Expected returns review due")


# ---------------------------------------------------------------- what the pages show
def view(mode: str) -> dict:
    chk = db.get_state(STATE) or {}
    h = haircut()
    rows, items = [], []
    for s in S.all_instances():
        v = ledger.value(mode, s.id)
        b = basis(s, chk)
        c = chk.get("strategies", {}).get(s.id) or {}
        mu = b["cagr"] * (1 - h) / 100 if b else None
        sig = c["vol"] / 100 if c.get("ok") and c.get("vol") else None
        bt = c.get("cagr10") if c.get("cagr10") is not None else c.get("cagr_max")
        tr = track(mode, s.id, mu, sig, v["value"])
        if tr:
            tr["text"] = TRACK_TEXT[tr["status"]]
        rows.append({"id": s.id, "name": s.name, "color": s.color, "value": round(v["value"], 2), "net_in": round(v["net_in"] or 0, 2),
                     "idle": (s.row or {}).get("control") == "stopped" and abs(v["value"] or 0) < 0.5 and not v["positions"],
                     "basis": b, "mu": mu, "vol": sig,
                     "ranges": ranges(mu, sig) if mu is not None else None,
                     "check": {"ok": c.get("ok"), "error": c.get("error"), "cagr": bt, "years": c.get("years"), "from": c.get("from"),
                               "worst12": c.get("worst12"), "best12": c.get("best12"), "maxdd": c.get("maxdd10")} if c else None,
                     "track": tr})
        items.append({"id": s.id, "amount": max(0.0, v["value"]), "mu": mu, "sig": sig})
    corr = chk.get("corr")
    port = portfolio(items, corr)
    tracked = [r["track"] for r in rows if r["track"]]
    total_track = None
    if tracked:
        e = sum(t["expected"] for t in tracked)
        val = sum(t["value"] for t in tracked)
        net = sum(t["net_in"] for t in tracked)
        months = max(t["months"] for t in tracked)
        wk = sum(t.get("weak", t["expected"]) for t in tracked)
        st_all = "early" if months < EARLY_MONTHS else "ahead" if val >= e else "behind" if val >= wk else "below"
        total_track = {"value": round(val, 2), "expected": round(e, 2), "net_in": round(net, 2), "weak": round(wk, 2),
                       "good": round(sum(t.get("good", t["expected"]) for t in tracked), 2), "months": months, "status": st_all,
                       "text": TRACK_TEXT[st_all], "real_ret": val / net - 1 if net > 0 else None, "exp_ret": e / net - 1 if net > 0 else None}
    weekly = {sid: {"w0": c["w0"], "wv": c["wv"], "maxdd": c.get("maxdd10")} for sid, c in chk.get("strategies", {}).items() if c.get("ok")}
    return {"mode": mode, "haircut_pct": round(h * 100, 1), "z": Z, "horizons": list(HORIZONS), "strategies": rows,
            "plan": get_plan(), "unassigned": round(max(0.0, ledger.pool_cash(mode)), 2),
            "portfolio": port, "fall": mix_fall(items, chk), "track": total_track, "corr": corr, "weekly": weekly,
            "check": status(), "review": review_info()}


# ---------------------------------------------------------------- docs
def _pct(x, d=1):
    return "—" if x is None else f"{x:+.{d}f}%"


def doc_block(sid: str) -> str:
    """The 'Expected return' table on a strategy's page (filled in when the page is opened)."""
    s = S.get(sid)
    spec = load_file()["strategies"].get(sid)
    if not s and not spec:
        return "*No expected return for this strategy.*"
    chk = db.get_state(STATE) or {}
    h = haircut()
    b = basis(s, chk) if s else {"cagr": spec["expect"]["cagr"], "basis": spec["expect"].get("basis"), "period": spec["expect"].get("period"),
                                 "reviewed": spec.get("reviewed"), "note": spec["expect"].get("note"), "maxdd": spec["expect"].get("maxdd")}
    if not b:
        return "*No expected return yet: it appears after the first check (Dashboard → Expected return → Re-run the check).*"
    c = chk.get("strategies", {}).get(sid) or {}
    mu = b["cagr"] * (1 - h) / 100
    sig = c["vol"] / 100 if c.get("ok") and c.get("vol") else None
    R = ranges(mu, sig)
    name = s.name if s else sid
    out = [f"**{name}** · {b['basis']} {b['cagr']:.1f}% a year ({b.get('period') or ''}) − {h * 100:.0f}% planning haircut = "
           f"**{mu * 100:.1f}% a year**. Reviewed {b.get('reviewed') or '—'}.", "",
           "| Over | Weak case (1 in 10 worse) | Typical | Good case (1 in 10 better) | $10,000 becomes (typical) |", "|---|---|---|---|---|"]
    for n in HORIZONS:
        r = R[n]
        wk = _pct(r["weak"] * 100) if "weak" in r else "—"
        gd = _pct(r["good"] * 100) if "good" in r else "—"
        out.append(f"| {n} year{'s' if n > 1 else ''} | {wk} | {_pct(r['typical'] * 100)} | {gd} | ${10000 * (1 + r['typical']):,.0f} |")
    out.append("")
    if c.get("ok"):
        out.append(f"Range from the bot backtest's volatility ({c['vol']:.0f}% a year, {c.get('years')} years of data). In that backtest the worst "
                   f"12 months were {_pct(c.get('worst12'))} and the best {_pct(c.get('best12'))}; its 10-year return is "
                   f"{_pct(c.get('cagr10') if c.get('cagr10') is not None else c.get('cagr_max'))} a year (check of {_day(chk.get('at'))}).")
    else:
        out.append("The weak / good range appears after the bot's first check of the backtests.")
    if b.get("note"):
        out += ["", f"*{b['note']}*"]
    return "\n".join(out)


def doc_table() -> str:
    """All strategies, for Docs → Expected returns."""
    chk = db.get_state(STATE) or {}
    h = haircut()
    out = [f"Planning haircut now: **{h * 100:.0f}%** (Dashboard → Expected return). Last backtest check: {_day(chk.get('at')) or 'not run yet'}.", "",
           "| Strategy | Basis | Research a year | Plan a year | 1 year weak / typical / good | Bot backtest now | Reviewed |",
           "|---|---|---|---|---|---|---|"]
    for s in S.all_instances():
        b = basis(s, chk)
        c = chk.get("strategies", {}).get(s.id) or {}
        if not b:
            out.append(f"| {s.name} | — | — | — | after the first check | — | — |")
            continue
        mu = b["cagr"] * (1 - h) / 100
        sig = c["vol"] / 100 if c.get("ok") and c.get("vol") else None
        r = ranges(mu, sig)[1]
        bt = c.get("cagr10") if c.get("cagr10") is not None else c.get("cagr_max")
        rng = f"{_pct(r['weak'] * 100, 0)} / {_pct(r['typical'] * 100, 0)} / {_pct(r['good'] * 100, 0)}" if sig is not None else f"— / {_pct(r['typical'] * 100, 0)} / —"
        out.append(f"| {s.name} | {b['basis']} | {b['cagr']:.1f}% | **{mu * 100:.1f}%** | {rng} | {_pct(bt) if bt is not None else '—'} | {b.get('reviewed') or '—'} |")
    return "\n".join(out)


def doc_log() -> str:
    rv = review_info()
    out = [f"Research numbers reviewed **{rv['reviewed']}** · next review **{rv['next']}**" + (" (due now)" if rv["due"] else "") + ".", ""]
    out += [f"- **{x['date']}** — {x['what']}" for x in reversed(rv["log"])]
    hist = db.get_state("expected_check_log") or []
    if hist:
        out += ["", "Backtest checks run by the bot: " + ", ".join(f"{_day(x['at'])} ({x['by']})" for x in hist[-6:]) + "."]
    return "\n".join(out)


def fill_doc(md_text: str) -> str:
    import re

    def rep(m):
        key = m.group(1)
        try:
            if key == "all":
                return doc_table()
            if key == "log":
                return doc_log()
            return doc_block(key)
        except Exception as e:                                # a doc never fails to open
            log.warning("expected doc %s: %s", key, e)
            return "*Expected return not available right now.*"
    return re.sub(r"<!--expected:([a-z0-9_]+)-->", rep, md_text)
