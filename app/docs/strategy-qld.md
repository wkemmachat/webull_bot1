<!--{"title": "QLD regime", "group": "The strategies"}-->
# QLD regime

Holds **QLD (2x Nasdaq-100)** in four steps depending on the state of QQQ: full when the trend is up, confirmed and calm; less when it is jumpy or not yet confirmed; **gold (GLD)** when the trend is off.

## How it decides

After each US close, from QQQ's daily closes:

| State | When | Holds |
|---|---|---|
| **2x** | QQQ > SMA200, SMA50 > SMA200, 20-day volatility < 30% | 99% QLD |
| **0.5x** | as 2x but volatility ≥ 30% | 25% QLD, 74% BIL |
| **1x** | QQQ > SMA200 but SMA50 ≤ SMA200 (not confirmed) | 50% QLD, 49% BIL |
| **Off** | QQQ ≤ SMA200 | 99% GLD |

Volatility = standard deviation of the last 20 daily log returns × √252. The bot trades on a state change (about 6–8 a year) or when
a holding drifts more than 10% from its target.

## What it holds

QLD (ProShares Ultra QQQ, 2x), BIL (T-bills) and GLD (gold).

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+32.5%** | −18.5% | 0.85 | +22.3% / −25.1% | +15.9% / −12.0% |
| 3 years | **+44.9%** | −26.3% | 1.14 | +44.0% / −42.3% | +26.3% / −22.8% |
| 5 years | **+28.8%** | −35.9% | 0.86 | +16.6% / −63.7% | +14.0% / −35.1% |
| 10 years | **+37.2%** | −35.9% | 1.09 | +31.9% / −63.7% | +20.2% / −35.1% |
| All (from 30 May 2007) | **+26.6%** | −39.1% | 0.88 | +23.9% / −83.1% | +15.9% / −53.4% |

- **Worst fall:** −39.1%, from 20 Jul 2015 to 14 Jan 2016; back at the old high on 1 May 2017.
- **$10,000 became** $963,830 (+9,538%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 80% of the days · **7.8 trades a year** · 25% of round trips made money (average +9.7%).
- Volatility 31% a year.

### Year by year

| Year | Strategy | QLD held | QQQ held |
|---|---|---|---|
| 2026 (part) | **+32.7%** | +22.5% | +15.1% |
| 2025 | **+30.2%** | +30.4% | +20.8% |
| 2024 | **+34.8%** | +42.8% | +25.6% |
| 2023 | **+86.0%** | +117.7% | +54.9% |
| 2022 | **−25.4%** | −60.5% | −32.6% |
| 2021 | **+53.9%** | +54.7% | +27.4% |
| 2020 | **+86.4%** | +88.9% | +48.4% |
| 2019 | **+35.0%** | +81.7% | +39.0% |
| 2018 | **+12.9%** | −8.3% | −0.1% |
| 2017 | **+69.7%** | +70.3% | +32.7% |
| 2016 | **+7.8%** | +10.0% | +7.1% |
| 2015 | **−15.7%** | +14.7% | +9.4% |
| 2014 | **+37.8%** | +37.6% | +19.2% |
| 2013 | **+71.0%** | +82.1% | +36.6% |
| 2012 | **+11.2%** | +34.8% | +18.1% |
| 2011 | **−11.8%** | 0.0% | +3.5% |
| 2010 | **+12.2%** | +36.9% | +20.1% |
| 2009 | **+59.9%** | +121.2% | +54.7% |
| 2008 | **−4.8%** | −72.9% | −41.7% |
| 2007 (part) | **+12.1%** | +11.8% | +8.8% |

## The research

Strategy **F** of the *Strategy to beat QQQ* research (AI x Alpaca): **39.7% a year in 2016–2026** with fills at the next open (37.4% at the same close).

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:qld_regime-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **2022-type years:** a slow bear market with sharp rallies flips the state often; 2022 was about −25%.
- **Gold when off** helps when gold rises in bad stock years, but gold can also fall then.
- Together with QLD + Trend + bear-dip and C2-7 Momentum it is one big Nasdaq bet: they are in and out at similar times.
- Webull: QLD needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

QQQ daily: **Moving Average** 200 and 50, **Historical Volatility** length 20 (annualised).
