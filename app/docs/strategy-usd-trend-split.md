<!--{"title": "USD · Trend split (3 rules + credit check)", "group": "The strategies"}-->
# USD · Trend split (3 rules + credit check)

Trades **USD (ProShares Ultra Semiconductors, 2x chips)** from the 1x chip ETF **SMH**, like [USD · SMH trend + SMH IBS-dip](#/docs/strategy-usd-smh-ibs), but the money is **split into three legs, a third each**. Each leg follows its own trend rule on SMH. A leg holds USD only while SMH is **calm** and **credit is OK**, meaning corporate bonds (LQD) are holding up against Treasuries (IEF). When a leg's trend is off, it buys USD for **one day** after SMH closes near the bottom of its day. The share in USD is the part of the money whose legs are in: 0, about ⅓, ⅔ or all.

This is **split C of round 3** of the research *Strategy research and stress tests* (15 Nov 2026). It was the USD pick that passed all 11 stress tests. It made more than all three USD strategies already in the bot over 3, 5 and 10 years and since 2006, with a smaller worst fall since 2006.

Added on 15 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from the daily bars of SMH, USD, LQD and IEF. The bot only decides on days where all four have a closed bar.

| Leg (⅓ of the money) | Trend rule on SMH | Calm gate | Credit check | Below its trend |
|---|---|---|---|---|
| **1** | close above its **SMA150** | 90th percentile | LQD ÷ IEF above SMA100 | one-day dip after SMH IBS < 0.30 |
| **2** | **ROC126 > 0**: higher than 126 trading days ago | 90th percentile | LQD ÷ IEF above SMA100 | one-day dip after SMH IBS < 0.30 |
| **3** | close above its **EMA150** | 80th percentile | LQD ÷ IEF above SMA100 | one-day dip after SMH IBS < 0.30 |

- A leg is **in** when its trend is up, SMH is calm and credit is OK. It is also in for a **dip day**: its trend is off and SMH's IBS < 0.30.
  - IBS = (close − low) ÷ (high − low). A dip day is held from the next open to the following open.
- **Calm**: the standard deviation of SMH's last 20 daily changes is below the leg's percentile of the same number over the last 252 trading days, today included.
- **Credit check**: LQD ÷ IEF, on **dividend-adjusted** closes, above its 100-day average.
  - The adjusted prices matter. LQD pays more interest than IEF, so with plain prices the ratio slides down every month and the check is off far more often.
  - With plain prices the backtest falls from 93% to 80% a year. The research used adjusted prices.
  - The bot takes Yahoo's adjusted history once a day and carries its last adjustment forward to today's close.
- **The legs are set back to a third each on the first trading day of each year.** In between, a leg that holds USD grows or shrinks with it, as separate sub-accounts would. *Rebalance the legs: daily* keeps exactly ⅓ per leg in, and gives almost the same backtest (about 93% a year either way).
- When one or more legs change, the target moves to the new share in USD. Orders start at the next open, 10 lots 5 minutes apart. Between changes it trades only when USD drifts more than 20 points from its target (the rebalance band).

## What it holds

USD or cash. No GLD and no T-bill ETF. Whatever the legs that are out don't use stays as cash in the strategy. *When out, hold* in Parameters can park it in a T-bill ETF, but every switch then pays the fee.

## When it trades

About **49 trades a year**: the legs turn on and off separately, plus the one-day dips. Over 10 years it held USD on about 68% of days (counting a part-held day by its share).

The one-day dips need the orders at the **next open**, as with the other IBS strategies. Keep *Entries start* on "as soon as the market is open" (the default for this type).

## Backtest results

The bot's own code for this strategy (type `trend_split`) on Yahoo daily prices to 13 Nov 2026. It decides at the close, trades at the next open and pays Webull's real fee (0.11% per buy and per sell); cash earns nothing. USD before Feb 2007 is built from SMH × 2. The bot reproduces the research's numbers within 0.1 point a year (93.0% / −36.6% over 10 years) and within half a point in every calendar year. The **Backtest** tab shows the same on the server.

| Period | **This strategy** | USD · SMH trend + SMH IBS-dip | USD Trend + IBS-dip | 2x Semis regime | USD held |
|---|---|---|---|---|---|
| 1 year | +22.9% / −28.9% | **+95.8% / −21.8%** | +55.0% / −36.3% | +51.2% / −32.9% | +5.9% / −55.6% |
| 3 years | **+128.2% / −30.5%** | +115.7% / −30.2% | +62.0% / −36.3% | +92.0% / −37.3% | |
| 5 years | **+84.5% / −36.4%** | +76.2% / −37.5% | +62.3% / −36.3% | +57.1% / −46.1% | |
| 10 years | **+92.9% / −36.6%** | +73.1% / −37.5% | +56.5% / −38.1% | +55.5% / −46.1% | +46.8% / −77.9% |
| Since 2006 | **+51.8% / −37.1%** | +42.3% / −50.8% | +34.6% / −51.5% | +29.4% / −53.3% | +21.9% / −89.9% |

Each cell is the return a year / worst fall. 10-year Sharpe: 1.53 for this strategy, 1.35 for USD · SMH trend + SMH IBS-dip.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** | USD · SMH trend + SMH IBS-dip | USD Trend + IBS-dip | 2x Semis regime |
|---|---|---|---|---|
| Normal | **92.9% / −36.6%** | 73.1% / −37.5% | 56.5% / −38.1% | 55.5% / −46.1% |
| Fee 0.25% a side | **83.6% / −40.0%** | 63.9% / −40.3% | 41.0% / −42.2% | 53.1% / −47.2% |
| Fee 0.50% a side | **68.1% / −47.4%** | 48.6% / −46.0% | 16.9% / −50.7% | 48.8% / −49.3% |
| Every order a day late (bot test) | 53.2% / −51.4% | 37.5% / −45.2% | 38.1% / −35.5% | **51.3% / −46.2%** |
| Every order a day late (research test) | **28.1%** | 8.8% | 18.9% | 51.4% |

It keeps the most when fees are higher. It also keeps more than USD · SMH when every order is a day late, but its fall then deepens to −51%. Only the 2x Semis regime, which trades about 9 times a year, is sturdier when orders are late.

### Year by year

| Year | **This strategy** | USD · SMH trend + SMH IBS-dip | USD held |
|---|---|---|---|
| 2026 (to 13 Nov) | +38.0% | **+97.7%** | +5.0% |
| 2025 | **+181.6%** | +127.6% | +62.1% |
| 2024 | **+145.3%** | +85.0% | +139.6% |
| 2023 | +49.9% | **+110.1%** | +228.8% |
| 2022 | **+38.9%** | +2.4% | −68.6% |
| 2021 | **+94.6%** | +51.9% | +104.3% |
| 2020 | **+250.7%** | +151.6% | +68.2% |
| 2019 | **+83.0%** | +61.6% | +110.4% |
| 2018 | **+45.7%** | +22.8% | −26.9% |
| 2017 | **+72.3%** | +67.1% | +81.7% |
| 2016 | **+37.4%** | +19.0% | +56.8% |
| 2015 | **−1.2%** | −15.1% | −7.5% |
| 2014 | +34.3% | **+36.9%** | +78.1% |
| 2013 | +71.5% | **+77.3%** | +77.7% |
| 2012 | **−4.1%** | −15.1% | −10.2% |
| 2011 | **+4.0%** | −17.1% | −14.9% |
| 2010 | +6.5% | **+43.1%** | +19.4% |
| 2009 | +140.4% | **+168.8%** | +137.5% |
| 2008 | **+17.4%** | −15.6% | −79.8% |
| 2007 | −0.1% | **+30.3%** | +8.3% |

Ahead of USD · SMH trend + SMH IBS-dip in 9 of the last 11 calendar years (2016 to 2026); behind in 2023 and in 2026 so far. Since 2007 it lost money in 3 years, at most −4.1% (2012).

## What to expect

- **Plan with less than the backtest.** The research's walk-forward check picked rules using only the past and held them for the next year. On USD that made about **73% a year** over 10 years with a −38.5% worst fall. That is the same as USD · SMH trend + SMH IBS-dip, not 93%. What held up best out of sample was the smaller fall, not the extra return. The Dashboard's expected return uses 95.3% a year (Oct 2016 – Oct 2026) minus the planning haircut.
- **The last year was weak**: +22.9% against +95.8%. In 2026 it held USD only 29% of the time on average (59% in 2025): on 95 days a leg's trend was up and calm but credit was weak, and on 88 days a leg's trend was up but SMH was jumpy.
- **Now (after the 13 Nov 2026 close) it is out.** All three legs are below their trend, SMH is jumpy and credit is weak, so it would hold cash.

## Expected return

<!--expected:usd_trend_split-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

It trades the same ETF as USD · SMH trend + SMH IBS-dip and USD Trend + IBS-dip. Money in both counts twice in *What your money is in*: the Dashboard's US-tech line adds them up. A common way to use it is to move part of the USD money, not all of it. One option is a third into this strategy, keeping the rest where it is, and comparing them for a few months on the strategy pages.

*A backtest is a history, not a promise. This is not financial advice.*
