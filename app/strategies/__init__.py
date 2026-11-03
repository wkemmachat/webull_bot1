"""Strategy registry: types come from the modules in this folder, instances (with their parameters,
colour, money controls and LINE switch) are rows in the `strategies` table."""
from __future__ import annotations

import importlib
import json
import pkgutil
import time

from .. import db
from .base import TYPES, StrategyBase, register  # noqa: F401

_loaded = False

DEFAULTS = [
    ("gold_sta", "supertrend", "Gold #1 · Supertrend + ADX", "#F2C14E",
     {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 20, "adx_len": 14, "etf": "UGL", "cash_etf": ""}, {}),
    ("gold_st30", "supertrend", "Gold #2 · Supertrend 30/2.5", "#B9852C",
     {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 0, "etf": "UGL", "cash_etf": ""}, {}),
    ("silver_dc", "donchian", "Silver #1 · Donchian 30/15", "#D5DBE3",
     {"symbol": "SI", "entry": 30, "exit": 15, "etf": "AGQ", "cash_etf": ""}, {}),
    ("silver_st", "supertrend", "Silver #2 · Supertrend 10/3", "#8592A3",
     {"symbol": "SI", "atr": 10, "mult": 3.0, "adx_min": 0, "etf": "AGQ", "cash_etf": ""}, {}),
    ("qld_regime", "regime", "QLD regime", "#5B8DEF",
     {"signal": "QQQ", "trade": "QLD", "off_symbol": "GLD", "cash_symbol": "", "vol_gate_pct": 30}, {}),
    ("semis_regime", "regime", "2x Semis regime", "#B084F5",
     {"signal": "SMH", "trade": "USD", "off_symbol": "GLD", "cash_symbol": "", "vol_gate_pct": 40}, {}),
    ("qld_tbd", "trend_dip", "QLD + Trend + bear-dip", "#3DC9C0",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5}, {}),
    ("c27_mom", "momentum_basket", "C2-7 Momentum 1x", "#E8875A", {"leverage": "1x"}, {}),
    ("c27_mom2x", "momentum_basket", "C2-7 Momentum 2x", "#9BCB4E", {"leverage": "2x"}, {}),
    ("qld_ibs", "ibs_dip", "QLD Trend + IBS-dip", "#E46AA8",
     {"trade": "QLD", "vol_symbol": "QQQ", "gold_etf": "GLD", "cash_symbol": "BIL", "ibs_max": 0.15, "adx_min": 20, "target_vol_pct": 50,
      "tbill_cash": True}, {}),
    ("usd_ibs", "ibs_dip", "USD Trend + IBS-dip", "#4FC3F7",
     {"trade": "USD", "vol_symbol": "USD", "compare_symbol": "SMH", "gold_etf": "GLD", "cash_symbol": "BIL", "st_atr": 20, "st_mult": 4.5,
      "ma_days": 200, "ibs_max": 0.15, "adx_min": 0, "target_vol_pct": 40, "leverage": 1, "vol_days": 20, "dip_full_size": True,
      "size_band_pct": 20, "tbill_cash": True}, {}),
    ("rom_tbd", "trend_dip", "ROM Trend + RSI(2)", "#20C997",
     {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "ma_days": 150, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 10}, {}),
    ("qld_tbdv", "trend_dip", "QLD Trend + bear-dip + Vol", "#7FDBCA",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5,
      "vol_gate_q": 80.0, "vol_days": 20, "gold_share_pct": 50.0, "gold_symbol": "GLD"}, {}),
    # 2 Nov 2026 challengers ("2x ETF Strategy Challengers" + stress tests): added with no money; move money from
    # USD Trend + IBS-dip and ROM Trend + RSI(2) yourself when you want them to trade.
    ("usd_smh_ibs", "trend_gate", "USD · SMH trend + SMH IBS-dip", "#2E86DE",
     {"signal": "SMH", "trade": "USD", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "SMA", "ma_days": 125,
      "vol_gate_q": 80.0, "vol_days": 20, "vol_lookback": 504, "rsi_buy": 0.0, "dip_ibs_max": 0.25, "dip_ibs_symbol": "SMH",
      "jumpy_ibs_max": 0.15, "jumpy_ibs_symbol": "USD", "target_vol_pct": 40.0, "size_vol_days": 20, "size_band_pct": 20.0}, {}),
    ("rom_vol_ibs", "trend_gate", "ROM · Trend + Vol + RSI & IBS dips", "#12B886",
     {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "EMA", "ma_days": 150,
      "vol_gate_q": 90.0, "vol_days": 20, "vol_lookback": 252, "rsi_buy": 5.0, "rsi_len": 2, "exit_ma": 5, "dip_ibs_max": 0.15,
      "dip_ibs_symbol": "ROM", "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}, {}),
    # 3 Nov 2026 gold challenger G1 ("Gold & Silver Challengers" + full stress test): added with no money; move the money
    # from Gold #1 and Gold #2 yourself when you want it to trade.
    ("gold_trend_calm", "metal_trend_calm", "Gold · Slow trend + calm + RSI dips", "#D4A017",
     {"symbol": "GC", "atr": 150, "mult": 4.0, "daily_ma": 50, "vol_q": 80.0, "vol_days": 20, "vol_lookback": 252,
      "rsi_len": 2, "rsi_buy": 5.0, "dip_ma": 200, "exit_ma": 5, "etf": "UGL", "cash_etf": ""}, {}),
]
# Earlier defaults: a strategy still on exactly these settings is moved to the new ones once (lower-cost versions, 26 Oct 2026:
# IBS-dip T-bill half as cash + QLD IBS < 0.15; metals flat in cash instead of SGOV).
# Settings you changed yourself are left alone.
UPGRADES = [
    ("lowcost_ibs_2026_10", "qld_ibs",
     {"trade": "QLD", "vol_symbol": "QQQ", "gold_etf": "GLD", "cash_symbol": "BIL", "ibs_max": 0.2, "adx_min": 20, "target_vol_pct": 50}),
    ("lowcost_ibs_2026_10", "usd_ibs",
     {"trade": "USD", "vol_symbol": "USD", "compare_symbol": "SMH", "gold_etf": "GLD", "cash_symbol": "BIL", "st_atr": 20, "st_mult": 4.5,
      "ma_days": 200, "ibs_max": 0.15, "adx_min": 0, "target_vol_pct": 40, "leverage": 1, "vol_days": 20, "dip_full_size": True,
      "size_band_pct": 20}),
    ("lowcost_metals_2026_10", "gold_sta", {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 20, "adx_len": 14, "etf": "UGL", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "gold_st30", {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 0, "etf": "UGL", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "silver_dc", {"symbol": "SI", "entry": 30, "exit": 15, "etf": "AGQ", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "silver_st", {"symbol": "SI", "atr": 10, "mult": 3.0, "adx_min": 0, "etf": "AGQ", "cash_etf": "SGOV"}),
    # 31 Oct 2026: park in cash instead of BIL (each BIL round trip costs 0.22% in fees; plain cash won in every period of the
    # bot's backtest), and QLD Trend + bear-dip + Vol parks half in gold.
    ("cash_parking_2026_10", "qld_regime", {"signal": "QQQ", "trade": "QLD", "off_symbol": "GLD", "cash_symbol": "BIL", "vol_gate_pct": 30}),
    ("cash_parking_2026_10", "semis_regime", {"signal": "SMH", "trade": "USD", "off_symbol": "GLD", "cash_symbol": "BIL", "vol_gate_pct": 40}),
    ("cash_parking_2026_10", "qld_tbd",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "BIL", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5}),
    ("cash_parking_2026_10", "qld_tbdv",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "BIL", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5,
      "vol_gate_q": 80.0, "vol_days": 20}),
]
UPGRADE_WHY = {"cash_parking_2026_10": "Parks in cash instead of BIL (each BIL round trip cost 0.22% in fees)"}
# Added with LINE alerts off: they hold no money until you move some to them (turn LINE on in the strategy when you do).
QUIET_DEFAULTS = {"usd_smh_ibs", "rom_vol_ibs", "gold_trend_calm"}
PALETTE = ["#3DC9C0", "#E8875A", "#E46AA8", "#9BCB4E", "#F2C14E", "#5B8DEF", "#B084F5"]


def load_plugins():
    global _loaded
    if _loaded:
        return
    for m in pkgutil.iter_modules(__path__):
        if m.name not in ("base",):
            importlib.import_module(f"{__name__}.{m.name}")
    _loaded = True


def seed() -> list:
    """Create the research strategies. On the first start all of them; later, a default strategy added in a new
    version is created once (one you archived is never brought back). Returns the ids created now."""
    fresh = not db.one("SELECT id FROM strategies LIMIT 1")
    done = set(db.get_state("seeded_defaults") or ([] if fresh else [d[0] for d in DEFAULTS[:6]]))
    now = int(time.time())
    added = []
    with db.tx() as c:
        n = c.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
        for k, (sid, typ, name, color, params, ex) in enumerate(DEFAULTS):
            if sid in done or c.execute("SELECT 1 FROM strategies WHERE id=?", (sid,)).fetchone():
                continue
            c.execute("INSERT INTO strategies(id,type,name,color,params,exec,control,line_on,archived,sort,created_at,updated_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sid, typ, name, color, json.dumps(params), json.dumps(ex), "active", 0 if sid in QUIET_DEFAULTS else 1, 0,
                       max(k, n), now, now))
            added.append(sid)
    db.set_state("seeded_defaults", sorted(done | {d[0] for d in DEFAULTS}))
    upgrade_defaults()
    return [] if fresh else added


def upgrade_defaults() -> list:
    """Move strategies that still use an earlier default to the new default (once per upgrade). Returns the ids moved."""
    load_plugins()
    seen = set(db.get_state("upgrades_done") or [])
    moved = []
    for key, sid, old in UPGRADES:
        tag = f"{key}:{sid}"
        if tag in seen:
            continue
        seen.add(tag)
        r = row(sid)
        new = next((d for d in DEFAULTS if d[0] == sid), None)
        cls = TYPES.get(r["type"]) if r else None
        if not r or not new or not cls or r["type"] != new[1]:
            continue
        if cls.merge_params(r["params"]) != cls.merge_params(old):
            continue                                    # changed by you: left alone
        db.run("UPDATE strategies SET params=?, updated_at=? WHERE id=?", (json.dumps(new[4]), int(time.time()), sid))
        changes = {k: v for k, v in cls.merge_params(new[4]).items() if cls.merge_params(old).get(k) != v}
        db.add_event("info", "strategy", f"{r['name']}: settings updated to the new default",
                     UPGRADE_WHY.get(key, "Lower-cost version (Webull fee 0.107% per trade)") + ": " + ", ".join(f"{k} → {v if v != '' else 'cash'}" for k, v in changes.items()),
                     strategy=sid)
        moved.append(sid)
    db.set_state("upgrades_done", sorted(seen))
    return moved


def rows(include_archived=False):
    q = "SELECT * FROM strategies" + ("" if include_archived else " WHERE archived=0") + " ORDER BY sort, created_at"
    out = []
    for r in db.rows(q):
        r["params"] = json.loads(r["params"] or "{}")
        r["exec"] = json.loads(r["exec"] or "{}")
        out.append(r)
    return out


def row(sid):
    r = db.one("SELECT * FROM strategies WHERE id=?", (sid,))
    if not r:
        return None
    r["params"] = json.loads(r["params"] or "{}")
    r["exec"] = json.loads(r["exec"] or "{}")
    return r


def instance(r) -> StrategyBase:
    load_plugins()
    cls = TYPES.get(r["type"])
    if not cls:
        raise KeyError(f"Unknown strategy type '{r['type']}' (missing module in app/strategies/?)")
    return cls(r)


def all_instances(include_archived=False):
    out = []
    for r in rows(include_archived):
        try:
            out.append(instance(r))
        except Exception as e:  # a broken plugin must not stop the others
            db.add_event("error", "strategy", f"Cannot load {r['id']}", str(e), strategy=r["id"])
    return out


def get(sid) -> StrategyBase | None:
    r = row(sid)
    return instance(r) if r else None


def types_public():
    load_plugins()
    return [{"type": t, "label": c.label, "family": c.family, "timeframe": c.timeframe, "description": c.description,
             "params": c.PARAMS, "exec_defaults": c.EXEC_DEFAULTS} for t, c in TYPES.items()]


def new_id(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")[:24] or "strategy"
    sid, k = base, 2
    while db.one("SELECT id FROM strategies WHERE id=?", (sid,)):
        sid, k = f"{base}_{k}", k + 1
    return sid


def create(typ: str, name: str, color: str | None, params: dict, exec_: dict | None = None) -> str:
    load_plugins()
    cls = TYPES.get(typ)
    if not cls:
        raise ValueError("Unknown strategy type")
    if not name.strip():
        raise ValueError("Give the strategy a name")
    clean = cls.merge_params(params)
    sid = new_id(name)
    n = db.one("SELECT COUNT(*) n FROM strategies")["n"]
    now = int(time.time())
    db.run("INSERT INTO strategies(id,type,name,color,params,exec,control,line_on,archived,sort,created_at,updated_at) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
           (sid, typ, name.strip(), color or PALETTE[n % len(PALETTE)], json.dumps(clean), json.dumps(exec_ or {}), "active", 1, 0, n,
            now, now))
    return sid


def update(sid: str, **kw):
    r = row(sid)
    if not r:
        raise KeyError(sid)
    sets, args = [], []
    for k in ("name", "color", "control", "line_on", "archived", "sort"):
        if k in kw and kw[k] is not None:
            sets.append(f"{k}=?")
            args.append(kw[k])
    if kw.get("params") is not None:
        cls = TYPES[r["type"]]
        sets.append("params=?")
        args.append(json.dumps(cls.merge_params({**r["params"], **kw["params"]})))
    if kw.get("exec") is not None:
        sets.append("exec=?")
        args.append(json.dumps(kw["exec"]))
    if not sets:
        return
    sets.append("updated_at=?")
    args.append(int(time.time()))
    db.run(f"UPDATE strategies SET {', '.join(sets)} WHERE id=?", (*args, sid))
