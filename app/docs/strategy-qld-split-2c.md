<!--{"title": "QLD · Split 2C (3 strategies, a third each)", "group": "The strategies"}-->
# QLD · Split 2C (3 strategies, a third each)

Trades **QLD (ProShares Ultra QQQ, 2x Nasdaq-100)** from **QQQ**, like [QLD Trend + bear-dip + Vol](#/docs/strategy-qld-tbdv). The difference is that the money is **split into three legs, a third each**. Each leg is a complete strategy with its own rules, and when a leg is out its third parks half in GLD and half in cash. The share in QLD is the sum of the legs that are in, each sized by its own rule. It moves in steps of about a third.

This is **split C of round 2** of the research *Strategy research and stress tests* (15 Nov 2026), the best QLD pick after three rounds. Over 10 years it kept almost all of the best single rule's return, and its worst fall was −21% instead of −28%. It passed 9 of 11 stress tests against the bot's best QLD strategy. Round 3 found nothing that clearly beat it.

Added on 15 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## The three legs

After each US close, from the daily bars of QQQ (with its volume) and QLD. Each leg is a strategy type the bot already has, with these settings:

| Leg (⅓ of the money) | Trend | Calm gate (QQQ) | Size when in | When the trend is off |
|---|---|---|---|---|
| **A** · EMA100 trend + dips (type *Trend + calm gate*) | QQQ close above its **EMA100** | 80th percentile | 99% | RSI(2) < 5 dip, held until QQQ closes above its SMA5; or one day after QLD IBS < 0.15 |
| **B** · IBD or SMA200, vol 60% (type *IBD trend + calm*) | **IBD uptrend** or QQQ above its **SMA200** | 80th percentile | 60% ÷ QLD's 20-day volatility, at most 99% | one day after QQQ RSI(2) < 5 |
| **C** · IBD, vol 40% (type *IBD trend + calm*) | **IBD uptrend** only | 80th percentile | 40% ÷ QLD's 20-day volatility, at most 99% | one day after QQQ RSI(2) < 5, only while QQQ's volatility is under 40% a year |

- **Calm**: the standard deviation of QQQ's last 20 daily changes is below its 80th percentile over the last 252 trading days, today included. A leg whose trend is up but QQQ is jumpy is *held back* and parks.
- **IBD market direction** (William O'Neil's rule, on QQQ and its volume):
  - **Distribution day**: QQQ closes down 0.2% or more on higher volume than the day before.
  - A distribution day stops counting after 25 sessions, or once QQQ closes 5% above it.
  - **Correction**: 6 distribution days counting since the last follow-through day end the uptrend.
  - **Rally attempt**: day 1 is the first higher close after the low. The attempt restarts if QQQ closes below its low.
  - **Follow-through day**: on day 4 or later of the attempt, QQQ closes up 1.25% or more on higher volume. This starts a new uptrend.
- **Size (legs B and C)** is set when the leg goes in and changes only when the volatility rule moves it more than 20 points, so the leg doesn't trade every day.
- Each leg's own settings are in *Parameters → Legs (JSON)*. Health checks each IBD leg against a separate step-by-step recompute.

## How the legs are added up

- Each leg is a sub-account. **The legs are set back to a third each on the first trading day of each year.** In between, a leg that holds QLD grows or shrinks with it, as separate sub-accounts would. *Rebalance the legs: daily* keeps them equal every day instead.
- The target is each leg's target weighted by its sub-account's value. QLD, then 50% GLD and 50% cash for the rest, with a 1% cash buffer.
  - All in, at full size: QLD 99%.
  - All out: 49.5% GLD, the rest cash.
- The target changes only when a leg's own target changes (in, out, a dip day, a resize) or a new year starts. Orders start at the next open, 10 lots 5 minutes apart. Between changes it trades only when a holding drifts more than 20 points from its target (the rebalance band).

## When it trades

About **36 trades a year** over 10 years: three legs going in and out separately, the one-day dips, the resizes, and GLD moving opposite to QLD. It held QLD on about 79% of days (counting a part-held day by its share).

Several legs buy for **one day** after a dip, so the orders need the **next open**, as with the other dip strategies. Keep *Entries start* on "as soon as the market is open" (the default for this type).

## Backtest results

The bot's own code for this strategy (type `split_mix`, legs `trend_gate` and `ibd_gate`) on Yahoo daily prices to 13 Nov 2026. It decides at the close, trades at the next open and pays Webull's real fee (0.11% per buy and per sell); cash earns nothing. QLD before Jun 2006 is built from QQQ × 2. The bot reproduces the research within half a point a year (50.5% / −21.1% against 50.1% / −21.0% over 10 years) and within 1 point in 15 of 20 calendar years (at most 2.4 points, in 2020). Each leg alone reproduces its round-1 research figure within half a point. The **Backtest** tab shows the same on the server.

| Period | **This strategy** | QLD Trend + bear-dip + Vol | QLD Trend + bear-dip | QLD Trend + IBS-dip | QLD regime | QLD held |
|---|---|---|---|---|---|---|
| 1 year | +2.8% / **−18.0%** | −0.5% / −28.1% | +7.7% / −28.1% | **+50.0% / −13.7%** | +11.9% / −28.4% | +14.1% / −28.3% |
| 3 years | +40.6% / **−19.2%** | +35.1% / −28.1% | +38.8% / −28.1% | **+49.9%** / −21.8% | +31.2% / −28.4% | +35.0% / −42.3% |
| 5 years | +40.5% / **−20.9%** | +34.8% / −28.1% | +27.4% / −29.5% | **+41.7%** / −21.8% | +21.7% / −36.3% | +12.8% / −63.7% |
| 10 years | **+50.5% / −21.1%** | +44.9% / −28.1% | +36.0% / −42.4% | +35.9% / −27.2% | +35.4% / −36.3% | +32.0% / −63.7% |
| Since 2006 | **+39.3% / −21.6%** | +34.8% / −29.2% | +29.6% / −42.4% | +28.7% / −30.6% | +22.4% / −39.4% | +22.5% / −83.1% |

Each cell is the return a year / worst fall. 10-year Sharpe: 1.47 for this strategy, 1.28 for QLD Trend + bear-dip + Vol (the best QLD strategy before this one).

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** | QLD Trend + bear-dip + Vol | QLD Trend + bear-dip | QLD Trend + IBS-dip | QLD regime |
|---|---|---|---|---|---|
| Normal | **50.5% / −21.1%** | 44.9% / −28.1% | 36.0% / −42.4% | 35.9% / −27.2% | 35.4% / −36.3% |
| Fee 0.25% a side | **45.6% / −21.4%** | 42.5% / −28.1% | 35.0% / −42.7% | 29.7% / −30.7% | 34.1% / −37.7% |
| Fee 0.50% a side | 37.3% / **−24.1%** | **38.4%** / −28.2% | 33.1% / −43.4% | 19.3% / −36.4% | 31.6% / −39.9% |
| Every order a day late (bot test) | 38.1% / **−24.9%** | **40.2%** / −28.1% | 33.8% / −45.8% | 30.4% / −26.7% | 35.0% / −36.0% |
| Every order a day late (research test) | 34.0% | **38.8%** | 33.1% | 25.3% | 34.0% |

It has the smallest worst fall in every test. It makes the most at Webull's real fee and at 0.25%. At 0.50% a side, or with every order a day late, QLD Trend + bear-dip + Vol makes a little more: it trades about 8 times a year against 36. The research also ran 11 tests in all, including shuffled histories, midday fills and the years before 2016; this split did at least as well as QLD Trend + bear-dip + Vol in 9 of them. In a typical shuffled decade it made 40.3% / −30.7% against 36.3% / −34.9%.

### Year by year

| Year | **This strategy** | QLD Trend + bear-dip + Vol | QLD held |
|---|---|---|---|
| 2026 (to 13 Nov) | +2.4% | −1.6% | **+12.8%** |
| 2025 | **+58.9%** | +56.8% | +30.4% |
| 2024 | **+46.0%** | +36.6% | +42.8% |
| 2023 | +80.8% | +72.4% | **+117.7%** |
| 2022 | **+24.1%** | +19.3% | −60.5% |
| 2021 | +54.0% | **+56.3%** | +54.7% |
| 2020 | **+122.0%** | +117.4% | +88.9% |
| 2019 | +60.4% | +49.7% | **+81.7%** |
| 2018 | **+35.1%** | +12.8% | −8.3% |
| 2017 | +46.4% | +52.6% | **+70.3%** |
| 2016 | **+22.9%** | +16.9% | +10.0% |
| 2015 | **+18.9%** | +6.2% | +14.7% |
| 2014 | +15.8% | +11.3% | **+37.6%** |
| 2013 | +51.3% | +77.7% | **+82.1%** |
| 2012 | +20.3% | +12.3% | **+34.8%** |
| 2011 | +1.8% | **+19.5%** | 0.0% |
| 2010 | +25.8% | +36.4% | **+36.9%** |
| 2009 | +116.5% | +83.8% | **+121.2%** |
| 2008 | +35.5% | **+44.0%** | −72.9% |
| 2007 | **+34.7%** | +23.6% | +29.0% |

Ahead of QLD Trend + bear-dip + Vol in 15 of 21 calendar years (2006 to 2026), and in 9 of the last 11. It has not lost money in a calendar year since 2006; the weakest was +1.8% (2011).

## What to expect

- **Plan with less than the backtest.** The research's walk-forward check picked rules using only the past and held them for the next year. On QLD that kept about three-quarters of the hindsight return: **about 33% to 36% a year** with a −37% worst fall over 10 years. What held up best out of sample was the smaller fall, not the extra return. The Dashboard's expected return uses 50.6% a year (Oct 2016 – Oct 2026) minus the planning haircut.
- **The last year was flat**: +2.8%, about the same as QLD Trend + bear-dip + Vol (−0.5%), while QLD Trend + IBS-dip made +50.0% with its many dip trades. In 2026 it held 51% of the money in QLD on average (68% in 2025): on 66 days a leg's trend was up but QQQ was too jumpy, and on 65 of them every leg was out.
- **It needs the orders on time.** With every order a day late it keeps 38% a year, less than QLD Trend + bear-dip + Vol (40%).
- **Now (after the 13 Nov 2026 close) it is out.** QQQ is jumpy: 2.23% daily volatility against a 1.50% gate. Leg A is below its EMA100. Legs B and C are in an IBD uptrend but held back by the calm gate. It would hold 49.5% GLD and the rest in cash.

## Expected return

<!--expected:qld_split_2c-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

It trades the same ETF as the four other QLD strategies. Money in more than one of them counts in each in *What your money is in*, and the Dashboard's Nasdaq line adds them up. A common way to use it is to move part of the QLD money, not all of it. One option is a third of the QLD Trend + bear-dip + Vol money into this strategy, then comparing the two for a few months on the strategy pages.

*A backtest is a history, not a promise. This is not financial advice.*
