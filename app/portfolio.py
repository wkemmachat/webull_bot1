"""Portfolio page: all the money in one mode, together.

  mix        each strategy's share now next to the ratio you planned (Expected return → ratio planner), and the Moves
             that would bring it back (nothing moves until you press Move)
  exposure   what the money holds underneath, by market (two strategies holding USD both count as semiconductors 2x)
  backtest   weekly backtest values of every strategy (from the expected-returns check): the page combines them for any
             split in the browser, "each strategy's money grows on its own" (sub-accounts are never rebalanced)
  corr       correlations of weekly backtest returns
  real       the real result since the first money, time-weighted (deposits and withdrawals are not gains)
"""
from __future__ import annotations

import time

from . import db, execution, expected, ledger, marketdata as md, perf
from . import strategies as S

MIN_MOVE = 50.0                  # smaller gaps are not worth a move

MARKETS = {"QLD": "Nasdaq-100 2x", "QQQ": "Nasdaq-100", "USD": "Semiconductors 2x", "SMH": "Semiconductors",
           "ROM": "Technology 2x", "IYW": "Technology", "GLD": "Gold", "UGL": "Gold 2x", "AGQ": "Silver 2x", "SLV": "Silver",
           "BIL": "T-bills", "SGOV": "T-bills"}
MARKET_COLOR = {"Nasdaq-100 2x": "#5B8DEF", "Semiconductors 2x": "#B084F5", "Technology 2x": "#20C997", "Gold": "#E0B04B",
                "Gold 2x": "#C99A2E", "Silver 2x": "#9AA7B8", "T-bills": "#7C8798", "Big tech stocks": "#E8875A",
                "Cash in strategies": "#4B5563", "Bot unassigned": "#374151"}


def market_of(sym: str) -> str:
    if sym in MARKETS:
        return MARKETS[sym]
    if sym in execution.single_stock_etfs():
        return "Big tech stocks"
    return "Big tech stocks" if sym.isalpha() and len(sym) <= 5 else sym


def suggest_moves(rows: list, unassigned: float) -> list:
    """Greedy: bot unassigned first, then from the most over-weight to the most under-weight strategy."""
    under = sorted(([r["id"], r["gap"]] for r in rows if r["gap"] is not None and r["gap"] >= MIN_MOVE), key=lambda x: -x[1])
    over = sorted(([r["id"], -r["gap"]] for r in rows if r["gap"] is not None and -r["gap"] >= MIN_MOVE), key=lambda x: -x[1])
    out = []
    pool = max(0.0, unassigned)
    for u in under:
        if pool < MIN_MOVE:
            break
        a = min(pool, u[1])
        if a >= MIN_MOVE:
            out.append({"kind": "give", "to": u[0], "amount": round(a, 2)})
            pool -= a
            u[1] -= a
    for o in over:
        for u in under:
            if o[1] < MIN_MOVE:
                break
            a = min(o[1], u[1])
            if a >= MIN_MOVE:
                out.append({"kind": "move", "from": o[0], "to": u[0], "amount": round(a, 2)})
                o[1] -= a
                u[1] -= a
    return out


def view(mode: str) -> dict:
    plan = expected.get_plan()
    pct = (plan or {}).get("pct") or {}
    strats = S.all_instances()
    syms = set()
    for s in strats:
        syms |= set(ledger.get(mode, s.id)["holdings"])
    px = md.prices(syms) if syms else {}
    rows, markets = [], {}
    for s in strats:
        v = ledger.value(mode, s.id, px)
        ap = execution.active_plan(mode, s.id)
        if abs(v["value"]) < 0.5 and not v["positions"] and not pct.get(s.id) and not ap:
            continue
        for sym, p in v["positions"].items():
            m = market_of(sym)
            markets[m] = markets.get(m, 0.0) + p["value"]
        if v["cash"] > 0.005:
            markets["Cash in strategies"] = markets.get("Cash in strategies", 0.0) + v["cash"]
        rows.append({"id": s.id, "name": s.name, "color": s.color, "control": (s.row or {}).get("control"), "value": round(v["value"], 2),
                     "cash": round(v["cash"], 2), "net_in": round(v["net_in"] or 0, 2), "pnl": round(v["pnl"], 2), "ret": v["ret"],
                     "holds": {k: round(p["value"], 2) for k, p in v["positions"].items()}, "plan_pct": pct.get(s.id, 0.0),
                     "running": bool(ap)})
    total = sum(r["value"] for r in rows)
    unassigned = max(0.0, ledger.pool_cash(mode))
    base = total + unassigned
    for r in rows:
        r["now_pct"] = r["value"] / total * 100 if total > 0 else 0.0
        r["target"] = round(r["plan_pct"] / 100 * base, 2) if plan else None
        r["gap"] = round(r["target"] - r["value"], 2) if plan else None
    if unassigned > 0.5:
        markets["Bot unassigned"] = unassigned
    tot_m = sum(markets.values()) or 1.0
    exposure = sorted(({"market": k, "usd": round(x, 2), "pct": x / tot_m * 100, "color": MARKET_COLOR.get(k, "#6B7280")}
                       for k, x in markets.items()), key=lambda m: -m["usd"])

    chk = db.get_state(expected.STATE) or {}
    series = {}
    for sid, c in (chk.get("strategies") or {}).items():
        if c.get("ok") and c.get("wv"):
            s = S.get(sid)
            if not s:
                continue
            series[sid] = {"name": s.name, "color": s.color, "w0": c["w0"], "wv": c["wv"], "m0": c.get("m0"), "mv": c.get("mv")}

    days, idx = perf.live_index(mode, "*")
    real = None
    if len(idx) >= 2:
        peak, worst = idx[0], 0.0
        for x in idx:
            peak = max(peak, x)
            worst = min(worst, x / peak - 1)
        real = {"from": str(days[0]), "days": [str(d) for d in days], "idx": [round(x, 5) for x in idx],
                "ret": idx[-1] - 1, "worst": worst, "now_dd": idx[-1] / max(idx) - 1}
    return {"mode": mode, "at": int(time.time()), "rows": rows, "total": round(total, 2), "unassigned": round(unassigned, 2),
            "plan": plan, "moves": suggest_moves(rows, unassigned) if plan else [], "exposure": exposure,
            "series": series, "corr": chk.get("corr") or {"ids": [], "m": []}, "check_at": chk.get("at"),
            "check_full": all(x.get("mv") for x in series.values()) if series else False, "real": real,
            "haircut_pct": round(expected.haircut() * 100, 1)}
