<!--{"title": "QLD Trend + IBS-dip", "group": "The strategies"}-->
# QLD Trend + IBS-dip

Holds **QLD (2x Nasdaq-100)** timed by **QLD's own price**: while its Supertrend is up and it is above its 200-day average, or for **one day after a weak close**. The size is **capped by Nasdaq volatility**, and idle money sits in **gold and cash**. From the research's *strategy 2*: the same 10-year return as the other QLD strategies with a much smaller worst fall, and the only one of them that made money in 2022.

## How it decides

After each US close, from **QLD's own daily bar** (and QQQ's closes for the size):

| State | Rule | Holds |
|---|---|---|
| **In · trend** | Supertrend(ATR 14, ×4) on QLD is **up** AND QLD closes **above its SMA200** | QLD at the capped size, rest parked |
| **In · dip day** | **IBS < 0.15** AND **ADX(14) > 20** (QLD closed near the day's low in a strong move) | QLD for the **next day only** |
| **Off** | neither | 50% GLD + 50% cash |

**IBS** (internal bar strength) = (close − low) ÷ (high − low): 0 means QLD closed on the day's low, 1 on its high. Weak closes
tend to bounce the next day; ADX above 20 keeps it to days with a real move.

**Size when in** = the smaller of 100% and **50% ÷ (2 × QQQ's 60-day volatility)**. With QQQ volatility at 18% a year that is
50 ÷ 36 → 100%; at 35% (a stressed market) it is 50 ÷ 70 → 71%. The size is changed only when the new size differs from the size
held by **more than 20 points**, so small volatility moves do not trade. The part not in QLD is parked like the off state.

## What it holds

QLD (2x Nasdaq-100) at the capped size; the rest, and everything when off, **50% GLD (gold) + 50% cash**. The cash half used to be
BIL (T-bills); see *Lower-cost settings* below. A dip day is a one-day trade: bought at the open after the weak close, sold at the next open unless the trend or a new dip signal keeps it.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes.

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+51.1%** | −12.8% | 1.59 | +22.3% / −25.1% | +15.9% / −12.0% |
| 3 years | **+50.7%** | −21.8% | 1.64 | +44.0% / −42.3% | +26.3% / −22.8% |
| 5 years | **+44.8%** | −21.8% | 1.51 | +16.6% / −63.7% | +14.0% / −35.1% |
| 10 years | **+34.4%** | −27.2% | 1.25 | +31.9% / −63.7% | +20.2% / −35.1% |
| All (from 9 Apr 2007) | **+29.1%** | −30.6% | 1.11 | +24.4% / −83.1% | +16.1% / −53.4% |

- **Worst fall:** −30.6%, from 18 Apr 2016 to 1 Dec 2016; back at the old high on 15 May 2017.
- **$10,000 became** $1,469,047 (+14,590%) from 9 Apr 2007 to 23 Oct 2026.
- **In the market** 61% of the days · **28.7 trades a year** · 61% of round trips made money (average +2.0%).
- Volatility 26% a year.

### Year by year

| Year | Strategy | QLD held | QQQ held |
|---|---|---|---|
| 2026 (part) | **+52.1%** | +22.5% | +15.1% |
| 2025 | **+52.0%** | +30.4% | +20.8% |
| 2024 | **+27.1%** | +42.8% | +25.6% |
| 2023 | **+70.0%** | +117.7% | +54.9% |
| 2022 | **+21.8%** | −60.5% | −32.6% |
| 2021 | **+10.5%** | +54.7% | +27.4% |
| 2020 | **+72.0%** | +88.9% | +48.4% |
| 2019 | **+22.1%** | +81.7% | +39.0% |
| 2018 | **+2.1%** | −8.3% | −0.1% |
| 2017 | **+53.1%** | +70.3% | +32.7% |
| 2016 | **−18.7%** | +10.0% | +7.1% |
| 2015 | **+2.0%** | +14.7% | +9.4% |
| 2014 | **+10.0%** | +37.6% | +19.2% |
| 2013 | **+49.7%** | +82.1% | +36.6% |
| 2012 | **+14.1%** | +34.8% | +18.1% |
| 2011 | **−11.1%** | +0.0% | +3.5% |
| 2010 | **+45.8%** | +36.9% | +20.1% |
| 2009 | **+78.6%** | +121.2% | +54.7% |
| 2008 | **+49.3%** | −72.9% | −41.7% |
| 2007 (part) | **+23.6%** | +24.5% | +15.5% |

## The research

**Research on single Stock Nasdaq · strategy 2** (QLD own-price + vol cap, 50/50 gold & T-bill parking), Oct 2016 – Oct 2026: **37.7% a year, worst fall −31.6%, Sharpe 1.27**. Over 1999–2026, with QLD rebuilt from the Nasdaq-100 before it existed: **30.1% a year, worst fall −32%** — it held up in the dot-com crash (+19.7% a year in 2000–02) when the bot's other QLD strategies lost money. 624 nearby settings had a median of 25% a year with a −37% worst fall, so plan on less than the best case.

### Lower-cost settings (26 Oct 2026)

Webull Thailand charges **0.107% of every buy and every sell** (0.10% + 7% VAT). This strategy switches 25–30 times a year, mostly
one-day dip trades, and with the research's parking every switch traded three ETFs (QLD, GLD and BIL). At the real fee the research
settings earned 30.4% a year over 10 years in the bot's backtest instead of 34.5% at 0.05%. Two changes win most of it back:

| Bot backtest at the real fee | 10 years | Worst fall (10 years) | Since 2007 | 2007–2016 |
|---|---|---|---|---|
| Research settings: dip below IBS 0.20, parking GLD + BIL | 30.4% | −30.5% | 25.5% | 20.1% |
| Parking GLD + **cash** | 31.7% | −30.2% | 27.3% | 22.6% |
| … and a dip only **below IBS 0.15** (the bot now) | **34.4%** | **−27.2%** | **29.1%** | **23.5%** |

- **Cash instead of BIL:** every switch trades about half as much. Cash earns no T-bill interest; the numbers above already count
  that. It won in all 50 combinations of IBS, ADX and dip size tried, over 10 years and since 2007.
- **IBS below 0.15:** fewer, stronger dips (25 trades a year instead of 29). IBS 0.10–0.15 beat 0.20 for every ADX setting tried
  (0–30); 0.20 sat in a dip between its neighbours.
- **Not tuned on the test years:** the research chose its settings on 2016–2026; 2007–2016 also improved (last column), and the
  new settings also win at a 0.05% or 0.16% fee.
- Numbers from the bot's engine on the research's prices; the server's own backtest gives the same 34.4% for the new settings.
- Strategies that still had the old default settings were moved to these once, on 26 Oct 2026 (Logs shows it). To go back:
  Parameters → *Dip day when IBS is below* 0.2 and *Keep the T-bill part as cash* off.

### Compared with the research

The research's 37.7% a year charged 0.05% once per switch. The bot charges the real fee on every ETF it trades (selling gold and
cash parking *and* buying QLD, then the reverse), which is what real trading costs. Its signals match the research rules on every
day since 2007 (same settings). A data tie was fixed on 25 Oct 2026: QLD's IBS of exactly 0.20 on 10 Feb 2022 came out as
0.19999… from Yahoo's prices; the bot now rounds IBS to 4 decimals so float noise can no longer decide a tie.

## Sister strategy

**USD Trend + IBS-dip** uses the same rules on USD (2x semiconductors) with settings the research chose for USD: Supertrend 20 × 4.5,
dip days on IBS < 0.15 held at 100%, size from USD's own 20-day volatility with a 40% cap. It has more return and deeper falls
(10 years at the real fee: +58.7% a year, worst fall −38.1%). Monthly correlation between the two is about 0.5, so together they spread the risk
better than either QLD strategy next to 2x Semis.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:qld_ibs-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Gives up the big rallies:** the volatility cap and the quick exits leave money on the table in strong years (2021 +11% vs QLD +55%, 2024 +27% vs +43%, 2019 +22% vs +82%).
- **Many small trades:** about 25 a year, many of them one-day dip trades at the open. Each pays Webull's 0.107% fee and the spread on QLD, so fills matter more than for the other QLD strategies.
- **2x Nasdaq:** the worst fall in 10 years was −27% (January – November 2018); since 2007 −31% (April – December 2016).
- Partly the same bet as QLD regime, QLD + Trend + bear-dip and C2-7 (monthly correlation about 0.7); it pairs best with 2x Semis (0.53).
- Webull: QLD needs the Leveraged & Inverse ETF permission; GLD is a plain ETF.

## Check it on TradingView

QLD daily: **Supertrend** (ATR 14, factor 4), **Moving Average** 200, **Average Directional Index** 14. IBS has no built-in indicator: (close − low) ÷ (high − low) of the day. QQQ's 60-day volatility: the standard deviation of its last 60 daily returns × √252.
