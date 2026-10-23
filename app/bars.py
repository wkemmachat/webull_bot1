"""Turning 1-hour bars into TradingView-aligned 4-hour bars, and the CME metals session clock.

COMEX gold/silver trade Sunday 18:00 to Friday 17:00 New York time, with a daily break 17:00-18:00.
TradingView starts 4H bars at the session open, so the bars run (New York time):
18-22, 22-02, 02-06, 06-10, 10-14, 14-17 (the last one is 3 hours long).
All bucket arithmetic is done on New York wall-clock time without a time zone and converted back
afterwards, so daylight-saving changes never produce ambiguous times.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
SIX_H = pd.Timedelta(hours=6)


def _to_ny_wall(ts):
    """tz-aware timestamp(s) → naive New York wall-clock time."""
    return ts.tz_convert(NY).tz_localize(None)


def _from_ny_wall(naive):
    if isinstance(naive, pd.Timestamp):
        return naive.tz_localize(NY, ambiguous=False, nonexistent="shift_forward")
    return naive.tz_localize(NY, ambiguous=np.zeros(len(naive), dtype=bool), nonexistent="shift_forward")


def _start_wall(naive):
    return (naive + SIX_H).floor("4h") - SIX_H      # 18:00 → 00:00 of the trading day


def _end_wall(start_naive):
    if isinstance(start_naive, pd.Timestamp):
        return start_naive.replace(hour=17, minute=0) if start_naive.hour == 14 else start_naive + pd.Timedelta(hours=4)
    end = start_naive + pd.Timedelta(hours=4)
    return end.where(start_naive.hour != 14, start_naive + pd.Timedelta(hours=3))


def bucket_start_ny(ts) -> pd.Timestamp:
    """Start (tz-aware New York) of the 4H bucket containing this tz-aware timestamp."""
    return _from_ny_wall(_start_wall(_to_ny_wall(pd.Timestamp(ts))))


def bucket_end_ny(start_ny: pd.Timestamp) -> pd.Timestamp:
    """End of a 4H bucket. The 14:00 bucket ends at the 17:00 daily close."""
    return _from_ny_wall(_end_wall(_to_ny_wall(pd.Timestamp(start_ny))))


def in_session_wall(naive_index):
    """Boolean mask: is the market open during this New York wall-clock hour?"""
    wd = naive_index.weekday
    h = naive_index.hour
    closed = (wd == 5) | ((wd == 6) & (h < 18)) | ((wd == 4) & (h >= 17)) | (h == 17)
    return ~np.asarray(closed)


def market_open_ny(t_ny) -> bool:
    """Is COMEX metals trading at this New York time? (ignores exchange holidays)"""
    wd = t_ny.weekday()  # Mon=0 .. Sun=6
    h = t_ny.hour
    if wd == 5:
        return False
    if wd == 6:
        return h >= 18
    if wd == 4:
        return h < 17
    return h != 17


def to_4h(df1h: pd.DataFrame) -> pd.DataFrame:
    """df1h: index = bar start (UTC, tz-aware), columns o,h,l,c,v. Returns 4H bars with
    index = bucket start (UTC), 'end' (UTC), 'n' = number of 1H bars, 'last_hour' = start of the
    newest 1H bar inside. Hours outside the trading session are dropped first."""
    cols = ["o", "h", "l", "c", "v", "end", "n", "last_hour"]
    if df1h.empty:
        return pd.DataFrame(columns=cols)
    wall = _to_ny_wall(df1h.index)
    keep = in_session_wall(wall)
    df1h = df1h[keep]
    wall = wall[keep]
    if df1h.empty:
        return pd.DataFrame(columns=cols)
    start_wall = _start_wall(wall)
    key = _from_ny_wall(start_wall).tz_convert(UTC)
    g = df1h.groupby(key)
    out = pd.DataFrame({
        "o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
        "v": g["v"].sum(), "n": g["c"].size(),
    })
    out["last_hour"] = pd.Series(df1h.index, index=df1h.index).groupby(key).max()
    starts_wall = _to_ny_wall(out.index)
    out["end"] = _from_ny_wall(_end_wall(starts_wall)).tz_convert(UTC)
    out.index.name = "t"
    return out[cols]


def last_closed_bucket_end(now_utc: datetime, delay_min: int):
    """End time (UTC) of the most recent 4H bar that should be complete and available from the
    data provider at `now_utc`, given the provider delay."""
    ref = pd.Timestamp(now_utc).tz_convert(UTC) - pd.Timedelta(minutes=delay_min)
    t = ref.floor("h")
    for _ in range(24 * 4):
        start = bucket_start_ny(t)
        end = bucket_end_ny(start)
        if end.tz_convert(UTC) <= ref and market_open_ny(start):
            return end.tz_convert(UTC)
        t = t - pd.Timedelta(hours=1)
    return None


def next_bucket_end(now_utc: datetime):
    now = pd.Timestamp(now_utc).tz_convert(UTC)
    t = now.floor("h")
    for _ in range(24 * 4):
        start = bucket_start_ny(t)
        end = bucket_end_ny(start)
        if end.tz_convert(UTC) > now and market_open_ny(start):
            return end.tz_convert(UTC)
        t = t + pd.Timedelta(hours=1)
    return None
