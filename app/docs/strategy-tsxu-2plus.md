<!--{"title": "TSXU · Trend + calm + credit + dips (2+)", "group": "The strategies"}-->
# TSXU · Trend + calm + credit + dips (2+)

This strategy trades **TSXU (Direxion Daily Semiconductors Top 5 Bull 2X)**, a 2x ETF on an equal-weight basket of the five largest chip companies. In late 2026 those were NVIDIA, Broadcom, TSMC, Micron and SK Hynix; the basket changes every quarter. It reads all its signals from **SMH**, the 1x semiconductor ETF, which has a long history.

It is **Strategy 2+** of the TSXU research (26 Nov 2026). Nothing beat it in four rounds of challengers.

| | Rule |
|---|---|
| **Hold 100%** while all three are true | **Trend:** SMH above its **200-day EMA**, with a 1% band (on above EMA + 1%, off below EMA − 1%). **Calm:** SMH's 20-day volatility at or below its **90th percentile** of the last 252 days. **Credit:** **LQD ÷ IEF** above its **100-day average** |
| **Otherwise, dip buy** | After SMH closes near its low (**IBS < 0.25**), buy **100%** at the next open, or **75%** when SMH's volatility is above its **95th percentile** ("stormy"). Hold while each close is another dip day; sell at the open after a close that is not |
| **Otherwise** | Cash |

- **IBS** = (close − low) ÷ (high − low) of SMH's day.
- **Volatility** = standard deviation of SMH's daily log changes over 20 days.
- **LQD ÷ IEF** compares corporate bonds with Treasuries. When it falls below its average, credit is getting tighter.
- **Prices for the signals have dividends added back** (SMH, LQD, IEF), as in the research.
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 20-point drift.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of TSXU** first (Go-live checklist).

## It repeats the USD strategies

TSXU and USD are both 2x chip ETFs. The research found their daily moves were **0.96 correlated**, and this strategy's rules are close to **USD · Trend split** and **USD · SMH trend + IBS dip**. Money here is **not spread out**: *What your money is in* counts it in the same Semiconductors group as USD. Treat this and the USD strategies as one bet, and size them together.

## Backtest results

These are from the bot's own code for this strategy (type `trend_credit_dip`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing.

**TSXU listed on 1 Oct 2025.** Before then the backtest uses a **model of TSXU**: 2 × SMH's daily move, minus 5% a year for the fund's fee, financing and spread. The research modelled the top-5 basket instead. The bot uses SMH so the model does not depend on knowing in advance which companies became the top five. Over the research's years the two give close results.

| Period | **2+ (this strategy)** | Strategy 1 (no dips) | Same rules on USD | TSXU held* | SMH held |
|---|---|---|---|---|---|
| 1 year | **+232% / −42.1%** | +71.6% / −21.2% | +153% / −39.4% | −4.4% / −66.8% | +24.6% / −40.2% |
| 3 years | **+178% / −42.1%** | +120% / −29.5% | +192% / −40.1% | +48.2% / −66.8% | +38.4% / −40.2% |
| 5 years | **+99.9% / −42.1%** | +54.6% / −40.1% | +115% / −40.1% | +22.3% / −75.2% | +23.8% / −45.3% |
| 10 years | **+99.5% / −42.1%** | +61.6% / −40.1% | +110% / −40.1% | +38.8% / −75.2% | +29.2% / −45.3% |
| Since Dec 2002 | **+32.5% / −82.2%** | +19.1% / −87.6% | +36.7% / −82.4% | +17.7% / −94.6% | +17.0% / −67.9% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. *TSXU held uses the model before Oct 2025. The USD column trades USD (real prices from 2007) with the same SMH signals.

- **Research comparison (10 years):**
  - The research had 103.1% / −44.0%, and the bot has 99.5% / −42.1%.
  - 1 year: research 240% / −42.4%, bot 232% / −42.1%.
  - 3 years: research 191.5% / −44.0%, bot 178% / −42.1%.
  - 5 years: research 107.5% / −44.0%, bot 99.9% / −42.1%.
  - The small gaps come from the TSXU model (SMH instead of the top-5 basket) and the fee.
- **On real TSXU only** (2 Oct 2025 – 25 Nov 2026): +263% a year. It is **now in a −42.1% fall**, from its peak on 22 Sep 2026 to 20 Nov 2026.
- **Activity:** about 52 trades a year over 10 years, 61% of round trips won. It held TSXU on 72% of days.

### Before the research's window: 2002–2012

The research started in 2013. The bot's model goes back to Dec 2002, and **those ten years went badly**:

- 2002–2012 lost **7.1% a year**.
- The worst fall was **−82.2%**, from a peak in Jan 2004 to Nov 2008. It took until Jan 2018 to recover.
- 2004 lost 48% and 2005 lost 25%.
- **The hold rule is what failed.** Over 2002–2012 the days held on trend + calm + credit lost about 76% in total, while the dip buys made about +96% (+17% more from stormy dips). Chip prices went sideways in those years. They kept crossing the 200-day EMA, so the strategy bought near tops and sold after falls, and a 2x fund turns that into big losses.

SMH then held different companies (Intel, Texas Instruments, Applied Materials), and the model is only an estimate. Even so, it shows the rules can fail for years outside the AI chip boom. Since Oct 2013 the bot gets 74.1% a year with a −43.8% fall, close to the research's 75.7% / −44.0%.

### Stress tests (10 years, a year / worst fall)

| Test | **2+** | Research |
|---|---|---|
| Normal (fee 0.11% a side) | **99.5% / −42.1%** | 103.1% / −44.0% |
| Fee 0.25% a side | 86.5% / −43.9% | 89.7% / −45.3% |
| Every order a day late | 13.9% / −69.5% | 14.0% / −69.0% |

**It needs prompt orders.** A day late, almost all of the edge is gone, because the dip buys last only a day or two.

### Year by year

| Year | **2+** | TSXU held* | SMH held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+261%** | −8.1% | +17.3% |
| 2025 | **+229%** | +85.3% | +49.2% |
| 2024 | +53.0% | **+62.7%** | +39.1% |
| 2023 | +63.7% | **+166%** | +73.4% |
| 2022 | **+2.4%** | −64.9% | −33.5% |
| 2021 | **+88.8%** | +75.3% | +42.1% |
| 2020 | **+251%** | +87.5% | +55.5% |
| 2019 | +123% | **+141%** | +64.5% |
| 2018 | **+30.2%** | −27.3% | −9.1% |
| 2017 | +69.8% | **+77.6%** | +38.5% |
| 2016 | +37.0% | **+66.4%** | +35.5% |
| 2015 | −21.2% | −9.9% | **−0.3%** |
| 2014 | +22.0% | **+56.3%** | +30.2% |
| 2013 | +34.2% | **+64.5%** | +33.3% |
| 2012 | −18.2% | +7.7% | **+8.6%** |
| 2011 | −17.7% | −22.9% | **−6.5%** |
| 2010 | −4.9% | **+20.5%** | +16.5% |
| 2009 | +60.2% | **+109%** | +58.6% |
| 2008 | **+5.2%** | −77.7% | −45.8% |
| 2007 | −15.9% | −15.0% | **−3.5%** |
| 2006 | **−4.5%** | −24.1% | −8.2% |
| 2005 | −25.0% | **+10.1%** | +9.8% |
| 2004 | −48.0% | −43.8% | **−19.6%** |
| 2003 (from Dec 2002) | +59.7% | **+191%** | +87.3% |

## What to expect

- **Plan far lower than the 10-year backtest.** The 10 years are almost all AI chip boom. The expected return below uses the **since-2002 figure** (32.5% a year, −82% worst fall), the same way as RAM. The research itself advises planning on 50–60% a year with a −47% fall, which assumes the boom-era behaviour continues.
- **Big swings.** It held 100% of a 2x fund through −42% in Sep–Nov 2026. Falls of 40–50% are normal for it even in good years.
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - SMH 422.46 is 17.2% under its 200-day EMA (510.32).
  - SMH's volatility is 93% a year, above its calm line (63%) and in "stormy" territory.
  - Credit is weak (LQD ÷ IEF 0.8% under its average).
  - SMH closed near its high (IBS 0.98), so no dip buy for the next open.

## Expected return

<!--expected:tsxu_2plus-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- **Size it together with the USD strategies.** Moving money from a USD strategy to this one changes little; adding money on top doubles the chip bet.
- TSXU is a young, smaller fund ($26 a share on 25 Nov 2026). Spreads can be wider than USD's, especially at the open. Run the Webull test trade first, and check the fill price against the open.

*A backtest is a history, not a promise. This is not financial advice.*
