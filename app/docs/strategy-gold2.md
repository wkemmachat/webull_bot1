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
- Flat: **cash** (until 26 Oct 2026 SGOV; cash saves Webull's fee on every switch, see below).

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | UGL held a year / worst fall | GLD held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+29.5%** | −21.4% | 0.78 | −12.5% / −51.0% | −0.2% / −26.4% |
| All (from 10 Jul 2024) | **+27.9%** | −21.4% | 0.79 | +38.9% / −51.0% | +25.1% / −26.4% |

- **Worst fall:** −21.4%, from 17 Apr 2026 to 29 Jul 2026; back at the old high on 24 Aug 2026.
- **$10,000 became** $17,578 (+76%) from 10 Jul 2024 to 26 Oct 2026.
- **In the market** 57% of the days · **46.3 trades a year** · 47% of round trips made money (average +1.4%).
- Volatility 33% a year.

### Year by year

| Year | Strategy | UGL held | GLD held |
|---|---|---|---|
| 2026 (part) | **+18.3%** | −23.5% | −7.5% |
| 2025 | **+51.2%** | +137.6% | +63.7% |
| 2024 (part) | **−1.8%** | +17.0% | +10.4% |

## The research

10-year ETF test (Apr 2016 – Oct 2026): **11.5% a year, worst fall −13.4%**. Slightly more return than Gold #1 with about the same worst fall, but more trades.

### Lower-cost: cash while flat (26 Oct 2026)

Webull Thailand charges **0.107% of every buy and every sell**. This strategy trades 30–45 times a year, and with SGOV as the flat
holding every switch traded two ETFs. In the bot's 2-year backtest, charging the real fee instead of 0.05% took the result from 30.8% to 23.7% a year.
Keeping **cash** while flat trades only UGL: **27.9%** a year over the same 2 years (cash earns no T-bill interest;
that is counted). The research's 10-year 11.5% a year is therefore planned as **9.0%** a year (the same fee loss
in proportion). A strategy that still had the old default was moved to cash once, on 26 Oct 2026; to go back, set
Parameters → *Cash ETF while flat* to SGOV.

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
