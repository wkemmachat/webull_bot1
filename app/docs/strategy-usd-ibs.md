<!--{"title": "USD Trend + IBS-dip", "group": "The strategies"}-->
# USD Trend + IBS-dip

Holds **USD (ProShares Ultra Semiconductors, 2x chips)** timed by **USD's own price**: while its Supertrend is up and it is above its 200-day average, at a size that shrinks when USD gets jumpy; and for **one day at full size after a weak close**. Idle money sits in **gold and cash**. This is the research's *candidate C (aggressive)*, run with a 20-point resize rule so it trades about half as often. Over 10 years it earned more than 2x Semis regime with a much smaller worst fall, and it made money in 2018 and 2022 when 2x Semis lost.

## How it decides

After each US close, from **USD's own daily bar**:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | Supertrend(ATR 20, ×4.5) on USD is **up** AND USD closes **above its SMA200** | USD at the volatility-capped size, rest parked |
| **In · dip day** | **IBS < 0.15**: USD closed in the bottom 15% of the day's range | **100% USD for the next day** |
| **Off** | neither | 50% GLD + 50% cash |

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

USD (2x semiconductors) at 40–100%; the rest, and everything when off, **50% GLD (gold) + 50% cash** (until 26 Oct 2026 the
cash half was BIL; see *Lower-cost settings* below). On average about half the money is in USD. A dip day is a one-day trade: bought at the open after the weak close, back to the trend size or to parking at the next open unless a new dip signal keeps it.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | USD held a year / worst fall | SMH held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+84.6%** | −26.7% | 1.62 | +43.4% / −39.3% | +53.4% / −24.6% |
| 3 years | **+71.8%** | −32.5% | 1.34 | +101.5% / −64.5% | +55.3% / −35.7% |
| 5 years | **+76.7%** | −32.5% | 1.39 | +50.7% / −77.8% | +32.3% / −45.3% |
| 10 years | **+58.7%** | −38.1% | 1.22 | +51.0% / −77.8% | +32.6% / −45.3% |
| All (from 14 Nov 2007) | **+36.7%** | −51.5% | 0.96 | +28.1% / −86.1% | +21.1% / −56.4% |

- **Worst fall:** −51.5%, from 5 Dec 2014 to 27 Jun 2016; back at the old high on 2 Oct 2017.
- **$10,000 became** $3,748,772 (+37,388%) from 14 Nov 2007 to 23 Oct 2026.
- **In the market** 59% of the days · **59.7 trades a year** · 57% of round trips made money (average +1.6%).
- Volatility 39% a year.

### Year by year

| Year | Strategy | USD held | SMH held |
|---|---|---|---|
| 2026 (part) | **+89.1%** | +40.0% | +46.4% |
| 2025 | **+17.6%** | +62.1% | +49.2% |
| 2024 | **+85.4%** | +139.6% | +39.1% |
| 2023 | **+148.6%** | +228.8% | +73.4% |
| 2022 | **+24.4%** | −68.6% | −33.5% |
| 2021 | **+56.2%** | +104.3% | +42.1% |
| 2020 | **+62.5%** | +68.2% | +55.5% |
| 2019 | **+31.7%** | +110.4% | +64.5% |
| 2018 | **+33.0%** | −26.9% | −9.1% |
| 2017 | **+62.2%** | +81.7% | +38.5% |
| 2016 | **−3.9%** | +56.8% | +35.5% |
| 2015 | **−24.2%** | −7.5% | −0.3% |
| 2014 | **+38.4%** | +78.1% | +30.2% |
| 2013 | **+56.8%** | +77.7% | +33.3% |
| 2012 | **+0.1%** | −10.2% | +8.6% |
| 2011 | **−12.7%** | −14.9% | −6.5% |
| 2010 | **+35.0%** | +19.4% | +16.5% |
| 2009 | **+90.1%** | +137.5% | +58.5% |
| 2008 | **+19.0%** | −79.8% | −45.8% |
| 2007 (part) | **−3.5%** | −0.0% | −1.4% |

## The research

**Research on single Stock Nasdaq · USD own-price strategies, candidate C (Trend + IBS-dip, aggressive)**, resized every day, Oct 2016 – Oct 2026: **66.8% a year, worst fall −36.7%, Sharpe 1.38** (2x Semis regime over the same years: 57.2%, −45.2%). Unseen test 2001–2007 with USD rebuilt from SMH: **22.0% a year** when 2x Semis lost 7.2% a year and USD held lost 25%. Over 2001–2026: 38.6% a year, worst fall −45.8%. 243 nearby settings had a median of 61% a year over 10 years. Costs matter: at 0.10% per side the 10-year result drops to 62.4%, at 0.15% to 58.5%.

**Checked in this bot (25 Oct 2026):** the bot's signals match the research rules day for day (same in and out days on every day since 2016). The research rebuilt with daily resizing gives 64.0% a year over 10 years (research 66.8%); the bot's version with the 20-point rule gave 62.5% with a −37.0% worst fall at a 0.05% cost. Prices from TradingView for USD (no dividends, as in the research); the same method reproduces the server's 2x Semis backtest within half a point.

### Lower-cost settings (26 Oct 2026)

Webull Thailand charges **0.107% of every buy and every sell** (0.10% + 7% VAT). This strategy trades about 62 times a year, and with
the research's parking each trade also bought or sold GLD and BIL. At the real fee the 10-year result fell from 62.5% to 53.2% a year.
Keeping the T-bill half of the parking as **cash** wins part of it back:

| Bot backtest at the real fee (research prices) | 10 years | Worst fall (10 years) | Since Nov 2007 | 2007–2016 |
|---|---|---|---|---|
| Research parking: 50% GLD + 50% BIL | 53.2% | −39.3% | 33.3% | 13.8% |
| 50% GLD + 50% **cash** (the bot now) | **56.4%** | **−38.3%** | **36.6%** | **17.1%** |

- It won in 44 of the 50 combinations of IBS, ADX and dip size tried over 10 years, and in all 50 since 2007. Cash earns no T-bill
  interest; the numbers above already count that.
- The other rules stay as the research chose them (IBS < 0.15, Supertrend 20 × 4.5, 20-point resizing): a wider resize band or
  other dip thresholds helped in some years and hurt in others.
- The server's own backtest (Yahoo prices with dividends) gives **58.7%** a year over 10 years for the new settings.
- A strategy that still had the old default settings was moved to this once, on 26 Oct 2026 (Logs shows it). To go back:
  Parameters → *Keep the T-bill part as cash* off.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:usd_ibs-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **2x chips:** worst falls of −38% (Nov 2017 – Jun 2018), −32% (Jan – Jun 2025) and −52% (Dec 2014 – Jun 2016, back at the high in Oct 2017). In the research's long test −46% (2001).
- **Gives up part of the big rallies:** 2019 +32% vs USD +110%; 2024 +85% vs +140%; 2025 +18% vs +62%. Over the last 3 years 2x Semis regime earned more (+109% a year vs +72%).
- **Many trades:** about 62 a year (one-day dip trades plus resizes). Each pays Webull's 0.107% fee and the spread on USD, so fees and fills at the open matter more than for any other strategy in the bot.
- **Same sector as 2x Semis regime** (monthly correlation about 0.6): treat it as an alternative or a partner to 2x Semis, not as diversification. With QLD Trend + IBS-dip the correlation is about 0.5.
- **Webull:** USD was refused on the shared test account. Run **Go-live → Test trade** on your Live account before giving it money.

## Check it on TradingView

USD daily: **Supertrend** (ATR 20, factor 4.5), **Moving Average** 200. IBS has no built-in indicator: (close − low) ÷ (high − low) of the day. USD's 20-day volatility: the standard deviation of its last 20 daily returns × √252 (TradingView's *Historical Volatility* indicator, length 20, uses √365 and log returns, so it reads about 20% higher).
