"""What the money in the strategies is really in: holdings grouped by what they follow (Nasdaq-100, US tech, semiconductors,
Nasdaq-100 stocks, gold, silver …), with the ETF's leverage. Several strategies often hold the same bet through different
ETFs (ROM, QLD and USD all rise and fall with US tech), so the Dashboard shows the total.

  value      dollars held in the group (cash and T-bills count as no risk)
  pct        share of the money in all strategies (strategy cash included)
  acts_like  value × leverage / all the money: 2x ETFs count twice ("moves like 120% in US tech")

US tech = Nasdaq-100 + US tech + semiconductors + Nasdaq-100 stocks: they fall together on a bad tech day (5 Nov 2026: IYW −6.9%,
QQQ −5.8%, SMH −8.6%). The "10% fall" line multiplies acts_like by 10%: a rough guide, since semiconductors usually move more
than the Nasdaq-100.
"""
from __future__ import annotations

# symbol → (group, leverage)
KNOWN = {
    "QQQ": ("nasdaq", 1), "QQQM": ("nasdaq", 1), "QLD": ("nasdaq", 2), "TQQQ": ("nasdaq", 3),
    "IYW": ("tech", 1), "XLK": ("tech", 1), "VGT": ("tech", 1), "ROM": ("tech", 2), "TECL": ("tech", 3),
    "SMH": ("semis", 1), "SOXX": ("semis", 1), "USD": ("semis", 2), "SOXL": ("semis", 3),
    "SPY": ("sp500", 1), "VOO": ("sp500", 1), "SSO": ("sp500", 2), "UPRO": ("sp500", 3),
    "GLD": ("gold", 1), "IAU": ("gold", 1), "GLDM": ("gold", 1), "UGL": ("gold", 2),
    "SLV": ("silver", 1), "AGQ": ("silver", 2),
    "BIL": ("tbills", 0), "SGOV": ("tbills", 0), "SHV": ("tbills", 0),
}
GROUPS = {   # key: (label, what it follows, colour)
    "nasdaq": ("Nasdaq-100", "QQQ", "#5B8DEF"),
    "tech": ("US tech", "IYW", "#20C997"),
    "semis": ("Semiconductors", "SMH", "#2E86DE"),
    "stocks": ("Nasdaq-100 stocks", "C2-7 picks", "#7FDBCA"),
    "sp500": ("S&P 500", "SPY", "#34508A"),
    "gold": ("Gold", "GLD", "#D4A017"),
    "silver": ("Silver", "SLV", "#9AA5B1"),
    "other": ("Other", "", "#B9852C"),
    "tbills": ("T-bills", "BIL", "#8FA98F"),
    "cash": ("Cash", "", "#C9D1C9"),
}
US_TECH = ("nasdaq", "tech", "semis", "stocks")
ORDER = list(GROUPS)


def _two_x_stock_etfs() -> dict:
    """2x single-stock ETF → its stock, from the C2-7 strategies' ETF lists."""
    from . import strategies as S
    out = {}
    for s in S.all_instances(include_archived=True):
        if hasattr(s, "etf_map"):
            try:
                out.update({etf: stock for stock, etf in s.etf_map().items()})
            except Exception:
                pass
    return out


def _members() -> set:
    try:
        from . import basket
        return set(basket.members())
    except Exception:
        return set()


def classify(sym, etfs=None, members=None):
    """(group, leverage) of a symbol."""
    if sym in KNOWN:
        return KNOWN[sym]
    etfs = _two_x_stock_etfs() if etfs is None else etfs
    if sym in etfs:
        return "stocks", 2
    members = _members() if members is None else members
    if sym in members:
        return "stocks", 1
    return "other", 1


def of_cards(cards) -> dict:
    """cards: the Dashboard's strategy cards ({id, name, color, cash, positions: {sym: {qty, value}}})."""
    etfs, members = _two_x_stock_etfs(), _members()
    groups, total = {}, 0.0
    for c in cards:
        cash = float(c.get("cash") or 0.0)
        total += cash
        if abs(cash) >= 0.005:
            g = groups.setdefault("cash", {"value": 0.0, "lev_value": 0.0, "symbols": {}, "strategies": {}})
            g["value"] += cash
            g["strategies"][c["id"]] = g["strategies"].get(c["id"], 0.0) + cash
        for sym, p in (c.get("positions") or {}).items():
            v = float(p.get("value") or 0.0)
            if not p.get("qty") or abs(v) < 0.005:
                continue
            total += v
            key, lev = classify(sym, etfs, members)
            g = groups.setdefault(key, {"value": 0.0, "lev_value": 0.0, "symbols": {}, "strategies": {}})
            g["value"] += v
            g["lev_value"] += v * lev
            sv = g["symbols"].setdefault(sym, {"value": 0.0, "lev": lev})
            sv["value"] += v
            g["strategies"][c["id"]] = g["strategies"].get(c["id"], 0.0) + v
    names = {c["id"]: (c["name"], c.get("color")) for c in cards}
    rows = []
    for key in sorted(groups, key=lambda k: (ORDER.index(k), -groups[k]["value"])):
        g = groups[key]
        label, follows, color = GROUPS[key]
        rows.append({"key": key, "label": label, "follows": follows, "color": color, "us_tech": key in US_TECH,
                     "value": round(g["value"], 2), "pct": (g["value"] / total) if total > 0.5 else None,
                     "acts_like": (g["lev_value"] / total) if total > 0.5 else None,
                     "symbols": [{"symbol": s, "value": round(x["value"], 2), "lev": x["lev"]}
                                 for s, x in sorted(g["symbols"].items(), key=lambda kv: -kv[1]["value"])],
                     "strategies": [{"id": sid, "name": names.get(sid, (sid, None))[0], "color": names.get(sid, (sid, None))[1],
                                     "value": round(v, 2)} for sid, v in sorted(g["strategies"].items(), key=lambda kv: -kv[1])]})
    tech = [r for r in rows if r["us_tech"]]
    tv = sum(r["value"] for r in tech)
    tl = sum(sum(s["value"] * s["lev"] for s in r["symbols"]) for r in tech)
    lev2 = sum(s["value"] for r in tech for s in r["symbols"] if s["lev"] >= 2)
    return {"total": round(total, 2), "rows": rows,
            "us_tech": {"value": round(tv, 2), "pct": (tv / total) if total > 0.5 else None,
                        "acts_like": (tl / total) if total > 0.5 else None,
                        "leveraged_pct": (lev2 / tv) if tv > 0.5 else None,
                        "fall10": round(-tl * 0.10, 2),
                        "strategies": len({s["id"] for r in tech for s in r["strategies"]})}}
