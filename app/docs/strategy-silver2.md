<!--{"title": "Silver #2 \u00b7 Supertrend 10/3", "group": "The strategies"}-->
# Silver #2 · Supertrend 10/3

A faster trend follower on 4-hour silver futures: in **2x silver (AGQ)** while Supertrend(10, 3) is up, T-bills while it is down.

## How it decides

| | Rule (4-hour COMEX silver futures, SI=F) |
|---|---|
| Buy | a 4H bar closes **above the Supertrend(10, 3) line** |
| Sell | a 4H bar closes **below the line** |

## What it holds

- Long: **99% AGQ** (2x silver).
- Flat: **99% SGOV**.

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | AGQ held a year / worst fall | SLV held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+13.4%** | −59.9% | 0.71 | −34.6% / −86.9% | +10.3% / −53.9% |
| All (from 17 Jun 2024) | **+25.6%** | −59.9% | 0.70 | +14.4% / −86.9% | +28.7% / −53.9% |

- **Worst fall:** −59.9%, from 28 Jan 2026 to 30 Jan 2026; not yet back at the old high.
- **$10,000 became** $17,099 (+71%) from 17 Jun 2024 to 23 Oct 2026.
- **In the market** 52% of the days · **34 trades a year** · 52% of round trips made money (average +3.2%).
- Volatility 71% a year.

### Year by year

| Year | Strategy | AGQ held | SLV held |
|---|---|---|---|
| 2026 (part) | **−37.9%** | −66.1% | −24.4% |
| 2025 | **+199.9%** | +360.7% | +144.7% |
| 2024 (part) | **−8.1%** | −12.1% | −2.2% |

## The research

10-year ETF test (Apr 2016 – Oct 2026): **17.2% a year, worst fall −34.3%**: the highest return of the metals strategies in the research, with the deepest falls.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:silver_st-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- The same silver crash risk as Silver #1 (about −60% in the bot's 2-year backtest, January 2026).
- Faster than Silver #1: exits sooner, but also more whipsaws.
- Webull: AGQ needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

COMEX:SI1! 4-hour bars: **Supertrend** (ATR length 10, factor 3).
