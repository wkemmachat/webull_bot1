<!--{"title": "BIB · Rates + trend blend with IBS dips (Blend v)", "group": "The strategies"}-->
# BIB · Rates + trend blend with IBS dips (Blend v)

This strategy trades **BIB (ProShares Ultra Nasdaq Biotechnology)**, a 2x ETF on the Nasdaq biotech index. It reads its signals from biotech (**IBB**, **XBI**), credit (**LQD ÷ IEF**), rates (the **10-year Treasury yield** and **TLT**), the market (**SPY**, **IWM**) and **VIX**.

It is **Blend v**, the main pick of the BIB research after four rounds (26 Nov 2026). It holds **half rule S3v** and **half rule S2+v**, so BIB is held at 0%, 50% or 100%.

| | **S3v: rates rule (50%)** | **S2+v: trend rule (50%)** |
|---|---|---|
| **Hold BIB while** | Credit healthy (**LQD ÷ IEF** above its 100-day average) **and** the **10-year yield** below its **50-day average** **and** **TLT** above its **100-day average** | **XBI** above its close of a year ago (252 days) **and** credit healthy **and** **SPY** and **IWM** above their **200-day averages** |
| **Deep dip** (when not holding) | After **BIB** closes with **IBS < 0.05** while **XBI** is above its **200-day average**: buy; held until **IBB** closes above its previous day's high, 5 closes at most, or until XBI falls under its average | The same |
| **One-day dips** (when not holding) | **IBB IBS < 0.10** while **VIX** closes **above 20**: buy for one day | The same, **plus BIB IBS < 0.20** while VIX is above 20 |
| **Otherwise** | Cash | Cash |

- **IBS** = (close − low) ÷ (high − low) of the day.
- **One-day dips** are bought at the next open and sold at the following open, unless the next close is another dip day.
- **VIX:** the one-day dips only count when VIX is above 20. The research found dip buys lost money in calm years (2003–06) and made it in nervous ones. VIX settles at 16:15 New York, after the bot's first read at 16:07, so the bot fetches VIX again at 16:20 and decides the signal again before the next open.
- **Prices for the signals have dividends added back** (IBB, XBI, LQD, IEF, TLT, SPY, IWM). The 10-year yield (^TNX) and VIX are index levels.
- **Idle cash stays cash.** The research earned T-bill interest on idle cash, without the cost of trading in and out. In the bot that means buying and selling a T-bill ETF around about 56 trades a year. That lost money in the backtest (10 years: 25.7% a year instead of 29.2% at Webull's fee, 13.4% instead of 22.7% at 0.25%), so it is off.
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 10-point drift.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of BIB** first (Go-live checklist). The test trade also confirms that Webull Thailand lets you buy BIB.

## Backtest results

These are from the bot's own code for this strategy (type `rates_trend_blend`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing. BIB has traded since April 2010, so the 10-year figures use its real prices. Before that, BIB is modelled as 2 × IBB minus 3% a year. The backtest starts in Feb 2007, when XBI has a year of history.

| Period | **Blend v (this strategy)** | S3v alone | S2+v alone | BIB held | IBB held |
|---|---|---|---|---|---|
| 1 year | **+131% / −13.0%** | +150% / −13.0% | +112% / −14.2% | +48.8% / −18.9% | +26.9% / −9.8% |
| 3 years | **+71.4% / −24.6%** | +80.4% / −22.0% | +60.7% / −27.7% | +42.3% / −45.3% | +22.9% / −24.9% |
| 5 years | **+48.2% / −24.6%** | +48.5% / −22.0% | +46.4% / −27.7% | +8.1% / −55.8% | +7.4% / −32.1% |
| 10 years | **+29.2% / −26.3%** | +27.2% / −36.2% | +29.6% / −34.9% | +10.5% / −66.2% | +9.0% / −39.8% |
| Since Feb 2007 | **+32.5% / −33.8%** | | | +15.2% / −67.2% | +11.4% / −39.8% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. "S3v alone" and "S2+v alone" are the same code with one share set to 100%.

- **The blend works as intended.** Over 10 years each rule alone fell about 35%; half and half fell 26%, with a return between the two.
- **Research comparison (Blend v, Webull's fee):**

  | Period | Research | Bot |
  |---|---|---|
  | 1 year | +133% / −8.6% | +131% / −13.0% |
  | 3 years | 71.8% / −26.3% | 71.4% / −24.6% |
  | 5 years | 46.9% / −26.3% | 48.2% / −24.6% |
  | 10 years | 28.7% / −26.3% | 29.2% / −26.3% |

  - **The 1-year worst fall differs.** The bot's comes from a dip trade bought on 12 Nov 2026 and held through a falling week to 20 Nov (BIB −15%), sold on 23 Nov's rebound. The 1-year returns match, so that trade is in the research too; I could not find why its fall reads smaller. Plan with the bot's figure.
- **Worst falls:**
  - Over 10 years: Apr → Oct 2019, back to its peak by May 2020.
  - Since 2007: Feb → Dec 2014.
- **Activity:** about 56 trades a year, 60% of round trips won. It held BIB on 66% of days.
- **Where the return comes from (10 years):**
  - **Dip trades made most of it.** The one-day dips nearly tripled the money (+182%) on only 5% of days, and the deep dips more than doubled it (+131%) on 4.5% of days.
  - The hold rules added less: +74% with both holding, +37% with S3v only, +9% with S2+v only.

### Stress tests (10 years, a year / worst fall)

| Test | **Bot** | Research |
|---|---|---|
| Normal (fee 0.11% a side) | **29.2% / −26.3%** | 28.7% / −26.3% |
| Fee 0.25% a side | 22.7% / −27.6% | 22.2% / −28% |
| Fee 0.50% a side | 11.9% / −36.4% | |
| Every order a day late | 11.4% / −45.1% | 12.2% / −45% |

**Fills at the open decide it.** The dips are short, so late orders or wide spreads take most of the edge. BIB is thinly traded, so treat the 0.25% line as the realistic one.

### Year by year

| Year | **Blend v** | BIB held | IBB held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+123%** | +52.8% | +29.4% |
| 2025 | **+96.4%** | +59.2% | +28.0% |
| 2024 | −5.2% | −9.9% | **−2.4%** |
| 2023 | **+13.3%** | −1.1% | +3.8% |
| 2022 | **+46.9%** | −28.9% | −13.7% |
| 2021 | **+10.2%** | −6.0% | +1.0% |
| 2020 | 35.3% | **+39.8%** | +26.0% |
| 2019 | +3.7% | **+46.7%** | +25.4% |
| 2018 | **+1.8%** | −24.9% | −9.5% |
| 2017 | 34.8% | **+40.5%** | +21.1% |
| 2016 | **+11.6%** | −44.2% | −21.4% |
| 2015 | **+122%** | +13.9% | +11.6% |
| 2014 | −2.8% | **+66.8%** | +33.8% |
| 2013 | +68.8% | **+160%** | +65.5% |
| 2012 | 63.3% | **+66.8%** | +32.1% |
| 2011 | **+33.4%** | +15.6% | +11.7% |
| 2010 | +6.2% | **+25.2%** | +14.8% |
| 2009 | **+33.7%** | +21.5% | +15.2% |
| 2008 | **+66.3%** | −33.3% | −12.3% |
| 2007 (from Feb) | −13.8% | −2.6% | **+1.3%** |

It lags BIB in steady biotech rallies (2013, 2014, 2019) and makes its money in nervous and falling years (2008, 2015, 2016, 2022, 2025).

## What to expect

- **Plan for about 15–22% a year and a −40% to −50% fall.**
  - At 0.25% per trade, the 10-year result is 22.7% a year.
  - When the research re-picked its best rules each year using only past data, they made 15.5% a year at 0.25%, about the same as holding BIB, but with much smaller losing years.
  - In the research's resampled histories, 1 in 10 ten-year paths had a fall worse than −53%.
- **It needs prompt orders at the open.** A day late, it drops to 11% a year with a −45% fall.
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - **Credit is weak** (LQD ÷ IEF 0.8% under its average), so neither rule holds, even though rates are easing (10-year yield 4.85%, 4.4% under its average; TLT above its average).
  - For S2+v, XBI is up 31.5% over a year, but SPY (−1.9%) and IWM (−3.5%) are under their 200-day averages.
  - VIX is 28.3, but BIB and IBB closed near their highs (IBS 0.80 and 0.79), so there is no dip.

## Expected return

<!--expected:bib_blend_v-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- **BIB is the thinnest fund in the bot:** about $1.0 million a day over the last 60 days, at $60.91 a share on 25 Nov 2026. Keep the money in it small, about the size of a day's normal trading or less. Check the first fills against the open price.
- *What your money is in* shows it as its own **Biotech** group. It moves only partly with the Nasdaq and health-care strategies, so it spreads your risk.

*A backtest is a history, not a promise. This is not financial advice.*
