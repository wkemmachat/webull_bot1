"""Good time to add money? (app/addmoney.py): percentiles from past days only, the times a strategy reached the add zone and
what came a year later, the verdict, and the plain-language LINE text."""
import numpy as np
import pandas as pd

from app import addmoney


def test_percentile_uses_only_past_days():
    v = np.array([100.0] * 800 + [90.0, 80.0, 95.0, 70.0])
    depth, pct = addmoney.past_pct(v)
    assert np.isnan(pct[:addmoney.WARM]).all()
    assert pct[800] == 100.0                             # deeper than every day before it (all at the high)
    assert pct[802] < pct[801]                           # 5% below is shallower than the 20% of the day before
    v2 = v.copy()
    v2[-1] = 10.0                                        # a later day changes nothing earlier
    assert np.array_equal(addmoney.past_pct(v2)[1][:-1], pct[:-1], equal_nan=True)


def _mean_reverting(seed=1, n=4200):
    """A strategy that recovers from its dips: deep days are followed by gains."""
    rng = np.random.default_rng(seed)
    trend = np.exp(np.arange(n) * 0.0012)
    dips = np.ones(n)
    for start in range(900, n - 400, 330):                # a fall of ~25% that heals within ~60 days
        d = np.r_[np.linspace(1, 0.75, 40), np.linspace(0.75, 1, 60)]
        dips[start:start + len(d)] = d
    noise = np.exp(rng.normal(0, 0.004, n))
    return pd.bdate_range("2008-01-01", periods=n), trend * dips * noise * 100


def test_entries_and_verdict_good():
    t, v = _mean_reverting()
    x = addmoney.from_series(t, v)
    assert x["n"] >= 6 and x["up_n"] == x["n"]           # every time it got deep, a year later it was higher
    assert x["verdict"] in ("good", "safer")
    z, a = x["zone_days"], x["any_day"]
    assert z["med"] > 0 and a["med"] > 0 and z["fall_p10"] >= a["fall_p10"] - 0.2
    assert x["zone_depth"] < 0 and x["buy_depth"] > x["zone_depth"]       # the 85th percentile is deeper than the 70th
    assert x["wait"] and 0 <= x["wait"]["better"] <= 1
    first = [e[0] for e in x["entries"]]
    assert first == sorted(first) and len(set(first)) == len(first)


def test_verdict_rules():
    a = {"up": 0.90, "med": 0.40, "fall_p10": -0.20}
    good = [("d", 0.5)] * 10
    assert addmoney.verdict({"up": 0.97, "med": 0.50, "fall_p10": -0.10}, a, good) == "good"
    assert addmoney.verdict({"up": 0.93, "med": 0.38, "fall_p10": -0.15}, a, good) == "safer"      # more often up, not by more
    assert addmoney.verdict({"up": 0.89, "med": 0.36, "fall_p10": -0.25}, a, [("d", 0.5)] * 7 + [("d", -0.1)] * 3) == "mixed"
    assert addmoney.verdict({"up": 0.60, "med": 0.0, "fall_p10": -0.3}, a, [("d", 0.1)] * 5 + [("d", -0.1)] * 5) == "none"
    assert addmoney.verdict({"up": 0.99, "med": 0.9, "fall_p10": 0.0}, a, good[:5]) == "none"          # too few falls to judge
    assert addmoney.label("good", True) == "Good time" and addmoney.label("good", False) == "Not yet" and addmoney.label("none", True) == "No signal"


def test_too_short_a_backtest_gives_nothing():
    t = pd.bdate_range("2024-01-01", periods=500)
    assert addmoney.from_series(t, np.linspace(100, 120, 500)) is None


def test_line_text():
    x = {"verdict": "good", "n": 29, "up_n": 28, "zone_days": {"med": 0.55, "p10": 0.2, "fall_med": -0.03}}
    t = addmoney.line_text("QLD · Split 2C", x, {"depth": -20.5, "pct": 100.0})
    assert t.startswith("▲ Good time to add money · QLD · Split 2C\nQLD · Split 2C is 20% below its high (100th percentile).")
    assert "28 of 29 times." in t and "every time" not in t and "$1,550" in t and "$1,200" in t and "$970" in t
