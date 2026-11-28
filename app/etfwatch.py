"""2x ETF watch (28 Nov 2026): every Saturday 09:40 Bangkok the bot ranks US-listed long 2x ETFs by money traded a day
(90-day average) and tells you what is new: a fund that entered the top 50, or a 2x fund listed in the last 4 months.

Only index, sector, theme, commodity, bond, currency and country funds count: single-stock 2x funds (Webull Thailand does
not let you trade them) and crypto funds are left out, as in the 26 Nov research that this list starts from. It only
reports: nothing is traded and no strategy changes. "Research it" marks a fund for you; Dismiss hides it.

Data: Yahoo (the same source as the bot's prices). Yahoo's search finds new listings less completely than a full
screener, so a brand-new fund with very little trading can show up a week or two late.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

from . import db, marketdata as md, notify
from . import strategies as S

log = logging.getLogger("etfwatch")
BKK = ZoneInfo("Asia/Bangkok")
RUN_DAY, RUN_AT = 5, "09:40"           # Saturday, Bangkok time (after the US Friday close)
TOP = 50
NEW_DAYS = 120                          # a 2x fund that first traded this recently is a "new listing"
TICKER_RE = re.compile(r"^[A-Z]{2,5}$")

# The 26 Nov 2026 research (note "US 2x ETFs: top 50 by volume"): every non-single-stock long 2x fund found, ticker →
# (tracks, group, researched before). Crypto funds are kept here so they are recognised, never ranked.
SEED = {
    "QLD": ("Nasdaq-100", "US broad index", True), "SSO": ("S&P 500", "US broad index", True), "AGQ": ("Silver", "Metals", True),
    "BITX": ("Bitcoin", "Crypto", True), "RAM": ("Roundhill Memory ETF (DRAM)", "Tech / growth", True), "ETHU": ("Ether", "Crypto", True),
    "UGL": ("Gold", "Metals", True), "BOIL": ("Natural gas futures", "Energy", True), "UCO": ("Crude oil futures", "Energy", True),
    "NUGT": ("Gold miners", "Metals", True), "USD": ("US semiconductors", "Tech / growth", True), "BITU": ("Bitcoin", "Crypto", False),
    "JNUG": ("Junior gold miners", "Metals", True), "ERX": ("Energy sector", "Energy", True), "GUSH": ("Oil & gas producers", "Energy", True),
    "SOLT": ("Solana", "Crypto", False), "ETHT": ("Ether", "Crypto", False), "UWM": ("Russell 2000", "US broad index", True),
    "DGP": ("Gold (ETN)", "Metals", False), "DDM": ("Dow 30", "US broad index", True), "CWEB": ("China internet", "Country / region", True),
    "XXRP": ("XRP", "Crypto", False), "MQQQ": ("Nasdaq-100, monthly reset", "US broad index", False),
    "TSXU": ("Top 5 semiconductor stocks", "Tech / growth", True), "XRPT": ("XRP", "Crypto", False), "ROM": ("Technology sector", "Tech / growth", True),
    "BRZU": ("Brazil", "Country / region", True), "SPUU": ("S&P 500", "US broad index", False), "SLON": ("Solana", "Crypto", False),
    "DIG": ("Energy sector", "Energy", False), "QPUX": ("Quantum computing basket", "Tech / growth", True), "MAGX": ("Magnificent 7", "Tech / growth", True),
    "URSP": ("S&P 500 Equal Weight", "US broad index", False), "UXRP": ("XRP", "Crypto", False), "USLV": ("Silver", "Metals", False),
    "QQQU": ("Magnificent 7", "Tech / growth", False), "UGLD": ("Gold", "Metals", False), "UYG": ("Financials", "US sector", True),
    "URAA": ("Uranium industry", "Energy", True), "CHAU": ("China A-shares CSI 300", "Country / region", True),
    "UBT": ("20+ year Treasuries", "Bonds / FX", True), "TARK": ("ARK Innovation (ARKK)", "Tech / growth", False),
    "BIB": ("Nasdaq biotech", "US sector", True), "FNGG": ("NYSE FANG+", "Tech / growth", False), "UGE": ("Consumer staples", "US sector", True),
    "RXL": ("Health care", "US sector", True), "UJB": ("High-yield bonds", "Bonds / FX", False), "INDL": ("India", "Country / region", True),
    "MVV": ("S&P MidCap 400", "US broad index", True), "FNGO": ("NYSE FANG+ (ETN)", "Tech / growth", False), "BTCU": ("Bitcoin", "Crypto", False),
    "EET": ("Emerging markets", "Country / region", True), "YCL": ("Japanese yen", "Bonds / FX", False),
    "LTL": ("Communication services", "US sector", False), "UST": ("7-10 year Treasuries", "Bonds / FX", True), "CPXR": ("Copper", "Metals", False),
    "WXET": ("Wheat futures", "Other commodity", False), "UPW": ("Utilities", "US sector", True), "AIBU": ("AI & big data index", "Tech / growth", True),
    "QQQP": ("Nasdaq-100, quarterly reset", "US broad index", False), "EFO": ("Developed ex-US (EAFE)", "Country / region", True),
    "EUVX": ("Lithography & photonics basket", "Tech / growth", False), "UBOT": ("Robotics & AI index", "Tech / growth", False),
    "SKYU": ("Nasdaq cloud computing", "Tech / growth", False), "UYM": ("Materials", "US sector", True),
    "TTXU": ("Top 5 technology stocks", "Tech / growth", False), "SPYQ": ("S&P 500, quarterly reset", "US broad index", False),
    "EZJ": ("Japan", "Country / region", True), "URE": ("Real estate", "US sector", True), "UXI": ("Industrials", "US sector", True),
    "UCC": ("Consumer discretionary", "US sector", True), "SAA": ("S&P SmallCap 600", "US broad index", False), "UBR": ("Brazil", "Country / region", False),
    "UPV": ("Europe", "Country / region", False), "ULE": ("Euro", "Bonds / FX", False), "XPP": ("China large-cap 50", "Country / region", True),
}
QUERIES = ["2X Long ETF", "Daily 2X ETF", "Ultra ProShares", "ProShares Ultra", "Direxion Daily Bull 2X", "Leverage Shares 2X",
           "Defiance Daily Target 2X", "Tradr 2X Long", "T-Rex 2X Long", "Roundhill Daily 2X", "GraniteShares 2x Long",
           "MAX 2X ETN", "2X Leveraged ETF", "Double Long ETF", "200% Daily"]
KEEP = re.compile(r"2X|ULTRA|DOUBLE LONG|200%", re.I)
DROP = re.compile(r"SHORT|INVERSE|BEAR|ULTRAPRO|ULTRASHORT|3X|BUFFER|YIELDMAX|DIVIDEND|VIX|INCOME|OPTION", re.I)
CRYPTO = re.compile(r"BITCOIN|ETHER|SOLANA|XRP|DOGE|SUI\b|CRYPTO|LITECOIN|CARDANO|AVALANCHE|CHAINLINK|POLKADOT|COIN\b", re.I)
NOT_STOCKS = {"ETF", "ETN", "USD", "NYSE", "FANG", "S&P", "MSCI", "AI", "US", "DAILY", "LONG", "BULL", "TARGET", "ULTRA", "MAX", "PLUS",
              "QQQ", "SPY", "DIA", "IWM", "SMH", "SOXX", "XLK", "GLD", "SLV", "ARKK", "DRAM", "KWEB", "FXI", "EEM", "TLT", "GDX"}
_running = {"on": False}


# ---------------------------------------------------------------- Yahoo (replaced in tests)
def _search(query: str) -> list:
    from . import etf2x
    return etf2x._search(query)


def _download(tickers: list) -> dict:
    """{ticker: {"adv90", "adv10", "price", "first"}} from Yahoo daily bars (dollar volume = shares × close)."""
    if md.source() == "csv" or not tickers:
        return {}
    import yfinance as yf
    out = {}
    df = yf.download(tickers, period="9mo", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
    for t in tickers:
        try:
            sub = df[t] if len(tickers) > 1 else df
            sub = sub.dropna(subset=["Close"])
            if sub.empty:
                continue
            dv = (sub["Close"] * sub["Volume"]).astype(float)
            out[t] = {"adv90": float(dv.tail(90).mean()), "adv10": float(dv.tail(10).mean()), "price": float(sub["Close"].iloc[-1]),
                      "first": int(sub.index[0].timestamp()), "days": int(len(sub))}
        except Exception:
            continue
    return out


def _first_trade(t: str) -> int | None:
    """First day a fund traded (Yahoo, full history): only asked for funds found by the search."""
    if md.source() == "csv":
        return None
    import yfinance as yf
    try:
        h = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=False)
        return int(h.index[0].timestamp()) if h is not None and len(h) else None
    except Exception:
        return None


def _quote_type(sym: str) -> str:
    try:
        for q in _search(sym):
            if q["symbol"] == sym:
                return q["type"]
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------- what a fund is
def is_long_2x(name: str) -> bool:
    return bool(name) and bool(KEEP.search(name)) and not DROP.search(name)


def is_crypto(name: str) -> bool:
    return bool(CRYPTO.search(name or ""))


def single_stock(name: str, own: str) -> bool:
    """A fund named after one company's ticker ("Tradr 2X Long NVDA Daily ETF", "Direxion Daily TSLA Bull 2X") is a
    single-stock fund. Upper-case words that Yahoo calls an EQUITY are taken as that company; ETFs (QQQ, DRAM) are not."""
    for tok in re.findall(r"\b[A-Z]{1,5}\b", name or ""):
        if tok == own or tok in NOT_STOCKS:
            continue
        if _quote_type(tok) == "EQUITY":
            return True
    return False


# ---------------------------------------------------------------- state
def known() -> dict:
    k = db.get_state("etfwatch:known")
    if not k:
        k = {t: {"tracks": a, "group": g, "researched": r, "source": "research 26 Nov 2026"} for t, (a, g, r) in SEED.items()}
        db.set_state("etfwatch:known", k)
    return k


def marks() -> dict:
    return db.get_state("etfwatch:marks") or {}


def mark(ticker: str, what: str) -> dict:
    t = (ticker or "").upper().strip()
    if not TICKER_RE.match(t):
        raise ValueError("Unknown ETF")
    m = marks()
    if what in ("research", "dismissed"):
        m[t] = {"mark": what, "t": int(time.time())}
    elif what == "clear":
        m.pop(t, None)
    else:
        raise ValueError("Mark: research, dismissed or clear")
    db.set_state("etfwatch:marks", m)
    return view()


def _status(t: str, k: dict, mk: dict) -> str:
    from . import pool
    for mode in ("live", "paper"):
        c = pool.cfg(mode)
        if c.get("on") and any(pool.main_symbol(S.get(sid)) == t for sid in c["members"] if S.get(sid)):
            return "pool"
    if any(t in (s.trade_symbols() or []) for s in S.all_instances()):
        return "bot"
    m = (mk.get(t) or {}).get("mark")
    if m == "research":
        return "to_research"
    return "researched" if (k.get(t) or {}).get("researched") else "not_researched"


# ---------------------------------------------------------------- the weekly check
def check(send_line: bool = True) -> dict:
    """Rank this week's top 50, compare with last week, find new 2x funds. Returns the stored result."""
    k = known()
    found_new = []
    for q in QUERIES:                                       # 1 · new 2x funds Yahoo knows about
        try:
            res = _search(q)
        except Exception as e:
            log.info("etf watch search %s: %s", q, e)
            res = []
        for r in res:
            t, name = r["symbol"], r["name"]
            if r["type"] != "ETF" or not TICKER_RE.match(t) or t in k or not is_long_2x(name):
                continue
            if is_crypto(name) or single_stock(name, t):
                k[t] = {"tracks": name, "group": "Crypto" if is_crypto(name) else "Single stock", "researched": False,
                        "source": "search", "name": name, "skip": True}
                continue
            first = _first_trade(t)
            k[t] = {"tracks": name, "group": "New · check", "researched": False, "source": "search", "name": name, "first": first,
                    "found": int(time.time())}
            if first and time.time() - first < NEW_DAYS * 86400:
                found_new.append(t)
        time.sleep(0.5)
    db.set_state("etfwatch:known", k)
    rank_set = [t for t, v in k.items() if v.get("group") not in ("Crypto", "Single stock") and not v.get("skip")]
    for t in rank_set:                                      # each fund's first trading day, asked once and kept
        if "first" not in k[t]:
            k[t]["first"] = _first_trade(t)
            time.sleep(0.2)
    db.set_state("etfwatch:known", k)
    data = _download(rank_set)                              # 2 · money traded a day
    if not data:
        raise RuntimeError("Yahoo gave no prices for the 2x ETFs")
    rows = []
    for t in rank_set:
        x = data.get(t)
        if not x or not np.isfinite(x["adv90"]):
            continue
        v = k[t]
        rows.append({"t": t, "tracks": v["tracks"], "group": v["group"], "adv90": round(x["adv90"] / 1e6, 3),
                     "adv10": round(x["adv10"] / 1e6, 3), "price": round(x["price"], 2), "first": v.get("first")})
    rows.sort(key=lambda r: -r["adv90"])
    top = rows[:TOP]
    for i, r in enumerate(top, 1):
        r["rank"] = i
    last = db.get_state("etfwatch:last") or {}
    prev = {r["t"]: r["rank"] for r in last.get("top", [])}
    for r in top:
        r["was"] = prev.get(r["t"])
    now = int(time.time())
    first_run = not prev
    entered = [] if first_run else [r["t"] for r in top if r["t"] not in prev]
    left = [] if first_run else [t for t in prev if t not in {r["t"] for r in top}]
    by_t = {r["t"]: r for r in rows}
    new = []
    for t in dict.fromkeys(found_new + entered):
        r = by_t.get(t) or {"t": t, "tracks": k[t]["tracks"], "group": k[t]["group"], "adv90": None, "first": k[t].get("first")}
        new.append({**r, "kind": "listing" if t in found_new else "entered", "name": k[t].get("name")})
    gone = [{"t": t, "tracks": k.get(t, {}).get("tracks", ""), "adv90": (by_t.get(t) or {}).get("adv90")} for t in left]
    res = {"t": now, "top": top, "new": new, "left": gone, "cutoff": top[-1]["adv90"] if top else None, "count": len(rows),
           "first_run": first_run}
    db.set_state("etfwatch:last", res)
    log_ = db.get_state("etfwatch:log") or []
    log_.insert(0, {"t": now, "new": [n["t"] for n in new], "left": left, "first_run": first_run, "cutoff": res["cutoff"]})
    db.set_state("etfwatch:log", log_[:30])
    if new and send_line:
        lines = [f"{n['t']} · {n['tracks']}" + (f" · ${n['adv90']:.1f}M a day" if n.get("adv90") else "")
                 + (" · new listing" if n["kind"] == "listing" else f" · entered the top {TOP} at #{n.get('rank')}") for n in new]
        notify.send("etfwatch", "New 2x ETFs this week (index, sector and commodity funds):\n" + "\n".join(lines)
                    + "\nDashboard → New 2x ETFs. Nothing changes until you research one.")
    db.add_event("info", "data", "2x ETF watch: " + (f"{len(new)} new" if new else ("starting list" if first_run else "nothing new")),
                 ", ".join(n["t"] for n in new) + (f" · left: {', '.join(left)}" if left else ""))
    return res


def _job():
    try:
        check()
    except Exception as e:
        log.warning("etf watch: %s", e)
        db.add_event("warn", "data", "2x ETF watch failed (retrying in 1 h)", str(e)[:300])
        db.set_state("etfwatch:retry_at", int(time.time()) + 3600)
        db.set_state("etfwatch:done", None)
    finally:
        _running["on"] = False


def start() -> dict:
    if _running["on"]:
        return {"running": True}
    _running["on"] = True
    threading.Thread(target=_job, daemon=True).start()
    return {"running": True}


def due(now) -> bool:
    """Saturday 09:40 Bangkok or later, once per Saturday (engine tick)."""
    b = now.astimezone(BKK)
    if b.weekday() != RUN_DAY or b.strftime("%H:%M") < RUN_AT:
        return False
    if time.time() < (db.get_state("etfwatch:retry_at") or 0):
        return False
    day = b.date().isoformat()
    if db.get_state("etfwatch:done") == day:
        return False
    db.set_state("etfwatch:done", day)
    return True


def next_run(now=None) -> int:
    b = (now or md.now_utc()).astimezone(BKK)
    h, m = (int(x) for x in RUN_AT.split(":"))
    d = b.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=(RUN_DAY - b.weekday()) % 7)
    if d <= b:
        d += timedelta(days=7)
    return int(d.timestamp())


# ---------------------------------------------------------------- views
def view() -> dict:
    last = db.get_state("etfwatch:last") or {}
    k, mk = known(), marks()
    top = [{**r, "status": _status(r["t"], k, mk), "years": _years(r.get("first"))} for r in last.get("top", [])]
    new = [{**n, "status": _status(n["t"], k, mk), "years": _years(n.get("first")), "mark": (mk.get(n["t"]) or {}).get("mark")}
           for n in last.get("new", [])]
    return {"t": last.get("t"), "top": top, "new": new, "left": last.get("left", []), "cutoff": last.get("cutoff"),
            "first_run": last.get("first_run"), "log": db.get_state("etfwatch:log") or [], "next": next_run(), "running": _running["on"],
            "counts": {s: sum(1 for r in top if r["status"] == s) for s in ("pool", "bot", "researched", "to_research", "not_researched")}}


def _years(first):
    if not first:
        return None
    return round((time.time() - first) / 31_557_600, 1)


def brief() -> dict:
    """Dashboard card: this week's new names (not dismissed) and the ones that left."""
    v = view()
    return {"t": v["t"], "new": [n for n in v["new"] if n.get("mark") != "dismissed"], "left": v["left"], "next": v["next"],
            "first_run": v["first_run"], "running": v["running"]}
