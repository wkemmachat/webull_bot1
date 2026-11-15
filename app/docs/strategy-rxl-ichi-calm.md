<!--{"title": "RXL · Ichimoku cloud + calm + S&P check + dips", "group": "The strategies"}-->
# RXL · Ichimoku cloud + calm + S&P check + dips

This strategy holds **RXL (ProShares Ultra Health Care, 2x US health care)**. Its trend signal comes from the 1x health-care ETF **XLV**: the trend is on while XLV is above its **Ichimoku cloud**, XLV is calm and the S&P 500 (SPY) is above its 200-day average. When the cloud trend is off, it buys RXL on **dips**. Otherwise its money sits half in GLD and half in cash.

This is **pick A of round 1** of the research *Strategy research and stress tests* (15 Nov 2026). It beat [RXL · Calm guard + dips](#/docs/strategy-rxl-calm-guard) over 1, 3, 5 and 10 years and since 2007, with smaller falls. It passed 11 of 12 stress tests.

Added on 15 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from the daily bars of XLV, RXL and SPY:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | XLV's cloud trend is on, XLV is calm **and** SPY is above its SMA200 | RXL at min(100%, 60% ÷ RXL's 20-day volatility); the rest half GLD, half cash |
| **In · dip trade** | Cloud trend off and XLV closes with **IBS < 0.25**. Sold on the first close of XLV above the previous day's high, or after 5 days | 100% RXL |
| **In · one-day dip** | Cloud trend off and XLV's **RSI(2) < 5**; held for the next day only | 100% RXL |
| **Out · held back** | Cloud trend on, but XLV is jumpy or SPY is below its SMA200 | 50% GLD + 50% cash |
| **Out** | Cloud trend off, no dip | 50% GLD + 50% cash |

- **The cloud trend** uses Ichimoku settings 18 / 48 / 96:
  - The conversion line is the midpoint of the 18-day high and low; the base line uses 48 days. Span A is their average; span B is the midpoint of the 96-day high and low.
  - Both spans are drawn 48 days ahead, so today's cloud comes from data 48 days old.
  - The trend turns **on** when XLV closes above the top of the cloud and **off** when it closes below the bottom. **Inside the cloud nothing changes.**
  - To check it in TradingView, add *Ichimoku Cloud* with Conversion Line 18, Base Line 48, Leading Span B 96 and Lagging Span 49. TradingView counts the displacement from 1.
- **Calm**: the standard deviation of XLV's last 20 daily changes is below its 80th percentile over the last 252 trading days, today included.
- **S&P check**: SPY's close above its 200-day simple average.
- **Size**: 60% ÷ RXL's 20-day volatility a year, at most 100%. It is resized only when that moves more than 20 points. RXL's volatility is usually under 60%, so in practice it is mostly 100%. Dip buys are always 100%.
- **IBS** = (close − low) ÷ (high − low).
- **Orders**: they start at the next open, 10 lots 5 minutes apart. Between signals it trades only when a holding drifts more than 20 points from its target (the rebalance band).
- **Strategy type**: it is built on the bot's *Trend + calm gate* type. Three options were added for it: *Trend average type: ICHI* with the three Ichimoku lengths, the *Market check*, and *Dip trade: sell on PREVHIGH*. Other strategies of that type are not affected.

## When it trades

About **29 trades a year** over 10 years, against 20 for RXL · Calm guard + dips. It held RXL on about 70% of days (counting a part-held day by its share).

When XLV's volatility sits right at its gate, the calm check can switch on and off from one day to the next, and each switch is a full trade. This happened several times in October and November 2026.

The dip buys need the orders at the **next open**. Keep *Entries start* on "as soon as the market is open" (the default for this type).

## Backtest results

This is the bot's own code for this strategy (type `trend_gate`) on Yahoo daily prices to 13 Nov 2026:

- It decides at the close, trades at the next open and pays Webull's real fee (0.11% per buy and per sell). Cash earns nothing.
- RXL's prices start in February 2007.
- The bot reproduces the research exactly, in every period and every calendar year.
  - One detail had to be found first: the research's cloud trend stays unchanged while XLV is inside the cloud.
  - Without that, the backtest made 19.7% a year instead of 26.6%.
- The **Backtest** tab shows the same on the server.

| Period | **This strategy** | RXL · Calm guard + dips | RXL held |
|---|---|---|---|
| 1 year | +29.1% / **−20.5%** | +28.1% / −21.2% | **+45.4%** / −21.3% |
| 3 years | **+24.7% / −28.8%** | +17.7% / −34.6% | +23.9% / −36.1% |
| 5 years | **+16.6% / −28.8%** | +6.3% / −34.6% | +8.3% / −36.1% |
| 10 years | **+26.6% / −30.1%** | +18.6% / −34.6% | +17.3% / −51.0% |
| Since 2007 | **+25.2% / −32.8%** | +18.5% / −56.6% | +16.0% / −67.7% |

Each cell is the return a year / worst fall. 10-year Sharpe: 0.98 for this strategy, 0.68 for RXL · Calm guard + dips.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** | RXL · Calm guard + dips |
|---|---|---|
| Normal | **26.6% / −30.1%** | 18.6% / −34.6% |
| Fee 0.25% a side | **19.2% / −33.8%** | 15.3% / −39.6% |
| Fee 0.50% a side | 7.0% / −56.0% | **9.7% / −53.2%** |
| Every order a day late (bot test) | **18.8% / −32.2%** | 16.2% / −41.5% |
| Every order a day late (research test) | **16.1%** | 13.5% |

It does better in every test except the 0.50% fee. **Fees matter a lot here**: health care moves slowly, so each trade earns little. At 0.25% a side it already gives up 7 points a year, and at 0.50% it falls behind. At Webull's real fee of 0.11% it is clearly ahead. In the research's typical shuffled decade it made 25.4% / −38.2% against 18.6% / −45.0%.

### Year by year

| Year | **This strategy** | RXL · Calm guard + dips | RXL held |
|---|---|---|---|
| 2026 (to 13 Nov) | +25.9% | +24.9% | **+41.7%** |
| 2025 | **+49.8%** | +26.3% | +19.8% |
| 2024 | −9.4% | −9.1% | **−2.7%** |
| 2023 | **+3.6%** | −4.2% | −3.1% |
| 2022 | **+15.1%** | −6.9% | −15.3% |
| 2021 | +36.9% | +36.5% | **+48.0%** |
| 2020 | **+77.3%** | +39.8% | +19.2% |
| 2019 | +34.3% | +39.3% | **+40.4%** |
| 2018 | **+23.0%** | +14.0% | +3.4% |
| 2017 | +44.1% | +46.5% | **+46.9%** |
| 2016 | **+5.8%** | +5.5% | −8.8% |
| 2015 | −7.5% | **+16.4%** | +7.5% |
| 2014 | +19.6% | +35.3% | **+53.1%** |
| 2013 | +53.0% | +72.1% | **+94.0%** |
| 2012 | +32.1% | +38.2% | **+38.5%** |
| 2011 | +26.8% | **+35.0%** | +17.8% |
| 2010 | **+9.2%** | −6.0% | +5.0% |
| 2009 | **+57.5%** | +43.7% | +39.5% |
| 2008 | **+28.6%** | −27.7% | −47.8% |
| 2007 | **+8.7%** | −2.5% | +2.3% |

It was ahead of RXL · Calm guard + dips in 12 of 20 calendar years, and in 8 of the last 11 (2016 to 2026). It lost money in 2 years: 2015 (−7.5%) and 2024 (−9.4%).

## What to expect

- **Plan with much less than the backtest.** The research's walk-forward check picked rules using only the past and held them for the next year. On RXL that made only about **10% a year** over 10 years with a −36% worst fall, less than holding RXL (17.3%). The research put the chance that the best RXL rule is a fluke at 60%, the highest of all the ETFs it tested. Timing RXL has cut the falls; there is no solid evidence that it adds return. The Dashboard's expected return uses 26.8% a year (Oct 2016 – Oct 2026) minus the planning haircut.
- **It sits out a lot in jumpy markets.** In 2026 it held RXL on 53% of days. On 78 days the cloud trend was on but XLV was too jumpy.
- **Now (after the 13 Nov 2026 close) it is out.**
  - XLV (188.85) is well above its cloud (159.29–169.07) and SPY is above its SMA200, so the trend is on.
  - But XLV is jumpy: 1.32% daily volatility against a 1.19% gate.
  - So it would hold 49.5% GLD and the rest in cash.

## Expected return

<!--expected:rxl_ichi_calm-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

It trades the same ETF as RXL · Calm guard + dips. Money in both counts in each in *What your money is in*. The two rules are different, so you can split the RXL money between them or switch fully. Compare them for a few months on the strategy pages.

*A backtest is a history, not a promise. This is not financial advice.*
