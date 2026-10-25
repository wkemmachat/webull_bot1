<!--{"title": "2x Semis regime", "group": "The strategies"}-->
# 2x Semis regime

The same four-state regime as QLD regime, read from **SMH** (semiconductors) and traded with **USD** (2x semiconductors). The highest-return daily strategy, and the deepest falls.

## How it decides

After each US close, from SMH's daily closes:

| State | When | Holds |
|---|---|---|
| **2x** | SMH > SMA200, SMA50 > SMA200, 20-day volatility < **40%** | 99% USD |
| **0.5x** | as 2x but volatility ≥ 40% | 25% USD, 74% BIL |
| **1x** | SMH > SMA200 but SMA50 ≤ SMA200 | 50% USD, 49% BIL |
| **Off** | SMH ≤ SMA200 | 99% GLD |

The gate is 40% because semiconductors normally move about 10 points more than the Nasdaq-100.

## What it holds

USD (ProShares Ultra Semiconductors, 2x), BIL and GLD.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | USD held a year / worst fall | SMH held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+62.8%** | −31.6% | 1.05 | +43.4% / −39.3% | +53.4% / −24.6% |
| 3 years | **+110.7%** | −36.5% | 1.50 | +101.5% / −64.5% | +55.3% / −35.7% |
| 5 years | **+69.4%** | −45.9% | 1.18 | +50.7% / −77.8% | +32.3% / −45.3% |
| 10 years | **+57.3%** | −45.9% | 1.12 | +51.0% / −77.8% | +32.6% / −45.3% |
| All (from 30 May 2007) | **+36.7%** | −46.7% | 0.91 | +27.2% / −88.6% | +20.0% / −64.2% |

- **Worst fall:** −46.7%, from 15 Apr 2010 to 2 Nov 2012; back at the old high on 20 Mar 2014.
- **$10,000 became** $4,295,509 (+42,855%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 74% of the days · **9 trades a year** · 26% of round trips made money (average +11.7%).
- Volatility 43% a year.

### Year by year

| Year | Strategy | USD held | SMH held |
|---|---|---|---|
| 2026 (part) | **+58.9%** | +40.0% | +46.4% |
| 2025 | **+63.7%** | +62.1% | +49.2% |
| 2024 | **+136.4%** | +139.6% | +39.1% |
| 2023 | **+177.7%** | +228.8% | +73.4% |
| 2022 | **−40.9%** | −68.6% | −33.5% |
| 2021 | **+84.4%** | +104.3% | +42.1% |
| 2020 | **+61.8%** | +68.2% | +55.5% |
| 2019 | **+61.7%** | +110.4% | +64.5% |
| 2018 | **−7.7%** | −26.9% | −9.0% |
| 2017 | **+81.3%** | +81.7% | +38.5% |
| 2016 | **+83.1%** | +56.8% | +35.5% |
| 2015 | **−20.8%** | −7.5% | −0.3% |
| 2014 | **+75.3%** | +78.1% | +30.2% |
| 2013 | **+62.8%** | +77.7% | +33.3% |
| 2012 | **−20.0%** | −10.2% | +8.6% |
| 2011 | **−12.2%** | −14.9% | −6.5% |
| 2010 | **−5.3%** | +19.4% | +16.5% |
| 2009 | **+78.1%** | +137.5% | +58.6% |
| 2008 | **−8.1%** | −79.8% | −45.7% |
| 2007 (part) | **+17.1%** | −1.8% | −10.3% |

## The research

Strategy **U** of the *Strategy to beat QQQ* research: the semiconductor sleeve on its own. Worst fall in the research about −46%.

## An alternative on the same ETF

**USD Trend + IBS-dip** also holds USD, but reads USD's own chart instead of SMH: a Supertrend + SMA200 trend leg sized by USD's
volatility, plus one-day full-size trades after weak closes. Over 10 years it earned more (+62.5% a year vs +57.3%) with a smaller
worst fall (−37.0% vs −45.9%), and it made money in 2018 (+34% vs −8%) and 2022 (+32% vs −41%). 2x Semis regime earned more over the
last 2–3 years of the chip rally (+111% a year vs +74% over 3 years) and trades far less (about 9 times a year vs 62). The two move
together (monthly correlation about 0.6), so running both is mostly the same bet: choose one, or split the money between them.
See **USD Trend + IBS-dip**.

## Risks and what to expect

- **Concentrated:** one sector, 2x. Falls of −40% to −47% happened (2022: about −41%).
- **Webull:** USD was refused on the Webull test account ("not available"); check it with Test trade on your Live account before giving it money. If Webull TH does not offer USD, choose another 2x semiconductor ETF in Parameters.
- Moves with the Nasdaq strategies (semiconductors are a large part of the Nasdaq-100).

## Check it on TradingView

SMH daily: **Moving Average** 200 and 50, **Historical Volatility** length 20.
