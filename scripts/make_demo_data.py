"""Write synthetic price files to data/csv so the app can run offline (DATA_SOURCE=csv): tests and demos.

  python scripts/make_demo_data.py [--dir data/csv] [--days 500]

GC/SI: hourly futures bars in COMEX session hours. ETFs: daily bars (QQQ, SMH, QLD, USD, GLD, BIL, SGOV, UGL, AGQ).
The prices are random walks, NOT real market data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def walk(seed, n, drift, vol, start):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, n)
    c = start * np.exp(np.cumsum(r))
    o = np.r_[start, c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, vol * 0.5, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, vol * 0.5, n)))
    return o, h, l, c


def hourly(seed, days, start, drift, vol, now):
    idx = pd.date_range(now - timedelta(days=days), now, freq="1h", tz="UTC")
    ny = idx.tz_convert("America/New_York")
    wd, hr = ny.weekday, ny.hour
    keep = ~((wd == 5) | ((wd == 6) & (hr < 18)) | ((wd == 4) & (hr >= 17)) | (hr == 17))
    idx = idx[keep][:-1]
    o, h, l, c = walk(seed, len(idx), drift, vol, start)
    return pd.DataFrame({"t": (idx.astype("int64") // 10 ** 9), "o": o, "h": h, "l": l, "c": c, "v": 1000})


def daily(seed, days, start, drift, vol, now):
    idx = pd.bdate_range(end=(now - timedelta(days=1)).date(), periods=days, tz="UTC")
    o, h, l, c = walk(seed, len(idx), drift, vol, start)
    return pd.DataFrame({"t": (idx.astype("int64") // 10 ** 9), "o": o, "h": h, "l": l, "c": c, "v": 1e6})


def lever(base: pd.DataFrame, k: float, start: float):
    r = base["c"].pct_change().fillna(0).values
    c = start * np.cumprod(1 + k * r)
    o = np.r_[start, c[:-1]]
    rng = np.random.default_rng(int(start))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, len(c))))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, len(c))))
    return pd.DataFrame({"t": base["t"], "o": o, "h": h, "l": l, "c": c, "v": 1e6})


def main(out: Path, days: int, now=None):
    now = now or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    out.mkdir(parents=True, exist_ok=True)
    gc = hourly(1, min(days, 700), 3600, 0.00006, 0.0028, now)
    si = hourly(2, min(days, 700), 44, 0.00008, 0.0045, now)
    gc.to_csv(out / "GC_1h.csv", index=False)
    si.to_csv(out / "SI_1h.csv", index=False)
    nd = int(days * 5 / 7) + 260
    qqq = daily(3, nd, 380, 0.0007, 0.012, now)
    smh = daily(4, nd, 180, 0.0008, 0.018, now)
    gld = daily(5, nd, 200, 0.0004, 0.009, now)
    for name, df in {"QQQ": qqq, "SMH": smh, "GLD": gld, "QLD": lever(qqq, 2, 70), "USD": lever(smh, 2, 50),
                     "UGL": lever(gld, 2, 40), "AGQ": lever(daily(6, nd, 30, 0.0004, 0.016, now), 2, 35),
                     "BIL": daily(7, nd, 91.0, 0.00015, 0.0003, now), "SGOV": daily(8, nd, 100.2, 0.00015, 0.0003, now),
                     "SPY": daily(9, nd, 500, 0.0005, 0.01, now)}.items():
        df.to_csv(out / f"{name}_1d.csv", index=False)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/csv")
    ap.add_argument("--days", type=int, default=500)
    a = ap.parse_args()
    print("wrote", main(Path(a.dir), a.days))
