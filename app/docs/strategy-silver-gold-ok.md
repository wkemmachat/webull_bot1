<!--{"title": "Silver · Trend with gold's OK + vol size", "group": "The strategies"}-->
# Silver · Trend with gold's OK + vol size

Holds **AGQ (ProShares Ultra Silver, 2x)** while silver's 4-hour trend is up **and gold agrees**, at a size that shrinks when silver is wild. Cash the rest of the time. It is challenger **S1** of the research *Gold & Silver Challengers* (3 Nov 2026) and is meant to take over, with [Silver · Trend + silver leading, else 1x](#/docs/strategy-silver-lead-1x), from [Silver #1](#/docs/strategy-silver1) and [Silver #2](#/docs/strategy-silver2).

Added on 3 Nov 2026 **with no money** and LINE alerts off. It trades only after you move money to it (Money → Move).

## How it decides

| Part | Rule |
|---|---|
| Trend | COMEX silver (SI=F) 4-hour **Supertrend(40, 2.5)** up |
| Gold's OK | COMEX gold (GC=F) 4-hour **Supertrend(30, 2.5)** up: the same signal as Gold #2, read from gold prices by this strategy itself |
| Size | AGQ weight = **70% ÷ (2 × silver's 40-day volatility)**, at most 99%; resized only when it moves more than 10% of the size held (about 1 resize a year) |
| Otherwise | cash |

Silver's volatility is the standard deviation of its last 40 daily log changes (17:00 New York session closes), a year. AGQ moves about twice as much, hence the 2 ×. In calm silver markets the size is 99%; after a crash it can fall to about 40%.

## When it trades

Like the other metals strategies: decided on each 4-hour close, buys from 22:00 Bangkok, sells as soon as the US market is open, 10 lots 10 minutes apart. About **50 orders a year**. The check waits until gold's 4-hour bar for the same 4 hours is in too, so a late gold price never decides on the previous bar (the strategy shows *Waiting for gold's 4H bar* meanwhile). LINE says **RESIZE** when only the AGQ size changes.

## Research results

OANDA spot silver and gold hourly prices built into the bot's 4-hour bars (since 2006), the bot's order times, Webull's real fee (0.11% per buy and per sell). The bot's own code (type `metal_trend_sized`) gave the research position at every order time since Oct 2016 and the same 10-year result (28.6% vs 28.5% a year).

| Period | A year | Worst fall | Silver #1 now | Silver #2 now | AGQ held |
|---|---|---|---|---|---|
| 1 year | **+140.5%** | −18.8% | +51.2% / −51.7% | +54.2% / −44.7% | −42.3% / −88.9% |
| 3 years | **+61.2%** | −35.3% | +43.9% / −51.7% | +48.6% / −44.7% | +18.0% / −88.9% |
| 5 years | **+48.4%** | −35.3% | +29.3% / −51.7% | +27.6% / −45.3% | +3.0% / −88.9% |
| 10 years | **+28.5%** | −50.2% | +12.8% / −60.7% | +12.1% / −69.7% | +0.6% / −88.9% |
| Since 2009 | **+12.2%** | −82.9% | +3.1% / −87.6% | +3.1% / −92.2% | −2.2% / −98.1% |

## Stress tests (3 Nov 2026)

- **Settings picked on 2009–2016 only, scored on 2016–2026:** 21.7% a year, worst fall −51.2%; 98% of its settings beat Silver #1 over those years.
- **Noisy prices** (16 runs): 24.9% to 28.8% a year. **Futures instead of spot bars** (Jul 2023 on): 65.7% vs 60.2%.
- **Since the Jan 2026 top:** +8.3% (Silver #1 −37.3%).
- **Weak spots:** if every order waited for the US open it made only 11.5% a year, and a full day late 14.8%: keep the bot's normal timing. The 2011–2015 silver bear market cost −81.5% (Silver #1 −84.8%).

## Expected return

<!--expected:silver_gold_ok-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving the money

Silver #1 and Silver #2 → this strategy and [Silver · Trend + silver leading, else 1x](#/docs/strategy-silver-lead-1x), half each (Money → Move, *Now, by today's signal*), on a weekday while COMEX trades. Then set Silver #1 and #2 to **Stopped** and turn LINE on here.

## Risks

- **2x silver** is the most violent market the bot trades: −50% over 10 years, −83% since 2009 even with these rules.
- **Settings chosen on the same history:** plan on less than the backtest.
- **Gold's OK** keeps it out of silver rallies that gold does not join.
- **Webull:** AGQ needs the Leveraged & Inverse ETF permission (already traded by Silver #1 and #2).

## Check it on TradingView

COMEX:SI1! 4-hour **Supertrend** (40, 2.5) and COMEX:GC1! 4-hour **Supertrend** (30, 2.5). Health → Indicator cross-check recomputes both and the size's volatility the long way.
