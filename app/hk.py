"""Hong Kong market: the 2x ETFs we researched (7234, 7226, 7233), HKD money, board lots, prices and trading hours.

What is different from the US ETFs
  symbol   digits only. The bot writes "7234"; Webull wants five digits ("07234"); Yahoo wants "7234.HK".
  lots     orders must be whole board lots (100 shares for all three); no fractions.
  money    paid in Hong Kong dollars (HKD) from the account's HKD cash. Convert USD → HKD in the Webull app first;
           the bot keeps its HKD in its own pot ("bot HKD"), separate from the USD it uses for US ETFs.
  orders   Webull's HK order type is ENHANCED_LIMIT (a limit order that may match a few ticks through); prices on
           HKEX's tick table (HK$0.001 under HK$0.25, HK$0.01 from HK$0.50 to HK$10 …).
  hours    09:30–12:00 and 13:00–16:00 Hong Kong time (08:30–11:00 and 12:00–15:00 Bangkok), Mon–Fri except
           Hong Kong holidays.
Webull Thailand's OpenAPI documents US trading only. Whether it accepts these orders is what the Go-live
"Hong Kong" test finds out; until then no strategy trades Hong Kong.
"""
from __future__ import annotations

import math
import time
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

from . import db

HKT = ZoneInfo("Asia/Hong_Kong")
CCY = "HKD"
SYM = "HK$"
PEG = 7.80                              # HKD per USD (pegged 7.75–7.85)

# The products we researched (Oct 2026). lot = board lot in shares (HKEX / Webull quote pages).
PRODUCTS = {
    "7234": {"name": "Bosera SZSE ChiNext Daily (2x)", "short": "ChiNext 2x", "lot": 100},
    "7226": {"name": "CSOP Hang Seng TECH Index Daily (2x)", "short": "Hang Seng TECH 2x", "lot": 100},
    "7233": {"name": "CSOP CSI 300 Index Daily (2x)", "short": "CSI 300 2x", "lot": 100},
}
TEST_SYMBOLS = list(PRODUCTS)

# Hong Kong exchange holidays (weekdays only). From the HK public-holiday calendar; Webull's answer is the final word.
HOLIDAYS = {
    date(2026, 1, 1), date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19), date(2026, 4, 3), date(2026, 4, 6),
    date(2026, 4, 7), date(2026, 5, 1), date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 1), date(2026, 10, 1),
    date(2026, 10, 19), date(2026, 12, 25),
}                                       # 2027: add the dates when HKEX publishes them (a holiday order just waits)
SESSIONS = ((dtime(9, 30), dtime(12, 0)), (dtime(13, 0), dtime(16, 0)))


def is_hk(sym) -> bool:
    s = str(sym or "").strip().upper().removesuffix(".HK")
    return s.isdigit() and 1 <= len(s) <= 5


def norm(sym) -> str:
    """'07234', '7234.HK', 7234 → '7234'. Other symbols unchanged (upper case)."""
    s = str(sym or "").strip().upper()
    if is_hk(s):
        return str(int(s.removesuffix(".HK")))
    return s


def api_symbol(sym) -> str:
    return norm(sym).zfill(5)


def yahoo(sym) -> str:
    return f"{int(norm(sym)):04d}.HK"


def lot(sym) -> int:
    s = norm(sym)
    v = db.get_setting(f"hk_lot_{s}")
    try:
        if v:
            return max(1, int(float(v)))
    except ValueError:
        pass
    return int((PRODUCTS.get(s) or {}).get("lot") or 100)


def name(sym) -> str:
    return (PRODUCTS.get(norm(sym)) or {}).get("short") or norm(sym)


def currency(sym) -> str:
    return CCY if is_hk(sym) else "USD"


def money(x, sym=None, ccy=None, dp=2) -> str:
    """'HK$1,234.50' for HK symbols / HKD, '$1,234.50' otherwise."""
    c = ccy or (currency(sym) if sym is not None else "USD")
    pre = SYM if c == CCY else "$"
    return f"{'-' if (x or 0) < 0 else ''}{pre}{abs(x or 0):,.{dp}f}"


# ---------------------------------------------------------------- prices
TICKS = ((0.25, 0.001), (0.50, 0.005), (10, 0.01), (20, 0.02), (100, 0.05), (200, 0.1), (500, 0.2), (1000, 0.5),
         (2000, 1.0), (5000, 2.0), (float("inf"), 5.0))


def tick(price: float) -> float:
    """HKEX spread table: the price step at this price."""
    for top, t in TICKS:
        if price < top or (price == top and top == 0.25):
            return t
    return 5.0


def round_price(price: float, side: str) -> float:
    """Onto the tick table; a buy limit rounds up and a sell limit down (so the limit stays at least as wide)."""
    t = tick(price)
    n = price / t
    n = math.ceil(n - 1e-9) if side == "BUY" else math.floor(n + 1e-9)
    return round(max(t, n * t), 3)


def price_text(price: float) -> str:
    return f"{price:.3f}" if tick(price) < 0.01 else f"{price:.2f}"


# ---------------------------------------------------------------- hours
def _hk(dt) -> datetime:
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(HKT)


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def is_open(dt, min_left_min: float = 0) -> bool:
    """Inside a continuous-trading session with at least min_left_min minutes before it ends."""
    h = _hk(dt)
    if not is_trading_day(h.date()):
        return False
    for a, b in SESSIONS:
        start = h.replace(hour=a.hour, minute=a.minute, second=0, microsecond=0)
        end = h.replace(hour=b.hour, minute=b.minute, second=0, microsecond=0)
        if start <= h < end - timedelta(minutes=min_left_min):
            return True
    return False


def next_open(dt) -> datetime:
    h = _hk(dt)
    for k in range(0, 15):
        d = (h + timedelta(days=k)).date()
        if not is_trading_day(d):
            continue
        for a, _ in SESSIONS:
            start = datetime.combine(d, a, HKT)
            if start > h:
                return start
    return h + timedelta(days=1)


def status(dt) -> dict:
    """For the pages: open now, and the next open in Hong Kong and Bangkok time."""
    o = is_open(dt, 5)
    nxt = next_open(dt)
    bkk = nxt.astimezone(ZoneInfo("Asia/Bangkok"))
    return {"open": o, "next_open": int(nxt.timestamp()),
            "text": "Hong Kong market open" if o else
            f"Hong Kong market closed · opens {nxt.strftime('%a %d %b %H:%M')} HK ({bkk.strftime('%H:%M')} Bangkok)",
            "hours": "09:30–12:00 and 13:00–16:00 Hong Kong time (08:30–11:00 and 12:00–15:00 Bangkok)"}


# ---------------------------------------------------------------- exchange rate
_fx = {"v": None, "t": 0}


def hkd_per_usd() -> float:
    """HKD per 1 USD: Yahoo's HKD=X (refreshed hourly), else the peg 7.80. Only used to show HKD in dollars."""
    if _fx["v"] and time.time() - _fx["t"] < 3600:
        return _fx["v"]
    v = None
    try:
        from . import marketdata as md
        if md.source() != "csv":
            v = float(md.quote("HKD=X", max_age=3600)["price"])
    except Exception:
        v = None
    if not v or not 7.5 < v < 8.1:
        v = PEG
    _fx.update(v=v, t=time.time())
    return v


def to_usd(hkd: float) -> float:
    return (hkd or 0.0) / hkd_per_usd()
