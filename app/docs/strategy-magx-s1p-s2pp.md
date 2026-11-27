<!--{"title": "MAGX · Mag 7 trend + RSI2 dips (half S1+, half S2++)", "group": "The strategies"}-->
# MAGX · Mag 7 trend + RSI2 dips (half S1+, half S2++)

This strategy trades **MAGX (Roundhill Daily 2X Long Magnificent Seven ETF)**, a 2x ETF on Apple, Microsoft, Alphabet, Amazon, NVIDIA, Meta and Tesla. It reads its signals from an **equal-weight basket of the seven stocks** that the bot builds itself, re-weighted to equal at the start of each quarter, like the fund.

It holds **half of Strategy 1+ and half of Strategy 2++** from the MAGX research (26 Nov 2026), in one MAGX position. You chose the mix on 27 Nov 2026. S1+ was the best all-round pick and S2++ the higher-return pick; together they keep most of S2++'s return with S1+'s smaller falls.

| | Strategy 1+ (half) | Strategy 2++ (half) |
|---|---|---|
| **Trend part** | **On** when the basket closes above its **previous 55-day high**; **off** below its **previous 20-day low**. Held only while the basket is **calm** (20-day volatility at or below its 90th percentile of 252 days), **credit** is healthy (**LQD ÷ IEF** above its 100-day average) and **SPY** is above its **200-day average** | The same |
| **Trend size** | **60% ÷ MAGX's 20-day volatility**, at most 100% | **80% ÷ MAGX's volatility**, at most 100% |
| **Deep dip** (trend part off) | After the basket's **2-day RSI** closes **below 5**: **75%** until the first close with RSI2 > 50, or 5 closes | The same |
| **One-day dip** (trend part off) | — | After RSI2 closes **below 10**: **100%** for a day (held while each close repeats it). The larger of this and the deep dip |
| **Otherwise** | Cash | Cash |

**What it holds:** half of the S1+ column plus half of the S2++ column. For example:

| Situation | Money in MAGX |
|---|---|
| Trend part on, MAGX volatility 40% a year | **100%** (both halves full) |
| Trend part on, MAGX volatility 70% a year | **~93%** (S1+ 86%, S2++ 100%) |
| Deep dip, RSI2 between 5 and 10 | **75%** |
| Deep dip and RSI2 below 10 | **88%** |
| One-day dip only (RSI2 5–10) | **50%** |
| Nothing | Cash |

- **RSI2** is Wilder's 2-day RSI of the basket's closes.
- **Volatility** is the standard deviation of daily log changes over 20 days, × √252.
- **Resizing:** each half's trend size changes only when the new size is **20 points or more** away from the one held, as in the research, so a held trend is not traded every day.
- **Prices for the signals have dividends added back** (the seven stocks, SPY, LQD, IEF).
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 10-point drift.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of MAGX** first (Go-live checklist). The test trade also confirms that Webull Thailand lets you buy MAGX.

## Backtest results

These are from the bot's own code for this strategy (type `mag7_mix`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing.

**MAGX listed on 29 Feb 2024.** Before then the backtest uses a **model of MAGX**: 2 × the basket's daily move, minus 8% a year for the fund's fee, financing and extra drag, as in the research. The model starts in Oct 2004, when five of the seven stocks were listed. Tesla joined in 2010 and Meta in 2012.

| Period | **Half + half (this strategy)** | S1+ alone | S2++ alone | MAGX held* | QQQ held |
|---|---|---|---|---|---|
| 1 year | **+24.4% / −13.3%** | +24.0% / −12.6% | +24.2% / −14.9% | −12.6% / −34.4% | +4.6% / −19.9% |
| 3 years | **+93.6% / −14.8%** | +75.3% / −13.9% | +111.7% / −16.5% | +38.0% / −54.2% | +18.4% / −22.8% |
| 5 years | **+63.3% / −20.4%** | +54.5% / −23.7% | +71.0% / −23.1% | +16.6% / −79.6% | +10.8% / −35.1% |
| 10 years | **+57.9% / −29.8%** | +52.8% / −31.2% | +62.3% / −29.7% | +51.5% / −80.1% | +19.0% / −35.1% |
| 2007–2013 (held out) | **+37.5% / −39.1%** | +40.8% / −30.8% | +32.9% / −46.7% | | |
| Since Oct 2004 | **+45.3% / −39.1%** | | | +49.6% / −90.9% | +14.7% / −53.4% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. *MAGX held uses the model before Mar 2024. The "S1+ alone" and "S2++ alone" columns are the same code with one share set to 100%.

- **Research comparison (half + half, return a year / worst fall):**

  | Period | Research | Bot |
  |---|---|---|
  | 1 year | 25.0% / −13.4% | 24.4% / −13.3% |
  | 3 years | 95.0% / −14.9% | 93.6% / −14.8% |
  | 5 years | 62.6% / −20.8% | 63.3% / −20.4% |
  | 10 years | 59.6% / −28.1% | 57.9% / −29.8% |
  | 2007–13 holdout | 38.6% / −39.3% | 37.5% / −39.1% |

  S1+ and S2++ alone match the research within about 2 points a year.
- **2007–2013 was a holdout.** The research never used those years to pick rules, and they include 2008, when MAGX's model fell 91%.
- **On real MAGX only** (Mar 2024 – Nov 2026): +84.9% a year, worst fall −14.8%.
- **Worst falls:**
  - Over 10 years: Sep 2020 → May 2021 (back to its peak by Nov 2021).
  - Since 2004: Jan → Jul 2010 (back by Mar 2012).
- **Activity:** about 31 trades a year (many are dip trades and resizes), 65% of round trips won. It held MAGX on 52% of days.
- **Where the return comes from:** almost all from the trend part. The dips add a little and fill the gaps.

### Stress tests (10 years, a year / worst fall)

| Test | **Half + half** |
|---|---|
| Normal (fee 0.11% a side) | **57.9% / −29.8%** |
| Fee 0.25% a side | 53.9% / −30.5% |
| Fee 0.50% a side | 46.9% / −31.8% |
| Every order a day late | 33.7% / −36.1% (research 34.6% / −36.3%) |

The dips need orders at the open. A day late, the 1-year result drops from +24% to +9%.

### Year by year

| Year | **Half + half** | MAGX held* | QQQ held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+26.1%** | −13.8% | +3.6% |
| 2025 | **+149%** | +26.2% | +20.8% |
| 2024 | 121% | **+131%** | +25.6% |
| 2023 | +37.0% | **+270%** | +54.9% |
| 2022 | **+15.0%** | −76.5% | −32.6% |
| 2021 | +32.6% | **+94.3%** | +27.4% |
| 2020 | +147% | **+256%** | +48.4% |
| 2019 | +56.7% | **+109%** | +39.0% |
| 2018 | **+6.7%** | −9.9% | −0.1% |
| 2017 | +52.0% | **+111%** | +32.7% |
| 2016 | +11.2% | **+47.9%** | +7.1% |
| 2015 | +31.6% | **+76.6%** | +9.4% |
| 2014 | **+35.7%** | +31.9% | +19.2% |
| 2013 | +146% | **+249%** | +36.6% |
| 2012 | +6.9% | **+21.7%** | +18.1% |
| 2011 | −4.2% | −4.6% | **+3.5%** |
| 2010 | −10.9% | +2.3% | **+20.1%** |
| 2009 | +93.0% | **+306%** | +54.7% |
| 2008 | **+66.1%** | −86.1% | −41.7% |
| 2007 | +78.9% | **+163%** | +19.0% |
| 2006 | +3.8% | **+44.2%** | +7.1% |
| 2005 | +14.2% | **+125%** | +1.6% |

It trails MAGX in most strong years and wins big in crash years (2008, 2022) and choppy ones (2018, 2025, 2026).

## What to expect

- **Plan lower than the backtest.** The seven stocks are hindsight picks, the winners of the last 20 years, which flatters both holding and the strategy. When the research re-picked its best rules each January using only past data, they made about 30–45% a year with falls of 40–50%. The expected return below uses the **since-2004 figure** (45.3% a year, −39.1%).
- **It overlaps QLD.** MAGX and QLD moved 0.89 together (real prices since Mar 2024). *What your money is in* shows MAGX as **Magnificent Seven**, counted inside US tech.
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - The basket is 12.3% under its 55-day high, and its breakout is off.
  - The basket is not calm (volatility 43% a year, calm line 29%).
  - Credit is weak (LQD ÷ IEF 0.8% under its average), and SPY is 1.9% under its 200-day average (716.70 vs 730.77).
  - RSI2 is 43, so there is no dip. The last dip trade ran 17–23 Nov 2026 (RSI2 fell to 3.7).

## Expected return

<!--expected:magx_s1p_s2pp-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- MAGX is a small fund: about $2.6 million a day traded over the last 60 days, at $49.28 a share on 25 Nov 2026. Keep the money in it moderate, and check the first fills against the open price.
- **Size it together with the Nasdaq strategies.** Moving money from a QLD strategy changes your risk little; adding money on top adds to the same bet.

*A backtest is a history, not a promise. This is not financial advice.*
