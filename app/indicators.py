"""Indicators written to match TradingView Pine Script v5 exactly.

- ta.rma / ta.ema are seeded with a simple average of the first `length` values,
  then updated recursively (rma: alpha = 1/length, ema: alpha = 2/(length+1)).
- ta.atr(length) = ta.rma(ta.tr(true), length); the first bar's true range is high - low.
- ta.supertrend(factor, atrPeriod) uses hl2 ± factor × ATR with the "final band" ratchet,
  and Pine's direction convention (-1 = uptrend, +1 = downtrend).
- ta.dmi(diLength, adxSmoothing) for +DI, -DI and ADX (Wilder's directional movement).
"""
import numpy as np


def _seeded(x, n, alpha):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    valid = np.where(~np.isnan(x))[0]
    if len(valid) == 0:
        return out
    start = valid[0]
    first = start + n - 1
    if first >= len(x):
        return out
    out[first] = x[start:first + 1].mean()
    for i in range(first + 1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def rma(x, n):
    return _seeded(x, n, 1.0 / n)


def ema(x, n):
    return _seeded(x, n, 2.0 / (n + 1))


def true_range(h, l, c):
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    pc = np.r_[np.nan, c[:-1]]
    with np.errstate(invalid="ignore"):
        tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def atr(h, l, c, n):
    return rma(true_range(h, l, c), n)


def supertrend(h, l, c, atr_period=10, factor=3.0):
    """Returns dict of arrays: line, direction (Pine: -1 up / +1 down), up (bool),
    upper (final upper band), lower (final lower band), basic_upper, basic_lower, atr, hl2."""
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    a = atr(h, l, c, atr_period)
    src = (h + l) / 2.0
    bu = src + factor * a
    bl = src - factor * a
    n = len(c)
    fu = np.full(n, np.nan)
    fl = np.full(n, np.nan)
    d = np.full(n, np.nan)
    st = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(a[i]):
            continue
        pl = fl[i - 1] if i > 0 and not np.isnan(fl[i - 1]) else 0.0   # nz(lowerBand[1])
        pu = fu[i - 1] if i > 0 and not np.isnan(fu[i - 1]) else 0.0   # nz(upperBand[1])
        cp = c[i - 1] if i > 0 else np.nan
        fl[i] = bl[i] if (bl[i] > pl or (i > 0 and cp < pl)) else pl
        fu[i] = bu[i] if (bu[i] < pu or (i > 0 and cp > pu)) else pu
        if i == 0 or np.isnan(a[i - 1]):
            d[i] = 1
        elif st[i - 1] == fu[i - 1]:
            d[i] = -1 if c[i] > fu[i] else 1
        else:
            d[i] = 1 if c[i] < fl[i] else -1
        st[i] = fl[i] if d[i] == -1 else fu[i]
    return {"line": st, "direction": d, "up": d == -1, "upper": fu, "lower": fl,
            "basic_upper": bu, "basic_lower": bl, "atr": a, "hl2": src}


def _fixnan(x):
    """Pine fixnan(): replace NaN with the last non-NaN value (leading NaNs stay NaN)."""
    out = np.array(x, dtype=float)
    last = np.nan
    for i in range(len(out)):
        if np.isnan(out[i]):
            out[i] = last
        else:
            last = out[i]
    return out


def dmi(h, l, c, di_length=14, adx_smoothing=14):
    """TradingView ta.dmi(diLength, adxSmoothing): returns dict plus_di, minus_di, adx.
    up = high - high[1]; down = low[1] - low
    +DM = up if up > down and up > 0 else 0;  -DM = down if down > up and down > 0 else 0
    TR uses ta.tr (no value on the very first bar); +DI = 100 * rma(+DM) / rma(TR)
    ADX = 100 * rma(|+DI - -DI| / (+DI + -DI), adxSmoothing)"""
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    up = np.r_[np.nan, h[1:] - h[:-1]]
    down = np.r_[np.nan, l[:-1] - l[1:]]
    with np.errstate(invalid="ignore"):
        pdm = np.where(np.isnan(up), np.nan, np.where((up > down) & (up > 0), up, 0.0))
        mdm = np.where(np.isnan(down), np.nan, np.where((down > up) & (down > 0), down, 0.0))
    tr = true_range(h, l, c)
    tr[0] = np.nan                      # ta.tr without handle_na: undefined on the first bar
    trur = rma(tr, di_length)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus = _fixnan(100 * rma(pdm, di_length) / trur)
        minus = _fixnan(100 * rma(mdm, di_length) / trur)
        s = plus + minus
        dx = np.abs(plus - minus) / np.where(s == 0, 1.0, s)
    adx = 100 * rma(dx, adx_smoothing)
    return {"plus_di": plus, "minus_di": minus, "adx": adx}


def highest_prev(h, n):
    """Highest high of the previous n bars, excluding the current bar (Pine: ta.highest(high, n)[1])."""
    h = np.asarray(h, dtype=float)
    out = np.full(len(h), np.nan)
    for i in range(n, len(h)):
        out[i] = h[i - n:i].max()
    return out


def lowest_prev(l, n):
    """Lowest low of the previous n bars, excluding the current bar (Pine: ta.lowest(low, n)[1])."""
    l = np.asarray(l, dtype=float)
    out = np.full(len(l), np.nan)
    for i in range(n, len(l)):
        out[i] = l[i - n:i].min()
    return out


def highest_incl(h, n):
    """Highest high of the last n bars including the current one: the breakout level for the NEXT bar."""
    h = np.asarray(h, dtype=float)
    out = np.full(len(h), np.nan)
    for i in range(n - 1, len(h)):
        out[i] = h[i - n + 1:i + 1].max()
    return out


def lowest_incl(l, n):
    l = np.asarray(l, dtype=float)
    out = np.full(len(l), np.nan)
    for i in range(n - 1, len(l)):
        out[i] = l[i - n + 1:i + 1].min()
    return out


def rsi(c, n=14):
    """TradingView ta.rsi(close, n): 100 - 100 / (1 + rma(gains, n) / rma(losses, n))."""
    c = np.asarray(c, dtype=float)
    ch = np.r_[np.nan, np.diff(c)]
    up = np.where(np.isnan(ch), np.nan, np.maximum(ch, 0.0))
    dn = np.where(np.isnan(ch), np.nan, np.maximum(-ch, 0.0))
    au, ad = rma(up, n), rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(ad == 0, np.where(au == 0, 50.0, 100.0), 100.0 - 100.0 / (1.0 + au / ad))
    out[np.isnan(au) | np.isnan(ad)] = np.nan
    return out


def sma(x, n):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        cs = np.cumsum(np.r_[0.0, x])
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out
