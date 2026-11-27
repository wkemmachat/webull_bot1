<!--{"title": "UWM · Trend + credit + calm dips (A3 + R3)", "group": "The strategies"}-->
# UWM · Trend + credit + calm dips (A3 + R3)

This strategy trades **UWM (ProShares Ultra Russell 2000)**, a 2x ETF on US small companies. It reads its signals from **IWM**, the 1x Russell 2000 ETF. UWM has traded since January 2007, so the whole backtest runs on its real prices, not a model.

It runs **two rules** from the UWM research and holds **half of what each one holds**, in one UWM position. You asked for them combined on 27 Nov 2026 so that neither rule's weak spot decides the result.

| | Rule A3 | Rule R3 |
|---|---|---|
| **Holds while** | IWM above its **100-day EMA**, credit healthy (**LQD ÷ IEF** above its 100-day average), **SPY** above its 200-day average, IWM's volatility **under 35%** a year | IWM above its **150-day EMA**, credit healthy (**HYG ÷ IEF** above its 100-day average), SPY above its 200-day average, IWM's volatility **under 30%**, **and** investors taking risk (**XLY ÷ XLP** above its 100-day average) |
| **Hold size** | 99% | 75% |
| **When not holding** | Dip trade: after IWM closes near its low (**IBS < 0.15**) while IWM is calm, buy 100%; sell on a close above the previous day's high or after 5 days | The same dip trade |

**What it holds each day** (half A3 + half R3):

| A3 | R3 | Money in UWM |
|---|---|---|
| Holds | Holds | **87%** |
| Holds | Out | 50% |
| Out | Holds | 37% |
| Dip | Dip | **100%** (both rules use the same dip) |
| Dip | Holds | 87% |
| Out | Out | Cash |

- **Calm** means IWM's 20-day volatility (daily log changes × √252) is at or below its 90th percentile of the last 252 days.
- **IBS** = (close − low) ÷ (high − low) of IWM's day.
- **XLY ÷ XLP** compares consumer discretionary with consumer staples.
- R3 uses LQD ÷ IEF on days before HYG had 100 days of history (2007).
- **Prices for the signals have dividends added back**, as in the research. LQD, HYG and IEF pay every month; on plain prices HYG ÷ IEF would drift down by the gap in their yields and the credit checks would read "weak" far too often. Before this fix the bot's 3-year result was 34% a year instead of 46%.
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 10-point drift.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of UWM** first (Go-live checklist).

## Backtest results

These are from the bot's own code for this strategy (type `two_rule_mix`) on Yahoo daily prices to 25 Nov 2026: decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell), cash earning nothing. The same code with one rule's share set to 0 gives each rule alone.

| Period | **A3 + R3 (this strategy)** | A3 alone | R3 alone | UWM held | IWM held |
|---|---|---|---|---|---|
| 1 year | **+51.8% / −8.4%** | +67.1% / −10.1% | +37.1% / −8.2% | +12.5% / −30.5% | +10.8% / −15.7% |
| 3 years | **+45.8% / −23.9%** | +48.8% / −23.9% | +41.7% / −25.9% | +21.0% / −49.8% | +15.9% / −27.5% |
| 5 years | **+25.6% / −33.3%** | +26.7% / −33.0% | +23.8% / −35.0% | −0.6% / −55.4% | +5.1% / −27.5% |
| 10 years | **+24.7% / −33.3%** | +24.0% / −37.1% | +24.6% / −35.0% | +7.2% / −71.5% | +8.6% / −41.1% |
| Since Jan 2007 | **+23.5% / −38.1%** | +21.5% / −42.9% | +24.9% / −38.1% | +6.1% / −88.2% | +7.9% / −58.6% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall.

- **The combination works as intended.** Its returns sit between the two rules (above both over 10 years), and its worst falls are at or near the smaller of the two in every period.
- **Research comparison:**
  - The research's half-and-half figure (two separate halves, rebalanced yearly) was 26.9% / −33.2% over 10 years and 22.9% / −44.2% since 2007.
  - The research's A3 alone was 23.7% / −37.4% over 10 years, and the bot's matches it.
  - The research's R3 alone was 29.5% / −34.1%. The bot's R3 makes less (24.6% / −35.0%), and a separate rebuild agrees with the bot, so some detail of R3 is not in the research notes.
- **Activity:** about 54 trades a year over 10 years (many are small resizes when one rule changes), 62% of round trips won. It held UWM on 71% of days, 57% of its money on average.

### Stress tests (10 years, a year / worst fall)

| Test | **A3 + R3** |
|---|---|
| Normal (fee 0.11% a side) | **24.7% / −33.3%** |
| Fee 0.25% a side | 19.5% / −36.6% |
| Every order a day late | 19.7% / −44.4% |

### Year by year

| Year | **A3 + R3** | UWM held | IWM held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+55.6%** | +11.5% | +10.0% |
| 2025 | **+40.1%** | +13.6% | +12.7% |
| 2024 | **+16.6%** | +11.3% | +11.4% |
| 2023 | **+26.6%** | +22.6% | +16.8% |
| 2022 | **−13.4%** | −43.7% | −20.5% |
| 2021 | **+35.7%** | +23.9% | +14.5% |
| 2020 | **+112%** | +16.6% | +20.0% |
| 2019 | +8.8% | **+48.6%** | +25.4% |
| 2018 | **−9.7%** | −25.9% | −11.1% |
| 2017 | +13.3% | **+26.9%** | +14.6% |
| 2016 | +3.6% | **+41.2%** | +21.6% |
| 2015 | −3.9% | −12.3% | **−4.5%** |
| 2014 | −6.6% | **+6.4%** | +5.0% |
| 2013 | +67.4% | **+87.0%** | +38.7% |
| 2012 | +3.6% | **+30.6%** | +16.7% |
| 2011 | **−0.5%** | −18.3% | −4.4% |
| 2010 | **+62.7%** | +50.6% | +26.9% |
| 2009 | **+95.7%** | +42.9% | +28.5% |
| 2008 | **+36.6%** | −66.9% | −34.1% |
| 2007 (from Jan) | **+5.0%** | −12.7% | −1.5% |

It lags UWM in calm, steady up years (2012–2014, 2016–2017, 2019) and gains most in crashes and recoveries (2008–2010, 2020).

## What to expect

- **Plan lower than the backtest.** The research warns that on UWM, rules picked each year using only past data did **no better than holding UWM**. This is the third round of searching the same 20 years. The fairer guide is the nearby-settings middle: about 27% a year for R3 and 23% for A3 over 10 years, with falls of about −34% to −40%.
- **It needs prompt orders.** A day late, the 10-year result falls to 19.7% a year with a −44% fall.
- **Now (after the 25 Nov 2026 close) it is out, in cash.** Both rules are off:
  - IWM 268.87 is under both its EMAs (280.27 and 278.71).
  - Credit is weak (LQD ÷ IEF −0.8% and HYG ÷ IEF −2.4% vs their averages), and XLY ÷ XLP is 5.2% under its average.
  - SPY is 1.9% under its 200-day average.
  - IWM's volatility is 31% (calm line 24%), so no dips either.

## Expected return

<!--expected:uwm_a3_r3-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- It is the only strategy in **US small companies** (*What your money is in* shows it as its own group), so it adds something different from the Nasdaq, semiconductor and gold strategies.
- UWM is a large, liquid fund ($52 a share on 25 Nov 2026), so spreads are small. Run the Webull test trade first.

*A backtest is a history, not a promise. This is not financial advice.*
