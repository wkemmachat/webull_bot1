<!--{"title": "Silver #2 \u00b7 Supertrend 10/3", "group": "The strategies"}-->
# Silver #2 · Supertrend 10/3

A faster trend follower on 4-hour silver futures: in **2x silver (AGQ)** while Supertrend(10, 3) is up, cash while it is down.

## How it decides

| | Rule (4-hour COMEX silver futures, SI=F) |
|---|---|
| Buy | a 4H bar closes **above the Supertrend(10, 3) line** |
| Sell | a 4H bar closes **below the line** |

## What it holds

- Long: **99% AGQ** (2x silver).
- Flat: **cash** (until 26 Oct 2026 SGOV; cash saves Webull's fee on every switch, see below).

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | AGQ held a year / worst fall | SLV held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+10.9%** | −59.9% | 0.69 | −29.4% / −86.9% | +15.0% / −53.9% |
| All (from 17 Jun 2024) | **+22.7%** | −59.9% | 0.67 | +14.4% / −86.9% | +28.6% / −53.9% |

- **Worst fall:** −59.9%, from 28 Jan 2026 to 30 Jan 2026; not yet back at the old high.
- **$10,000 became** $16,196 (+62%) from 17 Jun 2024 to 26 Oct 2026.
- **In the market** 52% of the days · **33.9 trades a year** · 52% of round trips made money (average +3.2%).
- Volatility 71% a year.

### Year by year

| Year | Strategy | AGQ held | SLV held |
|---|---|---|---|
| 2026 (part) | **−39.2%** | −66.1% | −24.4% |
| 2025 | **+194.4%** | +360.7% | +144.7% |
| 2024 (part) | **−9.5%** | −12.1% | −2.2% |

## The research

10-year ETF test (Apr 2016 – Oct 2026): **17.2% a year, worst fall −34.3%**: the highest return of the metals strategies in the research, with the deepest falls.

### Lower-cost: cash while flat (26 Oct 2026)

Webull Thailand charges **0.107% of every buy and every sell**. This strategy trades 30–45 times a year, and with SGOV as the flat
holding every switch traded two ETFs. In the bot's 2-year backtest, charging the real fee instead of 0.05% took the result from 25.6% to 20.6% a year.
Keeping **cash** while flat trades only AGQ: **22.7%** a year over the same 2 years (cash earns no T-bill interest;
that is counted). The research's 10-year 17.2% a year is therefore planned as **14.4%** a year (the same fee loss
in proportion). A strategy that still had the old default was moved to cash once, on 26 Oct 2026; to go back, set
Parameters → *Cash ETF while flat* to SGOV.

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
