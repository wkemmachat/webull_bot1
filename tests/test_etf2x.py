"""Weekly 2x ETF search for C2-7 Momentum 2x: name filter, the numbers that prove a usable 2x ETF, suggest / add / dismiss."""
import numpy as np
import pandas as pd
import pytest

from app import db, etf2x as X, notify, testtrade
from app import strategies as S
from conftest import NOW


def test_name_filter():
    ok = [("GraniteShares 2x Long COST Daily ETF", "COST", ""), ("Direxion Daily NVDA Bull 2X Shares", "NVDA", ""),
          ("Tradr 2X Long Costco Daily ETF", "COST", "Costco Wholesale Corporation"), ("T-Rex 200% Long COST", "COST", "")]
    bad = [("GraniteShares 2x Short COST Daily ETF", "COST", ""), ("Direxion Daily NVDA Bear 1X Shares", "NVDA", ""),
           ("Leverage Shares 3x Long NVDA", "NVDA", ""), ("Tradr 1.5X Long COST", "COST", ""), ("GraniteShares 2x Long NVDA Daily ETF", "COST", ""),
           ("Defiance Daily Target 2X Inverse COST", "COST", ""), ("Costco Wholesale Corporation", "COST", "")]
    for n, s, c in ok:
        assert X.name_ok(n, s, c), n
    for n, s, c in bad:
        assert not X.name_ok(n, s, c), n


def _series(n=200, seed=1, lev=1.0, vol=2_000_000, base=None):
    rng = np.random.default_rng(seed)
    r = base if base is not None else rng.normal(0.001, 0.02, n)
    c = 50 * np.cumprod(1 + lev * r)
    return pd.DataFrame({"c": c, "v": vol}, index=pd.bdate_range(end="2026-10-23", periods=len(r))), r


@pytest.fixture
def yahoo(monkeypatch):
    """Fake Yahoo: STOCK, a good 2x ETF, a 1x fund, a young ETF and a thin one."""
    stock, r = _series(250, seed=3)
    good, _ = _series(250, lev=2.0, base=r, vol=300_000)            # ~$15M+ a day
    onex, _ = _series(250, lev=1.0, base=r, vol=500_000)
    young, _ = _series(40, lev=2.0, base=r[-40:], vol=500_000)
    thin, _ = _series(250, lev=2.0, base=r, vol=500)
    data = {"STK": stock, "GOODL": good, "ONEX": onex, "YNGL": young, "THNL": thin}
    monkeypatch.setattr(X, "_history", lambda s: data.get(s))
    X._memo.clear()
    monkeypatch.setattr(X, "_spread_pct", lambda s: 0.1)
    return data


def test_yahoo_names_seen_in_real_search():
    """Names exactly as Yahoo's search returned them on 25 Oct 2026."""
    assert X.name_ok("GraniteShares 2x Long NVDA Daily ETF", "NVDA") and X.name_ok("Leverage Shares 2X Long NVDA Daily ETF", "NVDA")
    assert X.name_ok("Corgi AMD 2x Daily ETF", "AMD") and X.name_ok("Direxion Daily TSLA Bull 2X Shares", "TSLA")
    assert not X.name_ok("Graniteshares 2x Short NVDA Daily ETF", "NVDA") and not X.name_ok("Tradr 1.5X Short NVDA Daily ETF", "NVDA")
    assert not X.name_ok("xETFs NVDA Daily Income ETF", "NVDA")


def test_verify_numbers(yahoo):
    g = X.verify("GOODL", "STK")
    assert g["ok"] and 1.95 <= g["beta"] <= 2.05 and g["corr"] > 0.99 and g["days"] == 250
    assert not X.verify("ONEX", "STK")["ok"] and "does not move like 2x" in X.verify("ONEX", "STK")["why"][0]
    assert any("too young" in w for w in X.verify("YNGL", "STK")["why"])
    assert any("too little trading" in w for w in X.verify("THNL", "STK")["why"])
    assert X.verify("NOPE", "STK")["why"] == ["no prices on Yahoo"]


def test_scan_suggests_then_add_and_dismiss(monkeypatch):
    sid = "c27_mom2x"
    s = S.get(sid)
    before = s.params["etf_map"]
    from app import basket
    week, rk = basket.ranking_for(NOW.date())
    pool = s.params["pool"]
    target = next(st for st, _ in rk[:pool] if st not in s.etf_map())      # a large stock without a 2x ETF in the list
    stock, r = _series(250, seed=5)
    etf, _ = _series(250, lev=2.0, base=r, vol=400_000)
    monkeypatch.setattr(X, "_history", lambda sym: {target: stock, "ZZZL": etf}.get(sym))
    monkeypatch.setattr(X, "_spread_pct", lambda sym: None)

    def search(q):
        if q == f"{target} daily":
            return [{"symbol": "ZZZL", "name": f"Test 2X Long {target} Daily ETF", "type": "ETF"},
                    {"symbol": "ZZZS", "name": f"Test 2X Short {target} Daily ETF", "type": "ETF"}]
        return []
    monkeypatch.setattr(X, "_search", search)
    sent = []
    monkeypatch.setattr(notify, "send", lambda ev, text, **k: sent.append((ev, text)))
    try:
        out = X.scan(sid, now=NOW)
        row = out["stocks"][target]
        assert row["status"] == "found" and row["best"]["etf"] == "ZZZL" and [c["etf"] for c in row["checked"]] == ["ZZZL"]
        assert len(out["stocks"]) == pool + X.EXTRA
        assert all(v["status"] in ("mapped", "none", "found") for v in out["stocks"].values())
        assert sent and sent[0][0] == "etf2x" and f"{target} → ZZZL" in sent[0][1]
        # the same find next week: no second LINE message
        sent.clear()
        X.scan(sid, now=NOW)
        assert not sent
        v = X.view(sid)
        assert v["applies"] and any(r["stock"] == target and r["status"] == "found" for r in v["rows"])
        # dismiss: stays quiet and shows as dismissed
        X.dismiss(sid, target)
        assert X.scan(sid, now=NOW)["stocks"][target]["status"] == "dismissed"
        # add: written into the strategy's list, held as the ETF, testable on Go-live
        X.add(sid, target, "ZZZL")
        s2 = S.get(sid)
        assert s2.etf_map()[target] == "ZZZL" and s2.inst(target) == "ZZZL"
        assert "ZZZL" in testtrade.symbols()
        assert X.view(sid)["rows"] and next(r for r in X.view(sid)["rows"] if r["stock"] == target)["status"] == "mapped"
        with pytest.raises(ValueError):
            X.add(sid, target, "ZZZL")                                    # already there
        with pytest.raises(ValueError):
            X.add(sid, "AAPL", "ZZZL")                                    # one ETF per stock
    finally:
        S.update(sid, params={"etf_map": before})
        db.set_state(X._key(sid), None)


def test_only_for_2x_momentum():
    assert X.view("c27_mom") == {"applies": False}
    with pytest.raises(ValueError):
        X.scan("qld_regime")
    with pytest.raises(ValueError):
        X.start_scan("c27_mom2x")                                        # demo data: no Yahoo


def test_foreign_listings_and_crypto_wrappers_are_skipped(monkeypatch):
    monkeypatch.setattr(X, "_search", lambda q: [
        {"symbol": "TSLL", "name": "Direxion Daily TSLA Bull 2X Shares", "type": "ETF"},
        {"symbol": "TSLL.MX", "name": "Direxion Daily TSLA Bull 2X Shares", "type": "ETF"},
        {"symbol": "TSLL-USD", "name": "Direxion Daily TSLA Bull 2X ETF (Derivatives) USD", "type": "CRYPTOCURRENCY"}])
    assert [c["symbol"] for c in X.candidates("TSLA")] == ["TSLL"]
