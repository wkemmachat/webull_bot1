<!--{"title": "Silver · Trend + silver leading, else 1x", "group": "The strategies"}-->
# Silver · Trend + silver leading, else 1x

The careful silver strategy: in a slow silver up-trend it holds **AGQ (2x)** at a modest size only while silver is above its 100-day average and leading gold; the rest of the up-trend it holds plain **SLV (1x silver)**. Cash in down-trends. It is challenger **S3** of the research *Gold & Silver Challengers* (3 Nov 2026), the silver strategy with the smallest falls, meant to run beside [Silver · Trend with gold's OK + vol size](#/docs/strategy-silver-gold-ok) in place of [Silver #1](#/docs/strategy-silver1) and [Silver #2](#/docs/strategy-silver2).

Added on 3 Nov 2026 **with no money** and LINE alerts off.

## How it decides

| Part | Rule | Holds |
|---|---|---|
| Trend | COMEX silver (SI=F) 4-hour **Supertrend(180, 4)** up | — |
| Strong | trend up **and** silver's daily close above its **100-day average** **and** the gold/silver ratio below its **100-day average** (silver leading) | AGQ at **40% ÷ (2 × silver's 20-day volatility)**, at most 99% |
| Weak | trend up but one of the two checks fails | **99% SLV** |
| Down | trend down | cash |

The gold/silver ratio is gold's daily close divided by silver's (17:00 New York session closes, from the same 4-hour bars). The AGQ size is resized only when it moves more than 10% of the size held.

## When it trades

Decided on each 4-hour close, buys from 22:00 Bangkok, sells as soon as the US market is open. About **40 orders a year**. SLV is a plain 1x ETF; no extra permission.

## Research results

OANDA spot prices built into the bot's 4-hour bars, the bot's order times, Webull's real fee. The bot's own code (type `metal_trend_sized`) gave the research position at 99.97% of order times since Oct 2016 (10 years 13.1% vs 13.4% a year).

| Period | A year | Worst fall | Silver #1 now | SLV held |
|---|---|---|---|---|
| 1 year | **+27.0%** | −26.0% | +51.2% / −51.7% | +3.2% / −57.7% |
| 3 years | **+24.2%** | −27.4% | +43.9% / −51.7% | +28.0% / −57.7% |
| 5 years | **+12.4%** | −27.4% | +29.3% / −51.7% | +14.8% / −57.7% |
| 10 years | **+13.4%** | −28.7% | +12.8% / −60.7% | +10.2% / −57.7% |
| Since 2009 | **+10.2%** | −64.8% | +3.1% / −87.6% | +7.9% / −76.1% |

## Stress tests (3 Nov 2026)

- **Falls:** in 2,000 reshuffled decades a fall worse than −60% happened in 14% (Silver #1: 79%); worst 3-year window −19.5% a year (Silver #1 −41.5%).
- **2011–2020:** +4.3% a year, worst fall −64.8% (Silver #1 −4.8%, −87.6%).
- **Weak spots:** settings picked on 2009–2016 only made 6.4% a year over 2016–2026; fees of 0.50% a side take it to −0.9%; it lags in fast silver rallies (2024–26: +82% vs Silver #1 +214%).
- **Together with S1** (half each, 10 years): 21.6% a year, worst fall −38.7%.

## Expected return

<!--expected:silver_lead_1x-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks

- Still silver: −65% since 2009 in the 2011–2015 bear market.
- Settings chosen on the same history; its out-of-sample result was weak, so plan on the low side.

## Check it on TradingView

COMEX:SI1! 4-hour **Supertrend** (180, 4); daily **Moving Average** 100; the ratio COMEX:GC1!/COMEX:SI1! with a 100-day **Moving Average**. Health → Indicator cross-check recomputes the Supertrend and the size's volatility the long way.
