<!--{"title": "SSO · Slow MACD + calm + dips", "group": "The strategies"}-->
# SSO · Slow MACD + calm + dips

Holds **SSO (ProShares Ultra S&P 500, 2x the S&P 500)** while **SPY** (the 1x S&P 500 ETF) is in a slow uptrend and calm. The uptrend is SPY's 60-day EMA above its 130-day EMA, which is a slow MACD above zero. When that trend is off, it buys SSO on **dips**. Otherwise it holds cash.

This is **pick A of round 1** of the research *Strategy research and stress tests* (15 Nov 2026), the SSO pick for more return. It beat [SSO · Calm guard + dips](#/docs/strategy-sso-calm-guard) over 1, 3, 5 and 10 years and since 2006. It passed 10 of 12 stress tests, the most of any SSO pick.

Added on 15 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from SPY's daily bar:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | EMA60 > EMA130 **and** calm | 100% SSO |
| **In · dip trade** | EMA60 ≤ EMA130 and SPY closes with **IBS < 0.20**; held until SPY closes above its **SMA5** | 100% SSO |
| **In · one-day dip** | EMA60 ≤ EMA130 and SPY's **RSI(2) < 10**; held for the next day only | 100% SSO |
| **Out · held back** | EMA60 > EMA130 but jumpy | cash |
| **Out** | EMA60 ≤ EMA130, no dip | cash |

- **EMA60 and EMA130** are seeded like TradingView's. To check them there, add **MACD** with fast length 60 and slow length 130: the strategy is in the trend while the MACD line is above 0.
- **Calm**: the standard deviation of SPY's last 20 daily changes is below its 90th percentile over the last 252 trading days, today included.
- **IBS** = (close − low) ÷ (high − low). An IBS near 0 means SPY closed near the day's low.
- Orders start at the next open, 10 lots 5 minutes apart. Between signals it trades only when SSO drifts more than 20 points from its target (the rebalance band).
- It is built on the bot's existing *Trend + calm gate* type. Three options were added for it, and other strategies of that type are not affected:
  - *Trend average type: XEMA* with *XEMA: fast EMA*
  - *Dip trade: opens on IBS*
  - *One-day RSI dip*

## What it holds

SSO or cash. No GLD and no T-bill ETF.

## When it trades

About **15 trades a year** over 10 years, against 10 for SSO · Calm guard + dips. It held SSO on about 82% of days.

The dip buys need the orders at the **next open**. Keep *Entries start* on "as soon as the market is open" (the default for this type).

## Backtest results

This uses the bot's own code for this strategy (type `trend_gate`) on Yahoo daily prices to 13 Nov 2026.
- It decides at the close, trades at the next open and pays Webull's real fee (0.11% per buy and per sell). Cash earns nothing.
- SSO's own prices start in June 2006.
- The bot reproduces the research exactly: the same figure in every period and every calendar year.
- The **Backtest** tab shows the same on the server.

| Period | **This strategy** | SSO · Calm guard + dips | SSO held |
|---|---|---|---|
| 1 year | +10.4% / **−18.0%** | +8.2% / −18.1% | **+19.5%** / −18.2% |
| 3 years | +32.1% / **−24.0%** | +29.6% / −21.6% | **+34.9%** / −35.2% |
| 5 years | **+21.9% / −29.1%** | +18.0% / −37.1% | +14.3% / −46.7% |
| 10 years | **+33.7% / −36.7%** | +28.6% / −37.1% | +23.1% / −59.3% |
| Since 2006 | **+28.7% / −40.8%** | +23.3% / −46.6% | +15.4% / −84.7% |

Each cell is the return a year / worst fall. The 3-year worst fall is −24.0% for this strategy against −21.6% for Calm guard. 10-year Sharpe: 1.14 for this strategy, 0.97 for SSO · Calm guard + dips.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** | SSO · Calm guard + dips |
|---|---|---|
| Normal | **33.7% / −36.7%** | 28.6% / −37.1% |
| Fee 0.25% a side | **31.0% / −37.2%** | 26.8% / −39.7% |
| Fee 0.50% a side | **26.4% / −39.1%** | 23.7% / −44.1% |
| Every order a day late (bot test) | 28.1% / −42.2% | **29.1% / −31.6%** |
| Every order a day late (research test) | 24.6% | **27.9%** |

It makes more at every fee level. Its weak spot is **late orders**: with every order a day late it makes less than SSO · Calm guard + dips, and its worst fall deepens to −42%. The dip buys only work when they fill at the next open. In the research's typical shuffled decade it made 29.3% / −40.8% against 23.8% / −39.6%.

### Year by year

| Year | **This strategy** | SSO · Calm guard + dips | SSO held |
|---|---|---|---|
| 2026 (to 13 Nov) | +7.6% | +5.4% | **+16.4%** |
| 2025 | **+29.0%** | +26.6% | +26.2% |
| 2024 | +43.0% | +40.3% | **+43.5%** |
| 2023 | +36.3% | +46.2% | **+46.6%** |
| 2022 | **−0.8%** | −19.2% | −39.0% |
| 2021 | +55.3% | +60.1% | **+60.6%** |
| 2020 | **+160.8%** | +52.0% | +21.5% |
| 2019 | +37.6% | +53.2% | **+63.5%** |
| 2018 | −21.3% | **−3.5%** | −14.6% |
| 2017 | +44.0% | +44.1% | **+44.4%** |
| 2016 | +22.0% | **+44.5%** | +21.3% |
| 2015 | −3.6% | **+0.1%** | −1.2% |
| 2014 | +7.5% | +15.1% | **+25.5%** |
| 2013 | +53.4% | +66.6% | **+70.5%** |
| 2012 | +24.5% | +30.8% | **+31.0%** |
| 2011 | **+32.2%** | −9.6% | −2.9% |
| 2010 | **+36.4%** | +29.2% | +26.8% |
| 2009 | **+52.2%** | +34.6% | +47.2% |
| 2008 | **+16.2%** | −22.1% | −67.9% |
| 2007 | +2.6% | **+5.0%** | +1.1% |

**Where its edge comes from.** It is ahead of SSO · Calm guard + dips in only 9 of 21 calendar years (5 of the last 11). It wins big in the crash years, 2008, 2011, 2020 and 2022, where its dip buys catch the rebounds. It trails in steady bull years such as 2012 to 2016, 2019 and 2023.
- **2020 alone** (+161% against +52%) makes most of the 10-year gap. Without 2020, the years 2017 to 2026 average about 23.5% a year for this strategy against 25.6% for SSO · Calm guard + dips.
- **2018 is the exception:** a falling year where it lost more, −21.3% against −3.5%.

## What to expect

- **Plan with much less than the backtest.** The research's walk-forward check picked rules using only the past and held them for the next year. On SSO that made about **19% a year** over 10 years with a −40% worst fall. That is less than holding SSO (23.1%). Timing SSO has reliably cut the fall more than it has added return, and this strategy is the research's *more return* pick. The Dashboard's expected return uses 35.0% a year (Oct 2016 – Oct 2026) minus the planning haircut.
- **Think of it as crash insurance with a cost.** Expect it to lag in calm, rising years and to pull ahead when the market breaks and rebounds.
- **Now (after the 13 Nov 2026 close) it is out.** SPY's EMA60 (760.80) is 1.5% above its EMA130 (749.61), so the trend is up, but SPY is jumpy: 1.39% daily volatility against a 1.14% gate. It would hold cash.

## Expected return

<!--expected:sso_macd_calm-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

It trades the same ETF as SSO · Calm guard + dips. Money in both counts in each in *What your money is in*. The two rules are different and win in different years: Calm guard does better in steady bull years, this one in crashes. Splitting the SSO money between them, for example half each, is reasonable, as is a full switch. Compare them for a few months on the strategy pages.

*A backtest is a history, not a promise. This is not financial advice.*
