<!--{"title": "USD · SMH trend + SMH IBS-dip", "group": "The strategies"}-->
# USD · SMH trend + SMH IBS-dip

Holds **USD (ProShares Ultra Semiconductors, 2x chips)** while the 1x chip ETF **SMH** is above its 125-day average and calm, sized by USD's own volatility. When SMH is below its average, it buys USD for **one day** after SMH closes near the bottom of its day. Cash the rest of the time. It is challenger **U1** of the research *2x ETF Strategy Challengers* (2 Nov 2026), the USD strategy that held up best in the stress tests, and is meant to replace [USD Trend + IBS-dip](#/docs/strategy-usd-ibs).

Added on 2 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from SMH's and USD's daily bars (only days where both have a closed bar):

| State | Rule | Holds |
|---|---|---|
| **In · trend** | SMH closes above its **SMA125** and is **calm** | USD at min(100%, 40% ÷ USD's 20-day volatility), rest cash |
| **In · dip** | SMH below its SMA125 and **SMH's IBS < 0.25**; or above it but jumpy and **USD's IBS < 0.15** | 99% USD for the next day only |
| **Out · jumpy** | above SMA125 but not calm, no dip | cash |
| **Out** | below SMA125, no dip | cash |

- **IBS** = (close − low) ÷ (high − low): 0 means the day closed on its low. A one-day dip is held from the next open to the following open.
- **Calm**: the standard deviation of SMH's last 20 daily changes is below the **80th percentile** of the same number over the last **504** trading days (2 years), today included.
- **Size**: a new trend entry takes the size of the day; it is changed only when the size of the day moves more than 20 points (a RESIZE alert on LINE). Dip days are always 99%.

## What it holds

USD or cash. No GLD and no T-bill ETF (options in Parameters: *Gold share when out*, *When out, hold*).

## When it trades

Decided after each US close; orders start at the **next market open**, 10 lots 5 minutes apart. About **19 round trips a year** (fewer than USD Trend + IBS-dip's 22), in USD about 60% of the time.

**The orders must go out at the next open.** Its edge is the next day's bounce: in the stress tests, every trade one day late cut 10 years from 74% to 9% a year (USD Trend + IBS-dip: from 57% to 20%), and fills half way into the day cost about 22 points a year. Keep *Entries start* on "as soon as the market is open" (the default for this type) and do not pause it around a dip.

## Backtest results

The bot's own code for this strategy (type `trend_gate`) on TradingView prices to 30 Oct 2026 (no dividends), decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell). The research engine gave the same position on every day after the warm-up. The **Backtest** tab shows the server's numbers on Yahoo prices.

| Period | A year | Worst fall | Sharpe | USD Trend + IBS-dip | USD held |
|---|---|---|---|---|---|
| 1 year | **+99.6%** | −19.0% | 1.75 | +53.0% / −26.7% | +15.5% / −39.1% |
| 3 years | **+127.5%** | −29.4% | 1.81 | +66.1% / −32.0% | +101.8% / −64.0% |
| 5 years | **+86.2%** | −37.5% | 1.44 | +70.2% / −32.4% | +46.1% / −77.4% |
| 10 years | **+74.5%** | −37.5% | 1.37 | +56.5% / −38.4% | +49.6% / −77.4% |
| Since 2008 | **+49.6%** | −47.0% | 1.13 | +37.6% / −46.1% | +27.7% / −83.4% |

### Year by year

| Year | This strategy | USD Trend + IBS-dip |
|---|---|---|
| 2026 (to 30 Oct) | **+121.4%** | +73.7% |
| 2025 | **+128.0%** | +17.3% |
| 2024 | +82.9% | +83.9% |
| 2023 | +110.9% | +149.4% |
| 2022 | +1.4% | +24.4% |
| 2021 | +52.3% | +57.4% |
| 2020 | **+154.3%** | +63.3% |
| 2019 | **+60.2%** | +30.5% |
| 2018 | +20.0% | +26.1% |
| 2017 | +66.7% | +61.6% |
| 2016 | +14.9% | +7.5% |
| 2015 | −15.5% | −24.3% |
| 2014 | +35.5% | +37.2% |
| 2013 | +75.8% | +55.7% |
| 2012 | −14.3% | −0.1% |
| 2011 | −16.9% | −12.8% |
| 2010 | +43.7% | +34.9% |
| 2009 | +162.9% | +97.9% |
| 2008 | +29.4% | +26.9% |

## Stress tests (2 Nov 2026)

Compared with USD Trend + IBS-dip on the same prices:

- **2,000 simulated decades** (daily returns since 2008 reshuffled in month-long blocks): more return in 87% of them; the median worst fall is about the same (−45% vs −45%), and the chance of a fall worse than −50% too (30% vs 30%).
- **Fees:** at 0.25% per side 65% a year vs 41%; at 0.50% 50% vs 17% (it trades less).
- **Fills half way into the day:** 53% vs 46% a year.
- **Crises:** 2025 tariff crash +23% vs −19%; 2015–16 −12% vs −21%. Worse in the 2022 bear (−13% vs +16%) and the Jul–Aug 2024 chip drop (−21% vs −4%).
- **Noisy price feed** (highs and lows moved ±0.2%): 10 years between 67% and 78% a year.

## Expected return

<!--expected:usd_smh_ibs-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Settings chosen on the same history.** The research tested about 570,000 combinations; this one kept working when each setting was nudged (77% of its neighbours passed) and in 2008–2016, but plan on less than the backtest.
- **Same bet as USD Trend + IBS-dip** (daily correlation 0.84). Run it instead of USD Trend + IBS-dip, or split the USD money half and half while it proves itself (10 years: 66.6% a year, worst fall −34.7%).
- **2x chips:** the worst fall since 2008 was −47%; the longest time below a high was Feb 2011 – Dec 2013.
- **USD is thin** (a few million dollars a day): the bot's limit orders matter; keep lots modest.
- **Webull:** USD needs the Leveraged & Inverse ETF permission. It already trades in USD Trend + IBS-dip, so the Test trade on USD is already done if that one runs.

## Check it on TradingView

SMH daily: **Moving Average** 125. IBS = (close − low) / (high − low) of SMH's and USD's daily bars. AMEX:USD.
