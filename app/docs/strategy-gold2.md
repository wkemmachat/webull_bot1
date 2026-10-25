<!--{"title": "Gold #2 \u00b7 Supertrend 30/2.5", "group": "The strategies"}-->
# Gold #2 · Supertrend 30/2.5

The same Supertrend on 4-hour gold futures **without** the ADX filter: in whenever Supertrend is up. It reacts earlier than Gold #1 and catches more of each trend, at the cost of more false starts.

## How it decides

| | Rule (4-hour COMEX gold futures, GC=F) |
|---|---|
| Buy | a 4H bar closes **above the Supertrend(30, 2.5) line** (it turns up) |
| Sell | a 4H bar closes **below the line** |
| Bars and rolls | as Gold #1 (TradingView-aligned 4H bars, contract-roll gaps removed) |

## What it holds

- Long: **99% UGL** (2x gold).
- Flat: **99% SGOV** (T-bills).

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | UGL held a year / worst fall | GLD held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+32.2%** | −20.8% | 0.84 | −18.8% / −51.0% | −3.2% / −26.4% |
| All (from 10 Jul 2024) | **+30.8%** | −20.8% | 0.86 | +38.4% / −51.0% | +25.2% / −26.4% |

- **Worst fall:** −20.8%, from 17 Apr 2026 to 29 Jul 2026; back at the old high on 21 Aug 2026.
- **$10,000 became** $18,469 (+85%) from 10 Jul 2024 to 23 Oct 2026.
- **In the market** 58% of the days · **46.3 trades a year** · 47% of round trips made money (average +1.4%).
- Volatility 33% a year.

### Year by year

| Year | Strategy | UGL held | GLD held |
|---|---|---|---|
| 2026 (part) | **+20.5%** | −24.4% | −7.5% |
| 2025 | **+54.2%** | +137.6% | +63.7% |
| 2024 (part) | **−0.5%** | +17.0% | +10.4% |

## The research

10-year ETF test (Apr 2016 – Oct 2026): **11.5% a year, worst fall −13.4%**. Slightly more return than Gold #1 with about the same worst fall, but more trades.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:gold_st30-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- More trades than Gold #1, so more whipsaw losses in sideways markets.
- Same 2x and daily-reset risks as Gold #1; both gold strategies usually hold UGL at the same time, so together they are one bigger gold bet, not two independent ones.
- Webull: UGL needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

COMEX:GC1! 4-hour bars: **Supertrend** (ATR length 30, factor 2.5).
