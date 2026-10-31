<!--{"title": "2x Semis regime", "group": "The strategies"}-->
# 2x Semis regime

The same four-state regime as QLD regime, read from **SMH** (semiconductors) and traded with **USD** (2x semiconductors). The highest-return daily strategy, and the deepest falls.

## How it decides

After each US close, from SMH's daily closes:

| State | When | Holds |
|---|---|---|
| **2x** | SMH > SMA200, SMA50 > SMA200, 20-day volatility < **40%** | 99% USD |
| **0.5x** | as 2x but volatility ≥ 40% | 25% USD, rest cash |
| **1x** | SMH > SMA200 but SMA50 ≤ SMA200 | 50% USD, rest cash |
| **Off** | SMH ≤ SMA200 | 99% GLD |

The gate is 40% because semiconductors normally move about 10 points more than the Nasdaq-100.

## What it holds

USD (ProShares Ultra Semiconductors, 2x), GLD and cash. Until 31 Oct 2026 the cash part was held in BIL (T-bills); plain cash did slightly better in every period of the bot's backtest (10 years +56.8% against +56.2%). To go back, set *Cash part goes to* to BIL.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | USD held a year / worst fall | SMH held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+61.1%** | −31.6% | 1.03 | +43.4% / −39.3% | +53.4% / −24.6% |
| 3 years | **+108.7%** | −37.2% | 1.48 | +101.5% / −64.5% | +55.3% / −35.7% |
| 5 years | **+67.7%** | −46.4% | 1.16 | +50.7% / −77.8% | +32.3% / −45.3% |
| 10 years | **+55.9%** | −46.4% | 1.10 | +51.0% / −77.8% | +32.6% / −45.3% |
| All (from 30 May 2007) | **+35.4%** | −49.1% | 0.88 | +27.2% / −88.6% | +20.0% / −64.2% |

- **Worst fall:** −49.1%, from 15 Apr 2010 to 14 Dec 2012; back at the old high on 28 May 2014.
- **$10,000 became** $3,554,721 (+35,447%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 74% of the days · **9 trades a year** · 25% of round trips made money (average +11.5%).
- Volatility 43% a year.

### Year by year

| Year | Strategy | USD held | SMH held |
|---|---|---|---|
| 2026 (part) | **+57.3%** | +40.0% | +46.4% |
| 2025 | **+62.5%** | +62.1% | +49.2% |
| 2024 | **+134.1%** | +139.6% | +39.1% |
| 2023 | **+175.2%** | +228.8% | +73.4% |
| 2022 | **−41.7%** | −68.6% | −33.5% |
| 2021 | **+84.1%** | +104.3% | +42.1% |
| 2020 | **+59.7%** | +68.2% | +55.5% |
| 2019 | **+60.4%** | +110.4% | +64.5% |
| 2018 | **−9.3%** | −26.9% | −9.1% |
| 2017 | **+81.4%** | +81.7% | +38.5% |
| 2016 | **+81.0%** | +56.8% | +35.5% |
| 2015 | **−22.3%** | −7.5% | −0.3% |
| 2014 | **+74.9%** | +78.1% | +30.2% |
| 2013 | **+62.5%** | +77.7% | +33.3% |
| 2012 | **−22.1%** | −10.2% | +8.6% |
| 2011 | **−13.0%** | −14.9% | −6.5% |
| 2010 | **−6.3%** | +19.4% | +16.5% |
| 2009 | **+77.0%** | +137.5% | +58.5% |
| 2008 | **−8.8%** | −79.8% | −45.8% |
| 2007 (part) | **+16.7%** | −1.8% | −10.3% |

## The research

Strategy **U** of the *Strategy to beat QQQ* research: the semiconductor sleeve on its own. Worst fall in the research about −46%.

## An alternative on the same ETF

**USD Trend + IBS-dip** also holds USD, but reads USD's own chart instead of SMH: a Supertrend + SMA200 trend leg sized by USD's
volatility, plus one-day full-size trades after weak closes. Over 10 years at Webull's real fee it earned more (+58.7% a year vs
+55.9%) with a smaller worst fall (−38.1% vs −46.4%), and it made money in 2018 (+33% vs −9%) and 2022 (+24% vs −42%). 2x Semis
regime earned more over the last 2–3 years of the chip rally (+109% a year vs +72% over 3 years) and trades far less (about 9 times
a year vs 62), so it pays much less in fees. The two move
together (monthly correlation about 0.6), so running both is mostly the same bet: choose one, or split the money between them.
See **USD Trend + IBS-dip**.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:semis_regime-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Concentrated:** one sector, 2x. Falls of −40% to −47% happened (2022: about −42%).
- **Webull:** USD was refused on the Webull test account ("not available"); check it with Test trade on your Live account before giving it money. If Webull TH does not offer USD, choose another 2x semiconductor ETF in Parameters.
- Moves with the Nasdaq strategies (semiconductors are a large part of the Nasdaq-100).

## Check it on TradingView

SMH daily: **Moving Average** 200 and 50, **Historical Volatility** length 20.
