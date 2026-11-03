<!--{"title": "Gold · Slow trend + calm + RSI dips", "group": "The strategies"}-->
# Gold · Slow trend + calm + RSI dips

Holds **UGL (ProShares Ultra Gold, 2x gold)** while gold is in a slow 4-hour up-trend, above its 50-day average and calm, and also buys short RSI(2) dips in gold's long up-trend. Cash the rest of the time. It is challenger **G1** of the research *Gold & Silver Challengers* (3 Nov 2026), the gold strategy that held up best in the full stress test, and is meant to replace [Gold #1](#/docs/strategy-gold1) and [Gold #2](#/docs/strategy-gold2).

Added on 3 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

From COMEX gold futures (GC=F), the same 4-hour bars as Gold #1 and Gold #2 (contract-roll gaps removed). Daily closes are the futures' session closes at 17:00 New York, built from those 4-hour bars.

| Part | Rule | Holds |
|---|---|---|
| **Trend** | 4H **Supertrend(150, 4)** up **and** the last daily close above its **50-day average** **and** gold is **calm** | 99% UGL |
| **Dip** | a daily close with **RSI(2) below 5** while above the **200-day average** opens a dip trade; it ends on the first daily close above the **5-day average** | 99% UGL |
| Neither | | cash |

- **Calm**: the standard deviation of gold's last 20 daily log changes is at or below its **80th percentile** of the last **252** trading days, today included.
- The trend part needs all three at once; when any one fails it sells (unless a dip trade is open).
- It changes its mind only when a 4-hour bar closes, like Gold #1 and #2. The daily parts change when the 14:00–17:00 New York bar closes.

## What it holds

UGL or cash. No GLD, no T-bill ETF (option in Parameters: *Cash ETF while flat*).

## When it trades

Like Gold #1 and Gold #2: the signal is read from 4-hour bars around the clock, orders go to Webull only in US market hours. Buys start from **22:00 Bangkok**, sells as soon as the US market is open, 10 lots 10 minutes apart (Execution settings). About **26 orders a year** (Gold #1: 45), in UGL about a third of the time.

## Research results

The research engine on OANDA spot gold hourly prices built into the bot's 4-hour bars (since 2006), the bot's order times, Webull's real fee (0.11% per buy and per sell), cash earning nothing. The bot's own code for this strategy (type `metal_trend_calm`) gave the same position at 99.97% of order times over the last 10 years and every one since Jul 2023.

| Period | A year | Worst fall | Gold #1 now | Gold #2 now | UGL held |
|---|---|---|---|---|---|
| 1 year | **+59.0%** | −15.8% | +42.4% / −21.2% | +29.8% / −29.0% | −16.7% / −53.9% |
| 3 years | **+59.6%** | −16.0% | +40.1% / −21.2% | +37.3% / −29.0% | +36.6% / −53.9% |
| 5 years | **+34.1%** | −17.4% | +25.4% / −21.2% | +23.2% / −29.0% | +22.0% / −53.9% |
| 10 years | **+22.6%** | −22.0% | +14.5% / −25.2% | +13.2% / −31.4% | +14.2% / −53.9% |
| Since 2009 | **+18.0%** | −42.9% | +5.2% / −57.7% | +3.2% / −66.3% | +9.4% / −75.7% |

The bot's **Backtest** tab uses Yahoo's last ~2 years of hourly futures prices and needs about 14 months of history before this strategy's first decision (the 252-day calm test), so it shows a short period only.

## Stress tests (3 Nov 2026)

- **Settings picked on 2009–2016 only, scored on 2016–2026:** 20.9% a year, worst fall −22.9% (the same test on Gold #1's family: 11.7%, −46.6%). 89% of its settings beat Gold #1 over those 10 years.
- **Fees:** at 0.50% per side 11.2% a year (Gold #1: −2.4%).
- **Orders late:** all orders only at the US open 20.5%; one day late 18.3%; two days late 21.6%.
- **Futures instead of spot bars** (Jul 2023 – Oct 2026): 51.2% vs 50.7% a year.
- **Noisy prices** (highs and lows moved ±0.2%, 16 runs): 20.6% to 23.5% a year.
- **The lost decade:** 2011–2020 +7.2% a year (Gold #1 −1.2%), worst fall −42.9%; from the Sep 2011 gold top to the Jul 2020 new high +3.9% a year (Gold #1 −4.3%).
- **2,000 reshuffled decades:** more return than Gold #1 in 98%, a smaller worst fall in 95%; a fall deeper than −40% in 8% (Gold #1: 69%).
- **Weaker:** the late-2016 drop (−17.6% vs −0.5%), the Covid crash (−7.7% vs +3.4%) and the 2023–24 rally (+36.7% vs +64.6%).

## Expected return

<!--expected:gold_trend_calm-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving the money from Gold #1 and Gold #2

1. Money → **Move**, from Gold #1 to this strategy, **Now, by today's signal**. If this strategy wants UGL today and Gold #1 holds UGL, the shares change hands inside the bot (no Webull order, no fee); otherwise Gold #1 sells and this strategy buys at its next signal.
2. The same from Gold #2.
3. Set Gold #1 and Gold #2 to **Paused** or **Stopped** (they have no money left), and turn LINE on here.

## Risks and what to expect

- **Settings chosen on the same history.** Plan on less than the backtest; the since-2009 number above includes the 2011–2015 gold bear market.
- **2x gold:** the worst fall since 2009 was −42.9% (2011–2015).
- **Long cash periods:** the calm test keeps it out after sharp moves, so it can miss the first part of a fast rally (2023–24).
- **Dip trades** last a few days; the orders still need to go out the next US session.

## Check it on TradingView

COMEX:GC1! 4-hour: built-in **Supertrend** (ATR length 150, factor 4). Daily: **Moving Average** 50, 200 and 5, **Relative Strength Index** 2. Health → Indicator cross-check recomputes the Supertrend, the daily average and the calm test the long way.
