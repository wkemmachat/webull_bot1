<!--{"title": "RAM · Momentum + calm + one-day dips", "group": "The strategies"}-->
# RAM · Momentum + calm + one-day dips

This strategy trades **RAM (Roundhill T-REX 2x Long DRAM Daily Target ETF)**, a 2x ETF on DRAM, Roundhill's actively managed memory-chip fund. DRAM holds Micron (about 28%), Samsung (26%), SK Hynix (21%), Sandisk, Seagate, Western Digital, Kioxia and others. During US hours it moves mostly with **Micron (MU)**: the Korean and Japanese stocks are closed then.

| State | Rule | Holds |
|---|---|---|
| **In · momentum + calm** | **MU and SMH** are both above their close of **126 trading days** ago, **MU** is above its close of **20 days** ago, **and** SMH is **calm** | **100% RAM** |
| **In · one-day dip** | The hold rule is off and RAM closes near its low (**IBS < 0.10**) | 100% RAM, bought at the next open and sold at the open after |
| **Out** | Neither | Cash |

This is **rule A** of the research *RAM (2x memory ETF): two best strategies* (26 Nov 2026). Round 2 then tested about 460,000 variations and found none that held up better, so A was kept. You chose A over rule B (vol-sized, no dips), which had smaller falls and was less hurt by late fills.

Added on 26 Nov 2026 **with no money** and LINE off. You allowed it on Live, but first:
- run a **Webull test trade of RAM** (Go-live checklist);
- **start small**.

## Read this first

- **RAM has 5 months of real prices** (it listed on 24 Jun 2026), all from one extreme period. It closed at $3.70 on 25 Nov 2026, 89% under its high. At that price a one-cent spread costs 0.27% a trade.
- **The backtest before June 2026 is a model**: 2 × the daily move of a US memory basket (Micron 70%, Seagate 15%, Western Digital 15%) minus 18.5% a year, joined to RAM's first close.
  - The research's own model also included Samsung, SK Hynix and Kioxia. Its 10-year result was a little higher (79.7%), with a similar fall.
  - Before RAM listed, the dip signals come from the model's daily bar, so they are approximate.
- **The 10-year headline is the 2025–26 memory boom.** In 2025 the strategy made +271% and in 2026 +770%. Plan from the years before it.
- **It needs prompt orders.** With every order a day late, the 10-year result falls from 73.7% to 30.5% a year and the worst fall deepens to −81%. The one-day dips are the fragile part.

## How it decides

After each US close, from daily bars; orders go out at the next open:

- **Momentum**: MU's close above its close 126 trading days earlier (about 6 months), and the same for SMH.
- **Fast check**: MU's close above its close 20 trading days earlier (about a month).
- **Calm**: the standard deviation of SMH's last 20 daily log changes is at or below its 90th percentile of the last 504 trading days (about 2 years), today included.
- **IBS** = (close − low) ÷ (high − low) of RAM's own daily bar.
- **Orders**: 5 lots 1 minute apart from the open. A held position is traded back to its target only after a 20-point drift.

TradingView: MU and SMH daily, close vs close 126 and 20 bars back; for the calm check, the standard deviation of log(close/close[1]) over 20 days.

## Backtest results

These are from the bot's own code for this strategy (type `momentum_calm`) on Yahoo daily prices to 25 Nov 2026. Decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell), cash earning nothing.

| Period | **This strategy** | RAM held (modelled before Jun 2026) | Micron held |
|---|---|---|---|
| 1 year | **+848% / −62.5%** | +112% / −88.6% | +168% / −51.0% |
| 3 years | **+224% / −62.5%** | +116% / −88.6% | +98.8% / −57.6% |
| 5 years | **+103% / −62.5%** | +34.9% / −88.6% | +49.2% / −57.6% |
| 10 years | **+73.7% / −62.5%** | +25.1% / −91.4% | +40.8% / −57.6% |
| Since Dec 2002 | **+34.9% / −71.1%** | −2.2% / −99.4% | +17.3% / −90.9% |
| 8 years before the boom (Nov 2016 – Nov 2024) | **+29.3% / −44.5%** | +3.1% / −89.9% | |
| Since RAM listed (real prices, 24 Jun 2026) | −15.0% / −62.5% | −84.4% / −87.4% | |

Each cell is the return a year (the 1-year cell and the since-listing cell are totals) / the worst fall.

- The research's numbers: 10 years 79.7% / −62.5%, before the boom 20.6%, since RAM listed −14.9%. The bot's backtest matches within a few points. The since-listing figure is on real prices and matches almost exactly.
- About 40 trades a year over 10 years, 52% of round trips won. It held RAM on 41% of days.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** |
|---|---|
| Normal (fee 0.11% a side) | **73.7% / −62.5%** |
| Fee 0.25% a side | 64.3% / −63.2% |
| Every order a day late | 30.5% / −80.7% |

### Year by year

| Year | **This strategy** | RAM held (modelled) | Micron held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+770%** | +49.8% | +111% |
| 2025 | +271% | **+659%** | +240% |
| 2024 | −11.7% | −25.8% | **−1.0%** |
| 2023 | +23.1% | **+124%** | +71.9% |
| 2022 | **−19.4%** | −80.7% | −45.9% |
| 2021 | **+30.9%** | +30.6% | +24.2% |
| 2020 | **+76.1%** | −0.6% | +39.8% |
| 2019 | +73.8% | **+110%** | +69.5% |
| 2018 | **+28.7%** | −60.1% | −22.8% |
| 2017 | +52.0% | **+110%** | +87.6% |
| 2016 | **+80.5%** | +42.4% | +54.8% |
| 2015 | −20.4% | −85.2% | −59.6% |
| 2014 | −19.9% | **+76.1%** | +61.0% |
| 2013 | +348% | **+560%** | +243% |

The earlier years (2002–2012) are on the Backtest tab. They include long losing stretches: −21.5% in 2007 and −42.7% in 2011. It lost money in 10 of the 23 full years.

## What to expect

- **The Dashboard plans with 34.9% a year and a −71% fall**: the since-2002 backtest, not the 10 years, which the boom dominates. The research advises planning for falls of 50–65%; since 2002 the worst was −71%.
- **Long flat or losing stretches are normal for it.** It is out of the market about 60% of days, and memory chips go through deep busts (2008, 2011, 2015, 2022).
- **Now (after the 25 Nov 2026 close) it is out, in cash**: MU is 34.9% and SMH 29.6% under their levels of 126 days ago, MU is 38.8% under its level of 20 days ago, and SMH is jumpy.

## Expected return

<!--expected:ram_mom_calm-->

How it is worked out: [Expected returns](#/docs/expected-returns). This strategy uses its since-2002 backtest instead of the 10 years.

## Moving money to it

- It is the only strategy in **Memory chips** (*What your money is in*). Memory moves with semiconductors, though, so on a bad chip day it falls with USD (2x semis).
- Run the Webull test trade first, keep it small, and check the first Live fills against the open: the dips need next-open fills.

*A backtest is a history, not a promise. This is not financial advice.*
