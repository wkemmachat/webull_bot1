<!--{"title": "QLD Trend + IBS-dip", "group": "The strategies"}-->
# QLD Trend + IBS-dip

Holds **QLD (2x Nasdaq-100)** timed by **QLD's own price**: while its Supertrend is up and it is above its 200-day average, or for **one day after a weak close**. The size is **capped by Nasdaq volatility**, and idle money sits in **gold and T-bills**. From the research's *strategy 2*: the same 10-year return as the other QLD strategies with a much smaller worst fall, and the only one of them that made money in 2022.

## How it decides

After each US close, from **QLD's own daily bar** (and QQQ's closes for the size):

| State | Rule | Holds |
|---|---|---|
| **In · trend** | Supertrend(ATR 14, ×4) on QLD is **up** AND QLD closes **above its SMA200** | QLD at the capped size, rest parked |
| **In · dip day** | **IBS < 0.2** AND **ADX(14) > 20** (QLD closed near the day's low in a strong move) | QLD for the **next day only** |
| **Off** | neither | 50% GLD + 50% BIL |

**IBS** (internal bar strength) = (close − low) ÷ (high − low): 0 means QLD closed on the day's low, 1 on its high. Weak closes
tend to bounce the next day; ADX above 20 keeps it to days with a real move.

**Size when in** = the smaller of 100% and **50% ÷ (2 × QQQ's 60-day volatility)**. With QQQ volatility at 18% a year that is
50 ÷ 36 → 100%; at 35% (a stressed market) it is 50 ÷ 70 → 71%. The size is changed only when the new size differs from the size
held by **more than 20 points**, so small volatility moves do not trade. The part not in QLD is parked like the off state.

## What it holds

QLD (2x Nasdaq-100) at the capped size; the rest, and everything when off, **50% GLD (gold) + 50% BIL (T-bills)**. A dip day is a one-day trade: bought at the open after the weak close, sold at the next open unless the trend or a new dip signal keeps it.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+49.8%** | −12.6% | 1.43 | +22.3% / −25.1% | +15.9% / −12.0% |
| 3 years | **+51.2%** | −29.6% | 1.34 | +44.0% / −42.3% | +26.3% / −22.8% |
| 5 years | **+44.9%** | −29.6% | 1.28 | +16.6% / −63.7% | +14.0% / −35.1% |
| 10 years | **+34.5%** | −29.6% | 1.11 | +31.9% / −63.7% | +20.2% / −35.1% |
| All (from 30 May 2007) | **+30.0%** | −29.6% | 1.05 | +23.9% / −83.1% | +15.9% / −53.4% |

- **Worst fall:** −29.6%, from 10 Jul 2024 to 6 Sep 2024; back at the old high on 9 Apr 2025.
- **$10,000 became** $1,632,629 (+16,226%) from 30 May 2007 to 23 Oct 2026.
- **In the market** 62% of the days · **33.4 trades a year** · 59% of round trips made money (average +1.8%).
- Volatility 27% a year.

### Year by year

| Year | Strategy | QLD held | QQQ held |
|---|---|---|---|
| 2026 (part) | **+50.3%** | +22.5% | +15.1% |
| 2025 | **+71.4%** | +30.4% | +20.8% |
| 2024 | **+14.7%** | +42.8% | +25.6% |
| 2023 | **+66.6%** | +117.7% | +54.9% |
| 2022 | **+23.9%** | −60.5% | −32.6% |
| 2021 | **+10.3%** | +54.7% | +27.4% |
| 2020 | **+68.0%** | +88.9% | +48.4% |
| 2019 | **+23.9%** | +81.7% | +39.0% |
| 2018 | **+4.7%** | −8.3% | −0.1% |
| 2017 | **+50.7%** | +70.3% | +32.7% |
| 2016 | **−12.2%** | +10.0% | +7.1% |
| 2015 | **+0.9%** | +14.7% | +9.4% |
| 2014 | **+8.5%** | +37.6% | +19.2% |
| 2013 | **+50.3%** | +82.1% | +36.6% |
| 2012 | **+19.0%** | +34.8% | +18.1% |
| 2011 | **−13.1%** | +0.0% | +3.5% |
| 2010 | **+40.5%** | +36.9% | +20.1% |
| 2009 | **+80.9%** | +121.2% | +54.7% |
| 2008 | **+70.2%** | −72.9% | −41.7% |
| 2007 (part) | **+14.4%** | +11.8% | +8.8% |

## The research

**Research on single Stock Nasdaq · strategy 2** (QLD own-price + vol cap, 50/50 gold & T-bill parking), Oct 2016 – Oct 2026: **37.7% a year, worst fall −31.6%, Sharpe 1.27**. Over 1999–2026, with QLD rebuilt from the Nasdaq-100 before it existed: **30.1% a year, worst fall −32%** — it held up in the dot-com crash (+19.7% a year in 2000–02) when the bot's other QLD strategies lost money. 624 nearby settings had a median of 25% a year with a −37% worst fall, so plan on less than the best case. The bot's backtest is about 3–5 points a year lower than the research because it charges 0.05% on every dollar traded (about 29 trades a year), and it matches the research's signals day for day.

## Sister strategy

**USD Trend + IBS-dip** uses the same rules on USD (2x semiconductors) with settings the research chose for USD: Supertrend 20 × 4.5,
dip days on IBS < 0.15 held at 100%, size from USD's own 20-day volatility with a 40% cap. It has more return and deeper falls
(10 years: +62.5% a year, worst fall −37.0%). Monthly correlation between the two is about 0.5, so together they spread the risk
better than either QLD strategy next to 2x Semis.

## Risks and what to expect

- **Gives up the big rallies:** the volatility cap and the quick exits leave money on the table in strong years (2021 +10% vs QLD +55%, 2024 +15% vs +43%, 2019 +24% vs +82%).
- **Many small trades:** about 29 a year, many of them one-day dip trades at the open. Each pays the spread on QLD, so fills matter more than for the other QLD strategies.
- **2x Nasdaq:** the worst fall in 10 years was −30% (July – September 2024).
- Partly the same bet as QLD regime, QLD + Trend + bear-dip and C2-7 (monthly correlation about 0.7); it pairs best with 2x Semis (0.53).
- Webull: QLD needs the Leveraged & Inverse ETF permission; GLD and BIL are plain ETFs.

## Check it on TradingView

QLD daily: **Supertrend** (ATR 14, factor 4), **Moving Average** 200, **Average Directional Index** 14. IBS has no built-in indicator: (close − low) ÷ (high − low) of the day. QQQ's 60-day volatility: the standard deviation of its last 60 daily returns × √252.
