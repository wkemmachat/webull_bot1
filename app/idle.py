"""Idle cash in a strategy: money it holds but does not use yet, why, and what "Invest now" / "Top up now" would buy.

Two kinds of idle cash:
  waiting  money added with "wait for the next buy signal" (stays cash until the strategy's next BUY)
  band     cash left over because the gap to the target is inside the strategy's rebalance band (e.g. a small top-up:
           2x Semis with $152 of $2,545 = 6% < its 10% band). The bot uses it at the next signal or a bigger gap.
Top up now buys toward today's target with that cash only (it never sells), as a normal split plan.
"""
from __future__ import annotations

import json

from . import db, execution, ledger, marketdata as md
from . import strategies as S

SHOW_MIN_USD = 20.0           # smaller leftovers are not worth a box


def _state(sid) -> dict:
    r = db.one("SELECT * FROM strategy_state WHERE strategy=?", (sid,))
    if not r:
        return {}
    r = dict(r)
    r["target"] = json.loads(r["target"] or "{}")
    r["detail"] = json.loads(r["detail"] or "{}")
    return r


def _parking(s) -> set:
    out = set(s.cash_target() or {})
    for k in ("off_symbol", "cash_symbol", "gold_etf", "cash_etf"):
        if s.params.get(k):
            out.add(s.params[k])
    if hasattr(s, "parking"):
        try:
            out |= set(s.parking())
        except Exception:
            pass
    return out


def is_in(s, target: dict) -> bool:
    """The strategy holds (or wants) its trading ETF now, not only T-bills / gold parking / cash."""
    park = _parking(s)
    return any(w > 0.0005 and k not in park for k, w in (target or {}).items())


def next_buy_text(s, st: dict) -> str:
    """Plain words: what the strategy's next BUY signal is from here."""
    p, det, state = s.params, st.get("detail") or {}, st.get("state")
    if s.family == "regime":
        sig, ma = p.get("signal"), p.get("ma_days")
        if state == "off":
            return (f"The next buy is {sig} closing above its SMA{ma}" + (f" ({det['sma_long']:,.2f}; last close {det['close']:,.2f})"
                    if det.get("sma_long") and det.get("close") else "") + ". That turns the trend on (1x or 2x).")
        if state == "1x":
            return (f"The next buy is a step up to 2x: SMA{p.get('confirm_days')} crossing above SMA{ma} (the uptrend confirmed) "
                    f"while the {p.get('vol_days')}-day volatility stays under {p.get('vol_gate_pct')}%.")
        if state == "0.5x":
            v = det.get("vol")
            return (f"The next buy is a step up to 2x: the {p.get('vol_days')}-day volatility falling under {p.get('vol_gate_pct')}%"
                    + (f" (now {v * 100:.1f}%)" if v else "") + ".")
        return ("It is already at full size (2x), so its next buy signal needs a step down first and then a step up again "
                "(for example 2x → 0.5x → 2x), which can take weeks or months.")
    if s.type == "momentum_basket":
        return ("A basket buy signal: the QQQ trend turning on (Supertrend up and above SMA200) or an RSI(2) dip. "
                "While it is in, new money joins the basket at the weekly list change.")
    if is_in(s, st.get("target") or {}):
        return (f"It is already in ({st.get('label') or state}). Its next buy signal comes only after the next exit and a new "
                "entry, which can take weeks.")
    rule = (s.describe() or {}).get("rule") or ""
    return f"It buys at its next entry signal. {rule}".strip()


def view(mode: str, s, st: dict | None = None, prices: dict | None = None) -> dict | None:
    """The idle-cash box for one strategy in one mode, or None when nothing is idle."""
    if (s.row or {}).get("control") != "active" or execution.active_plan(mode, s.id):
        return None
    st = st if st is not None else _state(s.id)
    if not st.get("ok"):
        return None
    L = ledger.get(mode, s.id)
    waiting = ledger.waiting_cash(L) if (L["hold_cash"] and execution.waiting_for_buy(mode, s, L)) else 0.0
    tgt = dict(st.get("target") or {})
    syms = set(L["holdings"]) | set(tgt)
    px = prices if prices is not None else (md.prices(syms) if syms else {})
    held = {k: q * (px.get(k) or 0) for k, q in L["holdings"].items()}
    trade_cash = max(0.0, ledger.tradable_cash(L) - ledger.pending_strategy_buys(mode, s.id))
    E = trade_cash + sum(held.values())
    keep = max(0.0, 1 - sum(tgt.values())) * E
    band = max(0.0, trade_cash - keep)
    if waiting < 1 and band < SHOW_MIN_USD:
        return None
    E_all = E + waiting
    buys = []
    for sym, w in sorted(tgt.items(), key=lambda kv: -kv[1]):
        need = w * E_all - held.get(sym, 0.0)
        pr = px.get(sym)
        if need > 1 and pr:
            dp = execution.FRAC_DP if execution.fractional_on(mode, sym) else 0
            buys.append({"symbol": sym, "usd": round(need, 2), "price": pr, "qty": execution._down(need / pr, dp)})
    basket = hasattr(s, "adjust_target")
    band_pct = s.rebalance_band() * 100
    out = {"waiting": round(waiting, 2), "waiting_since": (L["hold_cash"] or None) if waiting else None,
           "band": round(band, 2), "band_pct": band_pct, "gap_pct": round(band / E * 100, 1) if E > 0 else None,
           "value": round(E_all, 2), "in": is_in(s, tgt), "state": st.get("state"), "label": st.get("label"),
           "next_buy": next_buy_text(s, st), "checks": (st.get("detail") or {}).get("checks") or [], "buys": buys,
           "action": None, "note": None}
    if waiting >= 1:
        out["action"] = "invest"
    elif basket:
        out["note"] = ("This strategy keeps equal money per stock and never tops up; the cash joins the basket at the next weekly "
                       "list change or buy signal.")
    elif any(b["qty"] > 0 for b in buys):
        out["action"] = "topup"
    else:
        out["note"] = "Too small to buy a whole share; turn on fractional shares (Execution) or add a little more."
    return out


def topup_now(mode: str, sid: str) -> dict:
    """Buy toward today's target with the strategy's own idle cash (never sells). A normal split plan, from the next check."""
    s = S.get(sid)
    if not s:
        raise ValueError("Unknown strategy")
    if (s.row or {}).get("control") != "active":
        raise ValueError(f"{s.name} is not active")
    if hasattr(s, "adjust_target"):
        raise ValueError(f"{s.name} keeps equal money per stock and never tops up")
    if execution.active_plan(mode, sid):
        raise ValueError(f"{s.name} already has a plan running; it uses the cash")
    st = _state(sid)
    if not st.get("ok") or not st.get("target"):
        raise ValueError(f"{s.name} has no target yet")
    settings = dict(db.get_settings())
    settings["exec_min_trade_usd"] = str(execution.MIN_FRACTION_USD)       # your choice: small top-ups are allowed
    pid = execution.build_plan(mode, s, st["target"], "rebalance", md.now_utc(), sell_override={},
                               note="Top up now (your choice)", settings=settings)
    if not pid:
        raise ValueError("Nothing to buy: the cash is less than one share (or $5 as a fraction)")
    ledger.set_applied_target(mode, sid, st["target"])
    db.add_event("info", "money", f"{s.name}: top up now (your choice)", f"Plan #{pid} buys toward today's target with its idle cash",
                 strategy=sid, mode=mode)
    return {"ok": True, "plan_id": pid}
