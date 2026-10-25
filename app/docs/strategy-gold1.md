<!--{"title": "Gold #1 \u00b7 Supertrend + ADX", "group": "The strategies"}-->
# Gold #1 · Supertrend + ADX

Holds **2x gold (UGL)** while gold futures are in a confirmed up-trend on 4-hour bars, and T-bills (SGOV) otherwise. The ADX filter only buys when the market is really trending, which avoids many false starts.

## How it decides

| | Rule (4-hour COMEX gold futures, GC=F) |
|---|---|
| Buy | a 4H bar closes with **Supertrend(30, 2.5) up AND ADX(14) above 20**. If Supertrend turns up while ADX is 20 or lower, it waits for the first close with ADX above 20 |
| Sell | a 4H bar closes **below the Supertrend line** (ADX does not matter for the exit) |
| Bars | aligned with TradingView: the session opens 18:00 New York, bars 18–22, 22–02, 02–06, 06–10, 10–14, 14–17 |
| Contract rolls | the jump when Yahoo switches to the next futures contract is removed from the indicator history |

## What it holds

- Long: **99% UGL** (ProShares Ultra Gold, 2x the daily move of gold) + 1% cash.
- Flat: **99% SGOV** (0–3 month T-bills, earns the T-bill rate).

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | UGL held a year / worst fall | GLD held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+38.9%** | −23.1% | 0.98 | −18.8% / −51.0% | −3.2% / −26.4% |
| All (from 10 Jul 2024) | **+29.5%** | −23.1% | 0.84 | +38.4% / −51.0% | +25.2% / −26.4% |

- **Worst fall:** −23.1%, from 28 Jan 2026 to 29 Jul 2026; not yet back at the old high.
- **$10,000 became** $18,050 (+80%) from 10 Jul 2024 to 23 Oct 2026.
- **In the market** 54% of the days · **43.7 trades a year** · 50% of round trips made money (average +1.5%).
- Volatility 32% a year.

### Year by year

| Year | Strategy | UGL held | GLD held |
|---|---|---|---|
| 2026 (part) | **+28.0%** | −24.4% | −7.5% |
| 2025 | **+46.9%** | +137.6% | +63.7% |
| 2024 (part) | **−4.0%** | +17.0% | +10.4% |

## The research

10-year ETF test (Apr 2016 – Oct 2026, Gold & Silver research): **10.3% a year, worst fall −13.2%**. It waits for a trending market, so it trades a little less than Gold #2; return and worst fall were similar in the research.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:gold_sta-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Whipsaws:** in sideways gold markets it buys and sells several times at a small loss each; most losing trades are small.
- **2x leverage both ways:** a sharp gold drop between two 4H closes costs about twice the drop before the exit triggers.
- **Leveraged ETF decay:** UGL resets daily; in choppy markets it loses a little even when gold ends flat.
- **Webull:** UGL needs the Leveraged & Inverse ETF permission on your account (Go-live → Test trade).
- Expect long flat periods in T-bills, then fast gains when gold trends.

## Check it on TradingView

COMEX:GC1! on 4-hour bars: built-in **Supertrend** (ATR length 30, factor 2.5) and **ADX** (smoothing 14, DI length 14). Health check → Indicator cross-check compares the bot's values with a second calculation; type TradingView's values next to them.
