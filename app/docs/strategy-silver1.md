<!--{"title": "Silver #1 \u00b7 Donchian 30/15", "group": "The strategies"}-->
# Silver #1 · Donchian 30/15

A classic breakout: buys **2x silver (AGQ)** when silver futures make a new 30-bar high on 4-hour bars and sells on a new 15-bar low. Big winners in silver rallies, but silver is the most violent market the bot trades.

## How it decides

| | Rule (4-hour COMEX silver futures, SI=F) |
|---|---|
| Buy | a 4H bar closes **above the highest high of the previous 30 bars** |
| Sell | a 4H bar closes **below the lowest low of the previous 15 bars** |
| Bars and rolls | TradingView-aligned 4H bars, contract-roll gaps removed |

## What it holds

- Long: **99% AGQ** (ProShares Ultra Silver, 2x).
- Flat: **cash** (until 26 Oct 2026 SGOV; cash saves Webull's fee on every switch, see below).

## When it trades

A signal counts when a 4-hour futures bar closes (Yahoo is about 11 minutes late). Entries start not before **22:00 Bangkok** while the US market is open; exits start as soon as it is open. 10 lots, 10 minutes apart. Between signals nothing is traded unless a holding drifts more than 10% from its target (e.g. after Add money).

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

Yahoo keeps only about **2 years** of hourly futures prices, so the bot's backtest is short and covers an exceptional period for gold and silver. The research's 10-year test (below) is the better guide to what to expect.

| Period | A year | Worst fall | Sharpe | AGQ held a year / worst fall | SLV held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **−13.1%** | −73.0% | 0.44 | −29.4% / −86.9% | +15.0% / −53.9% |
| All (from 17 Jun 2024) | **+4.8%** | −73.0% | 0.44 | +14.4% / −86.9% | +28.6% / −53.9% |

- **Worst fall:** −73.0%, from 28 Jan 2026 to 24 Sep 2026; not yet back at the old high.
- **$10,000 became** $11,161 (+12%) from 17 Jun 2024 to 26 Oct 2026.
- **In the market** 48% of the days · **30.5 trades a year** · 42% of round trips made money (average +1.7%).
- Volatility 70% a year.

### Year by year

| Year | Strategy | AGQ held | SLV held |
|---|---|---|---|
| 2026 (part) | **−45.9%** | −66.1% | −24.4% |
| 2025 | **+111.3%** | +360.7% | +144.7% |
| 2024 (part) | **−2.3%** | −12.1% | −2.2% |

## The research

10-year ETF test (Apr 2016 – Oct 2026): **15.5% a year, worst fall −33.9%**.

### Lower-cost: cash while flat (26 Oct 2026)

Webull Thailand charges **0.107% of every buy and every sell**. This strategy trades 30–45 times a year, and with SGOV as the flat
holding every switch traded two ETFs. In the bot's 2-year backtest, charging the real fee instead of 0.05% took the result from 7.4% to 3.5% a year.
Keeping **cash** while flat trades only AGQ: **4.8%** a year over the same 2 years (cash earns no T-bill interest;
that is counted). The research's 10-year 15.5% a year is therefore planned as **12.7%** a year (the same fee loss
in proportion). A strategy that still had the old default was moved to cash once, on 26 Oct 2026; to go back, set
Parameters → *Cash ETF while flat* to SGOV.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:silver_dc-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Crash risk:** in late January 2026 silver fell about 30% within a few days; AGQ lost more than half its value in under a week, far faster than any 4-hour exit. The bot's 2-year backtest shows a worst fall of about −73% (the crash plus the slide that followed until September 2026). Size this strategy so that such a fall is bearable.
- The 15-bar exit is wide: it gives back a good part of each gain before selling.
- Both silver strategies usually hold AGQ at the same time.
- Webull: AGQ needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

COMEX:SI1! 4-hour bars: **Donchian Channels** length 30 (buy level) and a second one with length 15 (sell level). The bot uses the highs/lows of the *previous* bars, like the channel shifted by one bar.
