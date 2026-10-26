"""Brokers, one per trading mode.

paper  PaperBroker: pretend money inside the bot. Fills limit orders against the live (Yahoo) price
       plus a small spread, only while the US session is open (the execution engine checks that).
test   WebullBroker(env="test"): Webull's test server (th-api.uat.webullbroker.com), test keys and account.
live   WebullBroker(env="live"): your real Webull Thailand account (region 'th').

The Webull part follows the official `webull-openapi-python-sdk` and the Gold & Silver bot. A new login
needs approval in the Webull app (SMS code; Menu → Messages → OpenAPI Notifications) within 5 minutes,
so the scheduler never starts a login by itself: it reuses the saved token. Webull's token file (token.txt: token,
expires, status) says when it ends; the Webull page and the Health check show that date.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from . import db, marketdata as md
from .config import DATA_DIR

log = logging.getLogger("broker")
MODES = ("paper", "test", "live")
MODE_LABEL = {"paper": "Paper", "test": "Webull test", "live": "Live"}


class BrokerError(Exception):
    pass


class BrokerRejected(BrokerError):
    """The broker answered and refused the order: it was NOT placed (safe to mark failed).
    permanent=True when trying again cannot help (no permission for the symbol, symbol not tradable)."""

    def __init__(self, msg, code="", permanent=False):
        super().__init__(msg)
        self.code, self.permanent = code, permanent


# Webull refusals that a retry cannot fix (seen on the Webull TH test server, Oct 2026)
SINGLE_STOCK_LEV_CODE = "OPENAPI_ONLY_UHNWE_SINGLE_STOCK_REVERSE_ETF_LIMIT"
PERMANENT_CODES = ("OPENAPI_IS_TH_FIRST_ETF_PLACE", "OPENAPI_TICKER_IS_DENY", SINGLE_STOCK_LEV_CODE)
PERMANENT_HINTS = {
    SINGLE_STOCK_LEV_CODE: "Webull Thailand allows leveraged or inverse ETFs on single stocks only for clients with 50M THB or "
                           "more. The bot holds the stock itself instead, so C2-7 Momentum 2x then works like 1x.",
    "OPENAPI_IS_TH_FIRST_ETF_PLACE": "Activate Leveraged & Inverse ETF trading for your Webull account (Webull app), then try again.",
    "OPENAPI_TICKER_IS_DENY": "Webull does not allow this symbol for your account. Choose another ETF for this strategy.",
}


def parse_rejection(text):
    """'... HTTP Status: 417, Code: X, Msg: Y ...' → BrokerRejected, or None when it is not a clear 4xx refusal."""
    import re
    m = re.search(r"HTTP Status:\s*(\d+).*?Code:\s*([A-Za-z0-9_]+)(?:.*?Msg:\s*([^\r\n]*))?", text or "", re.S)
    if not m or not m.group(1).startswith("4"):
        return None
    code, msg = m.group(2), (m.group(3) or "").split(", RequestID")[0].strip()
    perm = code in PERMANENT_CODES or any(w in code for w in ("DENY", "PERMISSION", "NOT_SUPPORT", "UHNW", "_LIMIT"))
    return BrokerRejected(f"{code}: {msg}", code=code, permanent=perm)


def _first(d, *keys):
    """The first of these keys that holds a number."""
    for k in keys:
        v = _num((d or {}).get(k))
        if v is not None:
            return v
    return None


def _num(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- paper
class PaperBroker:
    mode = "paper"
    label = "Paper trading (pretend money, live prices)"
    KEY = "paper_account"

    def __init__(self, settings=None, quote_fn=None):
        self.settings = settings or db.get_settings()
        self.quote_fn = quote_fn or md.quote
        self.spread = float(self.settings.get("paper_spread_pct") or 0.05) / 100
        self.fee = float(self.settings.get("paper_fee_pct") or 0) / 100

    def _acct(self):
        a = db.get_state(self.KEY)
        if not a:
            cash = float(self.settings.get("paper_start_cash") or 150000)
            a = {"cash": cash, "start_cash": cash, "positions": {}, "orders": {}, "created": int(time.time())}
            db.set_state(self.KEY, a)
        return a

    def _save(self, a):
        if len(a["orders"]) > 3000:     # keep the newest orders only
            keep = sorted(a["orders"].values(), key=lambda o: o.get("t", 0))[-2000:]
            a["orders"] = {o["cid"]: o for o in keep}
        db.set_state(self.KEY, a)

    def status(self):
        return {"connected": True, "label": self.label, "mode": "paper"}

    def ready(self):
        return True, None

    def quote(self, symbol):
        return self.quote_fn(symbol)

    def account(self):
        a = self._acct()
        pos, mv = {}, 0.0
        for sym, p in a["positions"].items():
            if p["qty"] <= 1e-9:
                continue
            try:
                px = self.quote(sym)["price"]
            except Exception:
                px = p.get("last") or (p["cost"] / p["qty"] if p["qty"] else 0)
            pos[sym] = {"qty": p["qty"], "cost": p["cost"] / p["qty"] if p["qty"] else None, "last": px, "value": p["qty"] * px}
            mv += p["qty"] * px
        return {"total": a["cash"] + mv, "cash": a["cash"], "market_value": mv, "buying_power": a["cash"],
                "positions": pos, "currency": "USD", "account_id": "PAPER"}

    def _try_fill(self, a, o):
        if o["status"] != "SUBMITTED":
            return
        q = self.quote(o["symbol"])
        px = q["price"] * (1 + self.spread if o["side"] == "BUY" else 1 - self.spread)
        if o["limit"] is not None and ((o["side"] == "BUY" and o["limit"] < px) or (o["side"] == "SELL" and o["limit"] > px)):
            return
        p = a["positions"].setdefault(o["symbol"], {"qty": 0.0, "cost": 0.0})
        qty = o["qty"]
        fee = qty * px * self.fee
        if o["side"] == "BUY":
            if qty * px + fee > a["cash"] + 1e-6:
                o.update(status="FAILED", error="insufficient cash")
                return
            p["qty"] += qty
            p["cost"] += qty * px
            a["cash"] -= qty * px + fee
        else:
            if qty > p["qty"] + 1e-9:
                o.update(status="FAILED", error="not enough shares")
                return
            avg = p["cost"] / p["qty"] if p["qty"] else 0
            p["qty"] -= qty
            p["cost"] = max(0.0, p["cost"] - avg * qty)
            a["cash"] += qty * px - fee
        p["last"] = q["price"]
        o.update(status="FILLED", filled_qty=qty, avg_price=round(px, 4), filled_at=int(time.time()), fee=round(fee, 4))

    def place(self, symbol, side, qty, limit, session, cid):
        a = self._acct()
        if cid in a["orders"]:
            return {"order_id": cid}
        o = {"cid": cid, "symbol": symbol, "side": side, "qty": float(qty), "limit": limit, "status": "SUBMITTED",
             "filled_qty": 0.0, "avg_price": None, "t": int(time.time())}
        a["orders"][cid] = o
        self._try_fill(a, o)
        self._save(a)
        if o["status"] == "FAILED":
            raise BrokerRejected(o.get("error", "rejected"), code="PAPER_REJECTED")
        return {"order_id": cid}

    def order(self, cid):
        a = self._acct()
        o = a["orders"].get(cid)
        if not o:
            raise BrokerError("unknown order")
        if o["status"] == "SUBMITTED":
            try:
                self._try_fill(a, o)
                self._save(a)
            except Exception as e:
                log.warning("paper fill check %s: %s", cid, e)
        return {"status": o["status"], "filled_qty": o["filled_qty"], "avg_price": o["avg_price"], "fee": o.get("fee") or 0.0}

    def cancel(self, cid):
        a = self._acct()
        o = a["orders"].get(cid)
        if o and o["status"] == "SUBMITTED":
            o["status"] = "CANCELLED"
            self._save(a)
        return True

    @classmethod
    def reset(cls, start_cash):
        db.set_state(cls.KEY, {"cash": float(start_cash), "start_cash": float(start_cash), "positions": {}, "orders": {},
                               "created": int(time.time())})


# ---------------------------------------------------------------- Webull
_wb_lock = threading.Lock()
_wb_clients: dict = {}


def conn_key(env):
    return "webull_conn_test" if env == "test" else "webull_conn"


# Webull's shared test accounts (developer.webull.co.th/apis/docs/sdk#test-accounts): public, anyone may trade in them.
SHARED_TEST_ACCOUNTS = [
    {"account_id": "1249711087713001472", "app_key": "86d0dac12b1b28de7539f087b2c1dca7", "app_secret": "28dfb45a1be192a04242efd1aeba20f6"},
    {"account_id": "1251161604462252032", "app_key": "0e3bd1b4a9d94857aee5410f9b769121", "app_secret": "e5e0f0046235380d5f6d3cebfe6d9696"},
    {"account_id": "1251161573554425856", "app_key": "c12c25c93f98169ad56f5148e4edfd16", "app_secret": "f3ac0da97d2085ad4ce14b961cbd8824"},
]


class WebullBroker:
    TEST_HOST = "th-api.uat.webullbroker.com"     # Webull TH test environment (live: api.webull.co.th, the SDK default for "th")

    def __init__(self, settings=None, env="live"):
        self.settings = s = settings or db.get_settings()
        self.env = "test" if env == "test" else "live"
        self.mode = self.env
        p = "webull_test_" if self.env == "test" else "webull_"
        self.prefix = p
        self.key = (s.get(p + "app_key") or "").strip()
        self.secret = (s.get(p + "app_secret") or "").strip()
        self.region = (s.get("webull_region") or "th").strip()
        self.endpoint = (s.get(p + "endpoint") or "").strip() if self.env == "test" else ""
        if self.env == "test" and not self.endpoint:
            self.endpoint = self.TEST_HOST
        self.account_id = (s.get(p + "account_id") or "").strip()
        self.label = "Webull test environment" if self.env == "test" else "Webull Thailand (live)"
        self.tok_dir = Path(DATA_DIR) / ("webull-test" if self.env == "test" else "webull")

    def _clients(self, interactive=False):
        if not self.key or not self.secret:
            raise BrokerError(f"Add your Webull {'test ' if self.env == 'test' else ''}App Key and App Secret on the Webull page")
        ck = (self.env, self.key, self.region, self.endpoint)
        with _wb_lock:
            if ck in _wb_clients:
                return _wb_clients[ck]
            st = db.get_state(conn_key(self.env)) or {}
            tok = self.tok_dir / "token.txt"
            if not interactive:
                ok_once = self.env == "test" and (self.tok_dir / "connected.ok").exists()
                if not tok.exists() and not ok_once:
                    raise BrokerError("Webull is not connected yet: press Connect on the Webull page")
                if st.get("status") in ("error", "connecting") and time.time() - st.get("at", 0) < 1800:
                    raise BrokerError("Webull login needs attention: press Connect on the Webull page")
            try:
                from webull.core.client import ApiClient
                from webull.data.data_client import DataClient
                from webull.trade.trade_client import TradeClient
            except ImportError as e:
                raise BrokerError("The Webull SDK is not installed (pip install -r requirements.txt)") from e
            api = ApiClient(self.key, self.secret, self.region)
            if self.endpoint:
                api.add_endpoint(self.region, self.endpoint)
            self.tok_dir.mkdir(parents=True, exist_ok=True)
            api.set_token_dir(str(self.tok_dir))
            api.set_file_logger(path=str(self.tok_dir / "webull_sdk.log"), log_level=logging.INFO,
                                format_string="%(asctime)s %(name)s %(levelname)s %(message)s", backup_count=48)
            db.set_state(conn_key(self.env), {"status": "connecting", "at": int(time.time()),
                                              "msg": "Waiting for approval: open the Webull app and enter the SMS code "
                                                     "(Menu → Messages → OpenAPI Notifications). You have 5 minutes."})
            try:
                trade = TradeClient(api)
                data = DataClient(api)
            except Exception as e:
                db.set_state(conn_key(self.env), {"status": "error", "at": int(time.time()), "msg": str(e)[:300]})
                raise BrokerError(f"Webull connection failed: {e}") from e
            prev = db.get_state(conn_key(self.env)) or {}
            db.set_state(conn_key(self.env), {"status": "connected", "at": int(time.time()), "msg": "Connected",
                                              "approved_at": prev.get("approved_at") or int(time.time())})
            if self.env == "test":
                (self.tok_dir / "connected.ok").write_text(str(int(time.time())))
            _wb_clients[ck] = (trade, data)
            return trade, data

    def connect(self):
        """Interactive login (Connect button). May wait up to 5 minutes for the SMS approval."""
        st = db.get_state(conn_key(self.env)) or {}
        st["approved_at"] = None
        db.set_state(conn_key(self.env), st)
        self._clients(interactive=True)
        st = db.get_state(conn_key(self.env)) or {}
        st["approved_at"] = int(time.time())
        db.set_state(conn_key(self.env), st)
        return self.status()

    def disconnect(self):
        with _wb_lock:
            for k in [k for k in _wb_clients if k[0] == self.env]:
                _wb_clients.pop(k, None)
        tok = self.tok_dir / "token.txt"
        if tok.exists():
            tok.rename(self.tok_dir / f"token.disconnected.{int(time.time())}.txt")
        db.set_state(conn_key(self.env), {"status": "disconnected", "at": int(time.time()), "msg": "Disconnected"})

    def ready(self):
        try:
            self._clients()
            return True, None
        except BrokerError as e:
            return False, str(e)

    @staticmethod
    def _call(fn, what):
        try:
            return fn()
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f"Webull {what} failed: {str(e)[:300]}") from e

    @staticmethod
    def _json(res, what):
        if res is None or getattr(res, "status_code", 0) != 200:
            body = ""
            try:
                body = res.text[:300]
            except Exception:
                pass
            raise BrokerError(f"Webull {what} failed ({getattr(res, 'status_code', '?')}): {body}")
        return res.json()

    def _touch(self):
        st = db.get_state(conn_key(self.env)) or {}
        if time.time() - (st.get("used_at") or 0) > 60:
            st["used_at"] = int(time.time())
            db.set_state(conn_key(self.env), st)

    def token_info(self):
        """(expires_unix, status) from the SDK's token file, or (None, None)."""
        f = self.tok_dir / "token.txt"
        try:
            lines = f.read_text().splitlines()
        except OSError:
            return None, None
        exp = None
        if len(lines) > 1 and lines[1].strip().isdigit():
            exp = int(lines[1].strip())
            exp = exp // 1000 if exp > 10 ** 11 else exp          # milliseconds or seconds
        return exp, (lines[2].strip() if len(lines) > 2 else None)

    def status(self):
        st = db.get_state(conn_key(self.env)) or {}
        tok = (self.tok_dir / "token.txt").exists()
        exp, tstat = self.token_info()
        connected = st.get("status") == "connected"
        return {"env": self.env, "mode": self.env, "connected": connected, "label": self.label,
                "has_keys": bool(self.key and self.secret), "token_saved": tok, "token_status": tstat,
                "lapses_at": exp if (connected and exp) else None, **st}

    def accounts(self):
        trade, _ = self._clients()
        js = self._json(self._call(trade.account_v2.get_account_list, "account list"), "account list")
        return js if isinstance(js, list) else js.get("data", js.get("accounts", []))

    def _acct_id(self):
        if self.account_id:
            return self.account_id
        accts = self.accounts()
        if not accts:
            raise BrokerError("No Webull account found for this API key")
        if len(accts) > 1:
            ids = ", ".join(str(a.get("account_id") or a.get("accountId")) for a in accts)
            raise BrokerError(f"This API key has several Webull accounts ({ids}). Enter the one to use as Account ID.")
        aid = accts[0].get("account_id") or accts[0].get("accountId")
        self.account_id = aid
        db.set_settings({self.prefix + "account_id": aid})
        return aid

    def quote(self, symbol):
        try:
            _, data = self._clients()
            res = self._call(lambda: data.market_data.get_snapshot(symbol, "US_ETF", extend_hour_required=True,
                                                                    overnight_required=True), "quote")
            js = self._json(res, "quote")
            row = js[0] if isinstance(js, list) and js else (js.get("data", [{}])[0] if isinstance(js, dict) else {})
            px = _num(row.get("extend_hour_last_price")) if row.get("extend_hour_last_trade_time", 0) and \
                (row.get("extend_hour_last_trade_time", 0) > (row.get("last_trade_time") or 0)) else None
            px = px or _num(row.get("price"))
            if px:
                self._touch()
                return {"price": px, "bid": _num(row.get("bid")), "ask": _num(row.get("ask")),
                        "time": int((row.get("last_trade_time") or 0) / 1000), "source": "webull"}
        except BrokerError as e:
            log.warning("Webull quote failed for %s, using Yahoo: %s", symbol, e)
        return md.quote(symbol)

    def raw_account(self):
        """The untouched balance and position JSON from Webull (for `python -m app.webull_check`)."""
        trade, _ = self._clients()
        aid = self._acct_id()
        b = self._json(self._call(lambda: trade.account_v2.get_account_balance(aid), "balance"), "balance")
        p = self._json(self._call(lambda: trade.account_v2.get_account_position(aid), "positions"), "positions")
        return aid, b, p

    def account(self):
        aid, b, p = self.raw_account()
        b = b.get("data", b) if isinstance(b, dict) else b
        # Webull TH can hold several currencies (USD, THB, CNY, HKD …). US ETFs are bought with USD only, so the bot
        # reads the USD figures when Webull sends them per currency; other currencies are reported, never used.
        cur = [x for x in (b.get("account_currency_assets") or []) if isinstance(x, dict)]
        usd = next((x for x in cur if str(x.get("currency") or "").upper() == "USD"), {})
        other = [{"currency": str(x.get("currency") or "?").upper(), "cash": _first(x, "cash_balance", "cash", "total_cash")}
                 for x in cur if str(x.get("currency") or "").upper() not in ("USD", "")]
        other = [o for o in other if o["cash"]]
        rws = p if isinstance(p, list) else p.get("data", p.get("positions", p.get("holdings", [])))
        pos, pos_v = {}, 0.0
        for r in rws or []:
            if (r.get("instrument_type") or "EQUITY") != "EQUITY":
                continue
            q = _first(r, "quantity", "qty", "position") or 0.0
            last = _first(r, "last_price", "price", "close_price")
            mv = _first(r, "market_value")
            v = mv if mv is not None else q * (last or 0.0)
            pos[r.get("symbol") or r.get("ticker")] = {"qty": q, "cost": _first(r, "cost_price", "average_cost", "avg_cost"),
                                                       "last": last if last is not None else (v / q if q else None), "value": v}
            pos_v += v
        if usd and (_first(usd, "cash_balance", "cash", "total_cash") is not None or other):
            cash = _first(usd, "cash_balance", "cash", "total_cash")       # None (→ no buys) rather than count THB
            mval = _first(usd, "market_value", "total_market_value")
        else:
            cash = _first(b, "total_cash_balance", "cash_balance", "total_cash")
            mval = _first(b, "total_market_value", "market_value")
        mval = mval if mval is not None else pos_v
        if usd and (cash is not None or other) and _first(usd, "net_liquidation_value", "total_asset", "total_assets",
                                                          "total_net_liquidation_value") is not None:
            total = _first(usd, "net_liquidation_value", "total_asset", "total_assets", "total_net_liquidation_value")
        else:
            total = _first(b, "total_net_liquidation_value", "net_liquidation_value", "total_asset", "total_assets",
                           "total_account_value", "account_value")
        if total is None and cash is not None:
            total = cash + (mval or 0.0)              # Webull did not send a total: cash + value of all positions
        self._touch()
        return {"total": total, "cash": cash, "market_value": mval,
                "buying_power": _first(usd, "buying_power") or _first(b, "buying_power", "total_buying_power"),
                "positions": pos, "currency": "USD", "account_id": aid, "other_cash": other}

    def place(self, symbol, side, qty, limit, session, cid):
        trade, _ = self._clients()
        order = {"combo_type": "NORMAL", "client_order_id": cid, "symbol": symbol, "instrument_type": "EQUITY",
                 "market": "US", "order_type": "LIMIT" if limit else "MARKET", "quantity": str(int(qty)),
                 "support_trading_session": session if limit else "CORE", "side": side,
                 "time_in_force": "DAY", "entrust_type": "QTY"}
        if limit:
            order["limit_price"] = f"{limit:.2f}"
        aid = self._acct_id()
        try:
            js = self._json(self._call(lambda: trade.order_v3.place_order(aid, [order]), "place order"), "place order")
        except BrokerError as e:
            rej = parse_rejection(str(e))
            if rej:
                raise rej from e
            raise                                       # timeout / 5xx: the order may or may not exist
        self._touch()
        return {"order_id": (js or {}).get("order_id")}

    def order(self, cid):
        trade, _ = self._clients()
        aid = self._acct_id()
        js = self._json(self._call(lambda: trade.order_v3.get_order_detail(aid, cid), "order status"), "order status")
        return self.parse_detail(js, cid)

    def order_raw(self, cid):
        """Webull's own order detail, unchanged (shown on the Go-live page when a test order does not fill)."""
        trade, _ = self._clients()
        aid = self._acct_id()
        return self._json(self._call(lambda: trade.order_v3.get_order_detail(aid, cid), "order status"), "order status")

    @staticmethod
    def parse_detail(js, cid):
        """Webull TH order detail: {client_order_id, combo_type, orders: [{status, filled_quantity, filled_price,
        commission: {actual_commission}, fees: [{type, actual_value}], ...}]}. Status: PENDING, SUBMITTED,
        PARTIAL_FILLED, FILLED, CANCELED (one L, seen on the TH test server), FAILED."""
        js = js.get("data", js) if isinstance(js, dict) and "orders" not in js and isinstance(js.get("data"), dict) else js
        items = js.get("orders") if isinstance(js, dict) else (js if isinstance(js, list) else None)
        items = [x for x in (items or []) if isinstance(x, dict)]
        it = next((x for x in items if x.get("client_order_id") == cid), items[0] if items else None)
        if not it or not it.get("status"):
            raise BrokerError("order not found at Webull")
        fee = _num((it.get("commission") or {}).get("actual_commission")) if isinstance(it.get("commission"), dict) else _num(it.get("commission"))
        fee = (fee or 0.0) + sum((_num(f.get("actual_value")) or 0.0) for f in (it.get("fees") or []) if isinstance(f, dict))
        status = str(it["status"]).upper()
        status = {"CANCELED": "CANCELLED", "PARTIALLY_FILLED": "PARTIAL_FILLED"}.get(status, status)   # Webull TH spells CANCELED
        return {"status": status, "filled_qty": _num(it.get("filled_quantity")) or 0.0,
                "avg_price": _num(it.get("filled_price")), "fee": fee}

    def cancel(self, cid):
        trade, _ = self._clients()
        aid = self._acct_id()
        self._json(self._call(lambda: trade.order_v3.cancel_order(aid, cid), "cancel order"), "cancel order")
        return True


_override: dict = {}


def get(mode: str, settings=None):
    """The broker for a mode. Tests can install fakes with set_override()."""
    if mode in _override:
        return _override[mode]
    if mode == "paper":
        return PaperBroker(settings)
    if mode in ("test", "live"):
        return WebullBroker(settings, env=mode)
    raise ValueError(f"unknown mode {mode}")


def set_override(mode, broker):
    if broker is None:
        _override.pop(mode, None)
    else:
        _override[mode] = broker


def enabled_modes(settings=None) -> list:
    s = settings or db.get_settings()
    return [m for m in MODES if s.get(f"mode_{m}") == "1"]
