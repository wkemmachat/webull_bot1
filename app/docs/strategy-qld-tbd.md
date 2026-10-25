<!--{"title": "QLD + Trend + bear-dip", "group": "The strategies"}-->
# QLD + Trend + bear-dip

Holds **QLD (2x Nasdaq-100)** while QQQ is above its 200-day average; below it, only short, sharp RSI(2) dips are bought and sold on the first bounce. T-bills (BIL) the rest of the time. Simple, and the best-checked strategy: the bot's backtest matches the research almost exactly.

## How it decides

After each US close, from QQQ's daily closes:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | QQQ closes above its SMA200 | 99% QLD |
| **In · dip trade** | below SMA200, a dip trade opens when RSI(2) < 5 and closes on the first close above SMA5 | 99% QLD |
| **Out** | below SMA200 and no dip trade | 99% BIL |

## What it holds

QLD (2x Nasdaq-100) or BIL (T-bills). Nothing else.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+23.3%** | −22.6% | 0.65 | +22.3% / −25.1% | +15.9% / −12.0% |
| 3 years | **+51.6%** | −26.1% | 1.19 | +44.0% / −42.3% | +26.3% / −22.8% |
| 5 years | **+34.2%** | −29.5% | 0.91 | +16.6% / −63.7% | +14.0% / −35.1% |
| 10 years | **+37.3%** | −42.3% | 1.00 | +31.9% / −63.7% | +20.2% / −35.1% |
| All (from 30 May 2007) | **+33.0%** | −42.3% | 0.96 | +23.9% / −83.1% | +15.9% / −53.4% |

- **Worst fall:** −42.3%, from 19 Feb 2020 to 9 Apr 2020; back at the old high on 3 Aug 2020.
- **$10,000 became** $2,532,380 (+25,224%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 83% of the days · **8.7 trades a year** · 48% of round trips made money (average +9.4%).
- Volatility 34% a year.

### Year by year

| Year | Strategy | QLD held | QQQ held |
|---|---|---|---|
| 2026 (part) | **+23.5%** | +22.5% | +15.1% |
| 2025 | **+51.5%** | +30.4% | +20.8% |
| 2024 | **+42.6%** | +42.8% | +25.6% |
| 2023 | **+67.9%** | +117.7% | +54.9% |
| 2022 | **−11.9%** | −60.5% | −32.6% |
| 2021 | **+54.5%** | +54.7% | +27.4% |
| 2020 | **+64.7%** | +88.9% | +48.4% |
| 2019 | **+47.2%** | +81.7% | +39.0% |
| 2018 | **−3.5%** | −8.3% | −0.1% |
| 2017 | **+69.8%** | +70.3% | +32.7% |
| 2016 | **−2.3%** | +10.0% | +7.1% |
| 2015 | **+4.4%** | +14.7% | +9.4% |
| 2014 | **+37.4%** | +37.6% | +19.2% |
| 2013 | **+78.5%** | +82.1% | +36.6% |
| 2012 | **+12.9%** | +34.8% | +18.1% |
| 2011 | **+6.4%** | 0.0% | +3.5% |
| 2010 | **+16.1%** | +36.9% | +20.1% |
| 2009 | **+84.8%** | +121.2% | +54.7% |
| 2008 | **+46.1%** | −72.9% | −41.7% |
| 2007 (part) | **+11.1%** | +11.8% | +8.8% |

## The research

**ETF Strategy Lab (23 Oct 2026)**, Oct 2007 – Oct 2026: **32.9% a year, worst fall −42.5%, Sharpe 0.95** (QQQ held: 15.1%, −53.3%). 60 neighbouring settings gave 22–33% a year (median 27.6%), so expect less than the best case. The bot's backtest over the same years: 33.0% a year, −42.3%, Sharpe 0.96.

## Risks and what to expect

- **2x Nasdaq:** a fast crash before QQQ crosses its SMA200 costs about twice the drop (worst fall −42%, February–April 2020).
- **Choppy years** around the SMA200 cost money: 2016 −2%, 2018 −4%, 2022 −12%.
- Overlaps with QLD regime and C2-7 Momentum (same index, similar timing).
- Webull: QLD needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

QQQ daily: **Moving Average** 200 and 5, **Relative Strength Index** length 2.
