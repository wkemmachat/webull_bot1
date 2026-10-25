"""Weekly search for 2x single-stock ETFs (C2-7 Momentum 2x). It suggests; it never adds one by itself.

After each weekend's Nasdaq-100 ranking, every stock among the largest (the strategy's pool + 3, so new names are seen a
week early) that has no ETF in the strategy's "2x ETFs" list is looked up on Yahoo. A candidate must:
  * be an ETF whose name says 2x long/bull on that stock (not short, inverse, 1.5x or 3x);
  * move like 2x the stock: daily beta 1.7–2.3 and correlation ≥ 0.90 over the last 60 trading days;
  * have traded at least 63 days (about 3 months);
  * trade at least $2 million a day (20-day average; setting etf2x_min_adv);
  * have a bid/ask spread under 0.5% when Yahoo gives one.
A pass is sent to LINE and shown on the strategy page with Add / Dismiss. Add writes the pair into the strategy's list;
the user then runs Go-live → Test trade so Webull's permission is proven before real money uses it.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import basket, db, marketdata as md, notify
from . import strategies as S

log = logging.getLogger("etf2x")
NY = ZoneInfo("America/New_York")
EXTRA = 3
MIN_DAYS = 63
BETA = (1.7, 2.3)
MIN_CORR = 0.90
MAX_SPREAD_PCT = 0.5
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
ETF_RE = re.compile(r"^[A-Z]{1,6}$")        # US listings only (not TSLL.MX, NVDL-USD …)
_running: dict = {}


def min_adv() -> float:
    try:
        return float(db.get_setting("etf2x_min_adv") or 2_000_000)
    except ValueError:
        return 2_000_000.0


def _key(sid):
    return f"etf2x:{sid}"


def state(sid) -> dict:
    return db.get_state(_key(sid)) or {}


def applies(s) -> bool:
    return s is not None and s.type == "momentum_basket" and s.params.get("leverage") == "2x"


# ---------------------------------------------------------------- Yahoo (replaced in tests)
def _search(query: str) -> list:
    """Yahoo search → [{symbol, name, type}]."""
    if md.source() == "csv":
        return []
    import yfinance as yf
    out = []
    for q in yf.Search(query, max_results=15, news_count=0).quotes or []:
        out.append({"symbol": str(q.get("symbol") or "").upper(), "name": q.get("longname") or q.get("shortname") or "",
                    "type": str(q.get("quoteType") or "").upper()})
    return out


def _history(sym: str) -> pd.DataFrame | None:
    """About a year of daily closes and volumes (columns c, v), oldest first."""
    if md.source() == "csv":
        return None
    import yfinance as yf
    h = yf.Ticker(sym).history(period="1y", auto_adjust=True)
    if h is None or h.empty:
        return None
    h = h.rename(columns={"Close": "c", "Volume": "v"})[["c", "v"]]
    h.index = pd.to_datetime([d.strftime("%Y-%m-%d") for d in h.index])
    return h.dropna()


_memo: dict = {}


def _hist(sym):
    """_history once per symbol per search run."""
    if sym not in _memo:
        _memo[sym] = _history(sym)
    return _memo[sym]


def _spread_pct(sym: str) -> float | None:
    if md.source() == "csv":
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(sym).info or {}
        bid, ask = float(info.get("bid") or 0), float(info.get("ask") or 0)
        if bid > 0 and ask > bid:
            return (ask - bid) / ((ask + bid) / 2) * 100
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- checks
def name_ok(name: str, stock: str, company: str = "") -> bool:
    """The fund's name says 2x long/bull on this stock."""
    n = " " + re.sub(r"[^a-z0-9.%+\-]+", " ", (name or "").lower()) + " "
    if not re.search(r"(?<![\d.\-])2(\.0)?x\b|200%|\b2 x\b", n):
        return False
    if re.search(r"short|inverse|bear|-2x|-1x|\b1\.25x|\b1\.5x|\b1\.75x|\b3x\b|300%|-200%", n):
        return False
    words = [w for w in re.sub(r"[^a-z0-9 ]+", " ", (company or "").lower()).split() if len(w) > 2 and w not in
             ("inc", "corp", "corporation", "the", "class", "com", "company", "holdings", "group", "plc", "ltd", "platforms")]
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(stock.lower())}(?![a-z0-9])", n)) or (bool(words) and words[0] in n)


def verify(etf: str, stock: str, name: str = "") -> dict:
    """Numbers that prove a candidate behaves like a usable 2x ETF on the stock."""
    out = {"etf": etf, "name": name, "ok": False, "why": []}
    try:
        e, s = _hist(etf), _hist(stock)
    except Exception as ex:
        out["why"].append(f"no prices ({str(ex)[:60]})")
        return out
    if e is None or e.empty or s is None or s.empty:
        out["why"].append("no prices on Yahoo")
        return out
    out["days"] = int(len(e))
    out["since"] = str(e.index[0].date())
    j = pd.DataFrame({"e": e["c"].pct_change(), "s": s["c"].pct_change()}).dropna().tail(60)
    if len(j) >= 20 and j["s"].var() > 0:
        out["beta"] = round(float(j["e"].cov(j["s"]) / j["s"].var()), 2)
        out["corr"] = round(float(j["e"].corr(j["s"])), 3)
    out["adv"] = round(float((e["c"] * e["v"]).tail(20).mean()), 0)
    sp = _spread_pct(etf)
    out["spread"] = round(sp, 3) if sp is not None else None
    if out["days"] < MIN_DAYS:
        out["why"].append(f"too young ({out['days']} trading days, needs {MIN_DAYS})")
    if out.get("beta") is None:
        out["why"].append("not enough overlapping days to measure")
    elif not (BETA[0] <= out["beta"] <= BETA[1]) or out["corr"] < MIN_CORR:
        out["why"].append(f"does not move like 2x {stock} (beta {out['beta']}, correlation {out['corr']})")
    if out["adv"] < min_adv():
        out["why"].append(f"too little trading (${out['adv'] / 1e6:,.1f}M a day, needs ${min_adv() / 1e6:,.1f}M)")
    if sp is not None and sp > MAX_SPREAD_PCT:
        out["why"].append(f"spread too wide ({sp:.2f}%)")
    out["ok"] = not out["why"]
    return out


def candidates(stock: str) -> list:
    """ETFs whose names say 2x long on the stock. Yahoo matches whole phrases, and the funds are named like
    "GraniteShares 2x Long NVDA Daily ETF", "Direxion Daily TSLA Bull 2X Shares" or "Corgi AMD 2x Daily ETF",
    so the ticker is searched with "daily", "2x", "bull" and "long"."""
    seen, out = set(), []
    for q in (f"{stock} daily", f"{stock} 2x", f"{stock} bull", f"{stock} long"):
        try:
            res = _search(q)
        except Exception as e:
            log.warning("search %s: %s", q, e)
            continue
        for r in res:
            sym = r["symbol"]
            if sym in seen or sym == stock or r["type"] not in ("ETF", "MUTUALFUND", "") or not ETF_RE.match(sym):
                continue
            if name_ok(r["name"], stock):
                seen.add(sym)
                out.append(r)
    return out[:5]


# ---------------------------------------------------------------- the weekly scan
def scan(sid: str, send_line: bool = True, now=None) -> dict:
    s = S.get(sid)
    if not applies(s):
        raise ValueError("Only for a momentum strategy set to 2x")
    now = now or md.now_utc()
    _memo.clear()
    week, rk = basket.ranking_for(now.astimezone(NY).date())
    pool = int(s.params.get("pool", 12))
    top = (rk or [])[:pool + EXTRA]
    emap = s.etf_map()
    old = state(sid)
    dismissed = old.get("dismissed", {})
    prev = {k: (v.get("best") or {}).get("etf") for k, v in old.get("stocks", {}).items() if v.get("status") == "found"}
    stocks, new = {}, []
    for i, (stock, mc) in enumerate(top):
        row = {"rank": i + 1, "mcap": mc, "in_pool": i < pool}
        if stock in emap:
            row.update(status="mapped", etf=emap[stock])
        else:
            checked = [verify(c["symbol"], stock, c["name"]) for c in candidates(stock)]
            good = sorted([c for c in checked if c["ok"]], key=lambda c: -c.get("adv", 0))
            best = good[0] if good else None
            row["checked"] = checked
            if best and dismissed.get(stock) == best["etf"]:
                row.update(status="dismissed", best=best)
            elif best:
                row.update(status="found", best=best)
                if prev.get(stock) != best["etf"]:
                    new.append((stock, best))
            else:
                row["status"] = "none"
        stocks[stock] = row
    out = {"at": int(time.time()), "week": str(week) if week else None, "stocks": stocks, "dismissed": dismissed,
           "added": old.get("added", {})}
    db.set_state(_key(sid), out)
    _memo.clear()
    if new:
        lines = [f"• {st} → {b['etf']} ({b['name'] or 'ETF'}): beta {b.get('beta')}, ${b['adv'] / 1e6:,.0f}M a day, "
                 f"trading since {b['since']}" for st, b in new]
        msg = (f"{s.name}: new 2x ETF{'s' if len(new) > 1 else ''} found for this week's largest stocks.\n" + "\n".join(lines) +
               "\nOpen the strategy page to add or dismiss (nothing changes until you add it; then run a Test trade).")
        db.add_event("info", "strategy", f"{s.name}: new 2x ETF found", msg, strategy=sid)
        if send_line:
            notify.send("etf2x", msg, strategy=sid)
    else:
        db.add_event("info", "strategy", f"{s.name}: 2x ETF search done", f"{len(top)} stocks checked, nothing new", strategy=sid)
    return out


def scan_all(send_line=True, now=None):
    for s in S.all_instances():
        if applies(s):
            try:
                scan(s.id, send_line, now)
            except Exception as e:
                log.warning("2x ETF search %s: %s", s.id, e)
                db.add_event("warn", "strategy", f"{s.name}: 2x ETF search failed", str(e)[:300], strategy=s.id)


def start_scan(sid) -> dict:
    if md.source() == "csv":
        raise ValueError("The search needs real prices from Yahoo (this copy runs on demo data)")
    if _running.get(sid):
        return {"running": True}
    _running[sid] = True

    def go():
        try:
            scan(sid)
        except Exception as e:
            log.warning("2x ETF search %s: %s", sid, e)
            db.add_event("warn", "strategy", "2x ETF search failed", str(e)[:300], strategy=sid)
        finally:
            _running[sid] = False
    threading.Thread(target=go, name="etf2x", daemon=True).start()
    return {"running": True}


# ---------------------------------------------------------------- what you decide
def add(sid: str, stock: str, etf: str) -> dict:
    s = S.get(sid)
    if not applies(s):
        raise ValueError("Only for a momentum strategy set to 2x")
    stock, etf = str(stock or "").upper().strip(), str(etf or "").upper().strip()
    if not SYMBOL_RE.match(stock) or not ETF_RE.match(etf):
        raise ValueError("Enter the stock and the ETF ticker")
    emap = s.etf_map()
    if emap.get(stock) == etf:
        raise ValueError(f"{stock} already uses {etf}")
    if etf in emap.values():
        raise ValueError(f"{etf} is already used for another stock")
    emap[stock] = etf
    S.update(sid, params={"etf_map": ", ".join(f"{k}:{v}" for k, v in emap.items())})
    st = state(sid)
    st.setdefault("added", {})[stock] = {"etf": etf, "at": int(time.time())}
    if stock in st.get("stocks", {}):
        st["stocks"][stock].update(status="mapped", etf=etf)
    st.get("dismissed", {}).pop(stock, None)
    db.set_state(_key(sid), st)
    db.add_event("info", "strategy", f"{s.name}: {stock} is now held through {etf}",
                 "Added from the 2x ETF search. Run Go-live → Test trade for it before real money uses it.", strategy=sid)
    return {"ok": True, "etf_map": S.get(sid).params["etf_map"]}


def dismiss(sid: str, stock: str) -> dict:
    st = state(sid)
    row = st.get("stocks", {}).get(stock)
    if not row or not row.get("best"):
        raise ValueError("Nothing to dismiss for this stock")
    st.setdefault("dismissed", {})[stock] = row["best"]["etf"]
    row["status"] = "dismissed"
    db.set_state(_key(sid), st)
    return {"ok": True}


def view(sid: str) -> dict:
    s = S.get(sid)
    if not applies(s):
        return {"applies": False}
    st = state(sid)
    emap = s.etf_map()
    try:
        _, picks, _ = s.current_list()
    except Exception:
        picks = []
    rows = []
    for stock, r in (st.get("stocks") or {}).items():
        r = dict(r)
        if stock in emap:                      # the list may have changed since the scan
            r.update(status="mapped", etf=emap[stock])
        rows.append({"stock": stock, "picked": stock in picks, **r})
    return {"applies": True, "at": st.get("at"), "week": st.get("week"), "rows": rows, "running": bool(_running.get(sid)),
            "rules": {"min_days": MIN_DAYS, "beta": BETA, "min_corr": MIN_CORR, "min_adv": min_adv(), "max_spread": MAX_SPREAD_PCT},
            "can_scan": md.source() != "csv"}
