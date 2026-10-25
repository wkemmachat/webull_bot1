<!--{"title": "USD Trend + IBS-dip", "group": "The strategies"}-->
# USD Trend + IBS-dip

Holds **USD (ProShares Ultra Semiconductors, 2x chips)** timed by **USD's own price**: while its Supertrend is up and it is above its 200-day average, at a size that shrinks when USD gets jumpy; and for **one day at full size after a weak close**. Idle money sits in **gold and T-bills**. This is the research's *candidate C (aggressive)*, run with a 20-point resize rule so it trades about half as often. Over 10 years it earned more than 2x Semis regime with a much smaller worst fall, and it made money in 2018 and 2022 when 2x Semis lost.

## How it decides

After each US close, from **USD's own daily bar**:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | Supertrend(ATR 20, ×4.5) on USD is **up** AND USD closes **above its SMA200** | USD at the volatility-capped size, rest parked |
| **In · dip day** | **IBS < 0.15**: USD closed in the bottom 15% of the day's range | **100% USD for the next day** |
| **Off** | neither | 50% GLD + 50% BIL |

**IBS** (internal bar strength) = (close − low) ÷ (high − low). A close near the low of a strong-moving ETF tends to bounce the next
day; the research found these one-day trades are the core of the edge on USD (they worked both in 2007–2026 and in the unseen
2001–2007 test).

**Size in the trend** = the smaller of 100% and **40% ÷ USD's 20-day volatility** (the standard deviation of its last 20 daily
returns × √252). USD normally moves 45–80% a year, so the trend size is usually **50–90%**:

| USD 20-day volatility | Trend size |
|---|---|
| 35% (calm) | 100% |
| 50% | 80% |
| 70% (jumpy) | 57% |
| 100% (crash) | 40% |

**Dip signal** → 100% for the next day, even while the trend is on. **The 20-point rule:** the size is changed only when the new size
differs from the size held by more than 20 points. A fresh entry takes the size of the day; off sets it to 0. Written as the research
has it (resize every day) the strategy traded about 134 times a year; with the rule about 62, with the same 10-year result.

## What it holds

USD (2x semiconductors) at 40–100%; the rest, and everything when off, **50% GLD (gold) + 50% BIL (T-bills)**. On average about half the money is in USD. A dip day is a one-day trade: bought at the open after the weak close, back to the trend size or to parking at the next open unless a new dip signal keeps it.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | USD held a year / worst fall | SMH held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+79.6%** | −26.2% | 1.57 | +42.6% / −39.4% | +52.9% / −24.6% |
| 3 years | **+73.6%** | −31.2% | 1.37 | +100.8% / −64.5% | +54.6% / −36.0% |
| 5 years | **+81.3%** | −31.2% | 1.45 | +50.3% / −77.8% | +31.5% / −45.3% |
| 10 years | **+62.5%** | −37.0% | 1.28 | +50.4% / −77.8% | +31.4% / −45.3% |
| All (from 14 Nov 2007) | **+41.7%** | −43.2% | 1.05 | +27.1% / −87.0% | +20.1% / −56.4% |

- **Worst fall:** −43.2%, from 29 May 2015 to 27 Jun 2016; back at the old high on 15 May 2017.
- **$10,000 became** $7,377,198 (+73,672%) from 14 Nov 2007 to 23 Oct 2026.
- **In the market** 59% of the days · **59.5 trades a year** · 58% of round trips made money (average +1.7%).
- Volatility 39% a year.

### Year by year

| Year | Strategy | USD held | SMH held |
|---|---|---|---|
| 2026 (part) | **+82.4%** | +39.4% | +46.4% |
| 2025 | **+20.8%** | +61.2% | +48.7% |
| 2024 | **+92.3%** | +139.4% | +38.5% |
| 2023 | **+158.0%** | +228.6% | +72.3% |
| 2022 | **+32.2%** | −68.7% | −34.3% |
| 2021 | **+60.5%** | +104.3% | +41.4% |
| 2020 | **+69.1%** | +67.7% | +54.5% |
| 2019 | **+34.3%** | +108.3% | +62.0% |
| 2018 | **+33.7%** | −27.5% | −10.8% |
| 2017 | **+65.3%** | +81.0% | +36.5% |
| 2016 | **+9.6%** | +56.2% | +34.5% |
| 2015 | **−20.3%** | −7.9% | −2.5% |
| 2014 | **+39.0%** | +76.3% | +28.7% |
| 2013 | **+57.0%** | +76.3% | +31.2% |
| 2012 | **+4.7%** | −10.8% | +6.2% |
| 2011 | **−8.9%** | −14.9% | −6.5% |
| 2010 | **+39.2%** | +19.1% | +16.5% |
| 2009 | **+102.8%** | +135.4% | +58.5% |
| 2008 | **+26.4%** | −80.0% | −45.8% |
| 2007 (part) | **−2.3%** | −5.2% | −1.4% |

## The research

**Research on single Stock Nasdaq · USD own-price strategies, candidate C (Trend + IBS-dip, aggressive)**, resized every day, Oct 2016 – Oct 2026: **66.8% a year, worst fall −36.7%, Sharpe 1.38** (2x Semis regime over the same years: 57.2%, −45.2%). Unseen test 2001–2007 with USD rebuilt from SMH: **22.0% a year** when 2x Semis lost 7.2% a year and USD held lost 25%. Over 2001–2026: 38.6% a year, worst fall −45.8%. 243 nearby settings had a median of 61% a year over 10 years. Costs matter: at 0.10% per side the 10-year result drops to 62.4%, at 0.15% to 58.5%.

**Checked in this bot (25 Oct 2026):** the bot's signals match the research rules day for day (same in and out days on every day since 2016). The research rebuilt with daily resizing gives 64.0% a year over 10 years (research 66.8%); the bot's version with the 20-point rule gives 62.5% with a −37.0% worst fall. Prices from TradingView for USD (no dividends, as in the research); the same method reproduces the server's 2x Semis backtest within half a point.

## Risks and what to expect

- **2x chips:** worst falls of −37% (Nov 2017 – Jun 2018), −31% (Jan – Jun 2025) and −43% (2015 – 16). In the research's long test −46% (2001).
- **Gives up part of the big rallies:** 2019 +34% vs USD +108%; 2024 +92% vs +139%; 2025 +21% vs +61%. Over the last 3 years 2x Semis regime earned more (+111% a year vs +74%).
- **Many trades:** about 62 a year (one-day dip trades plus resizes). Each pays the spread on USD, so fills at the open matter more than for any other strategy in the bot.
- **Same sector as 2x Semis regime** (monthly correlation about 0.6): treat it as an alternative or a partner to 2x Semis, not as diversification. With QLD Trend + IBS-dip the correlation is about 0.5.
- **Webull:** USD was refused on the shared test account. Run **Go-live → Test trade** on your Live account before giving it money.

## Check it on TradingView

USD daily: **Supertrend** (ATR 20, factor 4.5), **Moving Average** 200. IBS has no built-in indicator: (close − low) ÷ (high − low) of the day. USD's 20-day volatility: the standard deviation of its last 20 daily returns × √252 (TradingView's *Historical Volatility* indicator, length 20, uses √365 and log returns, so it reads about 20% higher).
