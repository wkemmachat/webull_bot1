<!--{"title": "QLD + Trend + bear-dip", "group": "The strategies"}-->
# QLD + Trend + bear-dip

Holds **QLD (2x Nasdaq-100)** while QQQ is above its 200-day average; below it, only short, sharp RSI(2) dips are bought and sold on the first bounce. Cash the rest of the time. Simple, and the best-checked strategy: the bot's backtest matches the research almost exactly.

## How it decides

After each US close, from QQQ's daily closes:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | QQQ closes above its SMA200 | 99% QLD |
| **In · dip trade** | below SMA200, a dip trade opens when RSI(2) < 5 and closes on the first close above SMA5 | 99% QLD |
| **Out** | below SMA200 and no dip trade | cash |

## What it holds

QLD (2x Nasdaq-100) or cash. Nothing else. Until 31 Oct 2026 the cash waited in BIL (T-bills); plain cash saves 0.22% in fees on every round trip and did slightly better in every period of the bot's backtest (10 years +37.3% / −42.4% against +36.5% / −42.7%; since 2007 +31.7% against +30.5%). The tables below are from the BIL version. To go back, set *When out, hold* to BIL.

Option: *Gold share when out (%)* in Parameters holds part of the parked money in GLD (0 = all cash, the default). On this strategy it adds a little return but deepens the worst fall: 10 years +37.3% / −42.4% with 0%, +39.2% / −44.2% with 50% (bot backtest, 26 Oct 2026). It helps more on [QLD Trend + bear-dip + Vol](#/docs/strategy-qld-tbdv), which is out more often.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+22.7%** | −22.7% | 0.63 | +22.3% / −25.1% | +15.9% / −12.0% |
| 3 years | **+51.2%** | −26.1% | 1.18 | +44.0% / −42.3% | +26.3% / −22.8% |
| 5 years | **+32.9%** | −30.1% | 0.88 | +16.6% / −63.7% | +14.0% / −35.1% |
| 10 years | **+36.4%** | −42.6% | 0.98 | +31.9% / −63.7% | +20.2% / −35.1% |
| All (from 30 May 2007) | **+31.7%** | −42.6% | 0.93 | +23.9% / −83.1% | +15.9% / −53.4% |

- **Worst fall:** −42.6%, from 19 Feb 2020 to 9 Apr 2020; back at the old high on 3 Aug 2020.
- **$10,000 became** $2,081,855 (+20,719%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 83% of the days · **8.7 trades a year** · 48% of round trips made money (average +9.3%).
- Volatility 34% a year.

### Year by year

| Year | Strategy | QLD held | QQQ held |
|---|---|---|---|
| 2026 (part) | **+22.9%** | +22.5% | +15.1% |
| 2025 | **+50.9%** | +30.4% | +20.8% |
| 2024 | **+42.6%** | +42.8% | +25.6% |
| 2023 | **+67.0%** | +117.7% | +54.9% |
| 2022 | **−14.8%** | −60.5% | −32.6% |
| 2021 | **+54.5%** | +54.7% | +27.4% |
| 2020 | **+63.9%** | +88.9% | +48.4% |
| 2019 | **+46.3%** | +81.7% | +39.0% |
| 2018 | **−4.1%** | −8.3% | −0.1% |
| 2017 | **+69.9%** | +70.3% | +32.7% |
| 2016 | **−3.9%** | +10.0% | +7.1% |
| 2015 | **+3.6%** | +14.7% | +9.4% |
| 2014 | **+37.4%** | +37.6% | +19.2% |
| 2013 | **+78.2%** | +82.1% | +36.6% |
| 2012 | **+10.9%** | +34.8% | +18.1% |
| 2011 | **+3.3%** | +0.0% | +3.5% |
| 2010 | **+14.2%** | +36.9% | +20.1% |
| 2009 | **+83.4%** | +121.2% | +54.7% |
| 2008 | **+41.2%** | −72.9% | −41.7% |
| 2007 (part) | **+11.0%** | +11.8% | +8.8% |

## The research

**ETF Strategy Lab (23 Oct 2026)**, Oct 2007 – Oct 2026: **32.9% a year, worst fall −42.5%, Sharpe 0.95** (QQQ held: 15.1%, −53.3%). 60 neighbouring settings gave 22–33% a year (median 27.6%), so expect less than the best case. The bot's backtest over the same years at Webull's real fee: 31.7% a year, −42.6%, Sharpe 0.93 (33.0% at a 0.05% cost).

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:qld_tbd-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **2x Nasdaq:** a fast crash before QQQ crosses its SMA200 costs about twice the drop (worst fall −42%, February–April 2020).
- **Choppy years** around the SMA200 cost money: 2016 −4%, 2018 −4%, 2022 −15%.
- Overlaps with QLD regime and C2-7 Momentum (same index, similar timing).
- Webull: QLD needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

QQQ daily: **Moving Average** 200 and 5, **Relative Strength Index** length 2.
