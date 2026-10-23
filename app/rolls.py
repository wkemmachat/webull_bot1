"""Contract-roll detection and back-adjustment for continuous futures (GC=F, SI=F).

When the data vendor switches the continuous series to the next contract, the price jumps by the
calendar spread (gold and silver usually trade in contango, so the jump is upward, about 0.3-2%).
A futures holder never earns that jump, so indicators should not see it. We detect it as a gap at
the first bar of a session that
  - is upward and between MIN_GAP and MAX_GAP,
  - is much larger than normal session-open gaps (> GAP_MULT x the median of the last 40),
  - happens in the last two weeks of a month or the first days of the next (when rolls happen),
  - is at least 35 days after the previous detected roll,
  - falls in one of the symbol's usual roll months.
All earlier prices are then multiplied by (new open / old close), so the most recent prices stay
exactly what the exchange shows and every older percentage move is preserved.
Gap-based detection is an estimate, used for history. While the bot runs on Yahoo data it also
records the vendor's contract code (e.g. GCZ26.CMX) every run, so a live roll is confirmed when the
code changes. All rolls are listed in Settings → Data and can be switched off there.
"""
import numpy as np
import pandas as pd

MIN_GAP = 0.004
MAX_GAP = 0.025
GAP_MULT = 3.5
MIN_DAYS_APART = 35
# Months in which the front contract usually rolls (TradingView/CME liquidity convention):
# gold rolls Jan→Apr, Mar→Jun, May→Aug, Jul→Dec, Nov→Feb; silver Feb→May, Apr→Jul, Jun→Sep, Aug→Dec, Nov→Mar.
ROLL_MONTHS = {"GC": (1, 3, 5, 7, 11), "SI": (2, 4, 6, 8, 11)}


def detect_rolls(df1h: pd.DataFrame, symbol: str = None):
    """Estimate past rolls in raw 1H data. Returns list of (timestamp_utc, ratio, gap).
    Used for history only; live rolls are confirmed from the vendor's contract code (see engine)."""
    if len(df1h) < 50:
        return []
    t = df1h.index
    dt = t.to_series().diff().dt.total_seconds().fillna(0).values
    session_first = dt >= 2 * 3600 - 1          # first bar after the daily break / weekend
    gap = (df1h.o.values / np.r_[np.nan, df1h.c.values[:-1]]) - 1
    idx = np.where(session_first & ~np.isnan(gap))[0]
    out = []
    last_t = None
    history = []
    for i in idx:
        g = gap[i]
        med = np.median(np.abs(history[-40:])) if len(history) >= 10 else 0.002
        history.append(g)
        ny = t[i].tz_convert("America/New_York") + pd.Timedelta(hours=6)   # trading date
        day = ny.day
        in_window = day >= 17 or day <= 5
        roll_month = ny.month if day >= 17 else (ny.month - 2) % 12 + 1
        if symbol in ROLL_MONTHS and roll_month not in ROLL_MONTHS[symbol]:
            continue
        if not in_window or not (MIN_GAP <= g <= MAX_GAP) or g < GAP_MULT * med:
            continue
        if last_t is not None and (t[i] - last_t).days < MIN_DAYS_APART:
            continue
        out.append((t[i], 1.0 + g, float(g)))
        last_t = t[i]
    return out


def apply_rolls(df1h: pd.DataFrame, rolls):
    """rolls: iterable of (timestamp_utc, ratio). Returns back-adjusted copy and the
    per-bar factor (adjusted = raw x factor)."""
    factor = pd.Series(1.0, index=df1h.index)
    for ts, ratio in rolls:
        factor[df1h.index < ts] *= ratio
    adj = df1h.copy()
    for col in ("o", "h", "l", "c"):
        adj[col] = df1h[col] * factor
    return adj, factor


def find_roll_bar(df1h: pd.DataFrame, start, end):
    """Within [start, end], the session-open bar with the largest upward gap: where a confirmed
    contract switch actually happened in the data. Returns (timestamp, ratio, gap) or None."""
    if df1h.empty:
        return None
    t = df1h.index
    dt = t.to_series().diff().dt.total_seconds().fillna(0).values
    gap = (df1h.o.values / np.r_[np.nan, df1h.c.values[:-1]]) - 1
    best = None
    for i in range(1, len(df1h)):
        if not (start <= t[i] <= end) or dt[i] < 2 * 3600 - 1 or np.isnan(gap[i]):
            continue
        if not (MIN_GAP * 0.5 <= gap[i] <= MAX_GAP):     # rolls in contango are upward, roll-sized gaps
            continue
        if best is None or gap[i] > gap[best]:
            best = i
    if best is None:
        return None
    return t[best], 1.0 + float(gap[best]), float(gap[best])
