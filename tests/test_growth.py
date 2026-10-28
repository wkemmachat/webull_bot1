"""Growth of $10,000 (strategy page, above Falls to expect): same days as the backtest, ETFs held, years, real line."""
from datetime import date, timedelta

import pytest

from app import perf


def _days(n):
    d0, out = date(2020, 1, 2), []
    d = d0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_growth_numbers(clean):
    days = _days(800)
    vals = [100 * (1.001 ** i) for i in range(800)]
    vals[300:400] = [vals[299] * (1 - 0.003 * k) for k in range(100)]          # a fall
    bench = {"QLD": [None] * 50 + [50 * (1.0005 ** i) for i in range(750)], "QQQ": [200.0] * 800}
    g = perf.growth("qld_regime", "paper", days, vals, bench)
    assert g["strategy"][0] == 10000 and g["end"] == pytest.approx(vals[-1] / vals[0] * 10000, rel=1e-6)
    assert g["days"][0] == str(days[0]) and g["days"][-1] == str(days[-1])
    assert g["worst"]["depth"] < -25 and g["worst"]["peak"] == str(days[299])
    q = g["bench"][0]
    assert q["symbol"] == "QLD" and q["values"][0] is None and q["from"] == str(days[50])
    i50 = g["days"].index(str(days[50])) if str(days[50]) in g["days"] else None
    if i50 is not None:
        assert q["values"][i50] == pytest.approx(10000 * vals[50] / vals[0], rel=1e-6)   # starts where the strategy is
    assert g["bench"][1]["end"] == pytest.approx(10000)
    yrs = {y["year"]: y for y in g["years"]}
    assert set(yrs) == {2020, 2021, 2022, 2023} and yrs[2023]["part"] and not yrs[2021]["part"]
    assert g["real"] is None
    assert len(g["days"]) <= 702
