<!--{"title": "ROM · Trend + Vol + RSI & IBS dips", "group": "The strategies"}-->
# ROM · Trend + Vol + RSI & IBS dips

Holds **ROM (ProShares Ultra Technology, 2x US tech)** while the 1x tech ETF **IYW** is above its 150-day exponential average and calm. Below the average it buys RSI(2) dip trades and one-day dips after ROM closes near the low of its day. Cash the rest of the time. It is challenger **R1** of the research *2x ETF Strategy Challengers* (2 Nov 2026), the ROM strategy that held up best in the stress tests, and is meant to replace [ROM Trend + RSI(2)](#/docs/strategy-rom-tbd).

Added on 2 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move).

## How it decides

After each US close, from IYW's and ROM's daily bars (only days where both have a closed bar):

| State | Rule | Holds |
|---|---|---|
| **In · trend** | IYW closes above its **EMA150** and is **calm** | 99% ROM |
| **In · dip** | below EMA150: an RSI dip trade opens when **RSI(2) < 5** and closes on the first close above **SMA5**; or **ROM's IBS < 0.15** (held the next day only) | 99% ROM |
| **Out · jumpy** | above EMA150 but not calm, no dip | cash |
| **Out** | below EMA150, no dip | cash |

- **EMA150** is TradingView's "Moving Average Exponential" 150 (seeded with a simple average, as Pine does).
- **Calm**: the standard deviation of IYW's last 20 daily changes is below the **90th percentile** of the same number over the last 252 trading days, today included.
- **IBS** = (close − low) ÷ (high − low) of ROM's own day: 0 means it closed on its low.

Compared with ROM Trend + RSI(2): EMA150 instead of SMA150, the volatility filter, dip exit at SMA5 instead of SMA10, and the extra one-day IBS dips.

## What it holds

ROM or cash. Nothing else (options in Parameters: *Gold share when out*, *When out, hold*).

## When it trades

Decided after each US close; orders start at the **next market open**, 10 lots 5 minutes apart. About **10 round trips a year** (ROM Trend + RSI(2): 3), in ROM about 80% of the time.

The one-day dips need the orders to go out at the next open: in the stress tests, every trade one day late cost it 16 points a year (60% → 44%; ROM Trend + RSI(2) lost 2). Fills half way into the day still left it ahead (53% vs 48%).

## Backtest results

The bot's own code for this strategy (type `trend_gate`) on TradingView prices to 30 Oct 2026 (no dividends; ROM pays almost none), decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell). The research engine gave the same position on every day after the warm-up. The **Backtest** tab shows the server's numbers on Yahoo prices.

| Period | A year | Worst fall | Sharpe | ROM Trend + RSI(2) | ROM held |
|---|---|---|---|---|---|
| 1 year | **+16.3%** | −28.3% | 0.48 | +11.5% / −31.0% | +26.5% / −31.0% |
| 3 years | **+56.8%** | −29.4% | 1.19 | +52.2% / −31.6% | +50.5% / −47.8% |
| 5 years | **+43.3%** | −34.3% | 0.99 | +38.6% / −31.6% | +17.7% / −67.1% |
| 10 years | **+59.9%** | −34.3% | 1.32 | +49.7% / −37.6% | +36.2% / −67.1% |
| Since 2008 | **+42.0%** | −35.4% | 1.09 | +32.2% / −52.0% | +23.5% / −79.1% |

### Year by year

| Year | This strategy | ROM Trend + RSI(2) |
|---|---|---|
| 2026 (to 30 Oct) | +28.4% | +23.1% |
| 2025 | +60.0% | +67.1% |
| 2024 | +36.1% | +26.5% |
| 2023 | **+112.9%** | +93.8% |
| 2022 | +0.6% | −6.8% |
| 2021 | +63.5% | +76.9% |
| 2020 | **+164.5%** | +77.7% |
| 2019 | **+93.3%** | +50.4% |
| 2018 | +19.3% | +37.4% |
| 2017 | +77.5% | +79.9% |
| 2016 | +17.7% | +16.7% |
| 2015 | +4.6% | −7.0% |
| 2014 | +4.7% | +31.8% |
| 2013 | +34.6% | +36.9% |
| 2012 | +27.0% | +25.7% |
| 2011 | −11.9% | +2.9% |
| 2010 | +25.0% | +7.5% |
| 2009 | +117.0% | +113.4% |
| 2008 | **+32.2%** | −40.1% |

## Stress tests (2 Nov 2026)

Compared with ROM Trend + RSI(2) on the same prices:

- **2,000 simulated decades:** more return in 88% of them and a smaller worst fall in 74%; the chance of a fall worse than −50% is 17% vs 39%.
- **Fees:** at 0.25% per side 55% a year vs 49%; at 0.50% 48% vs 47%.
- **Crises:** 2008 +15% vs −48% (Jan 2008 – Mar 2009), COVID crash −16% vs −33%, Jul–Aug 2024 −17% vs −30%. Worse in the 2025 tariff crash (−18% vs −12%) and in 2011 (−22% vs +3%).
- **Noisy price feed** (highs and lows moved ±0.2%): 10 years between 56% and 61% a year.

## Expected return

<!--expected:rom_vol_ibs-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Settings chosen on the same history.** It kept working when each setting was nudged (90% of its neighbours passed) and in 2008–2016 (24% a year vs 15%), but plan on less than the backtest.
- **Same bet as ROM Trend + RSI(2)** (daily correlation 0.84). Run it instead, or split the ROM money half and half while it proves itself (10 years: 55.8% a year, worst fall −26.7%).
- **2x tech:** worst single day −23% and worst week −28% over 10 years (deeper than ROM Trend + RSI(2)'s −15% and −20%): a one-day dip can be bought just before a second down day.
- **ROM is thin** (about $5M a day): keep lots modest and use the limit offset.
- **Webull:** ROM already trades in ROM Trend + RSI(2), so its Test trade is done if that one runs.

## Check it on TradingView

IYW daily: **Moving Average Exponential** 150, **Moving Average** 5, **Relative Strength Index** 2. ROM daily: IBS = (close − low) / (high − low). AMEX:ROM.
