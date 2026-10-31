<!--{"title": "QLD Trend + bear-dip + Vol", "group": "The strategies"}-->
# QLD Trend + bear-dip + Vol

The same rules as [QLD + Trend + bear-dip](#/docs/strategy-qld-tbd), plus a **volatility filter**: the trend half holds **QLD (2x Nasdaq-100)** only while QQQ is above its 200-day average **and calm**. When the market turns jumpy, the strategy steps aside (half gold, half cash) even above the average. The RSI(2) dip trades are unchanged and are not filtered.

The filter helps most in a sell-off that starts from a high, while QQQ is still above its average. It stepped aside in late February 2020 as the crash began, and from December 2021 through January 2022 before QQQ broke its average. So the worst fall over 10 years was −25% instead of −43%. The price is that it also steps aside in nervous bull markets (2014, 2024, this year), so it can lag the plain version for a year or two.

## How it decides

After each US close, from QQQ's daily closes:

| State | Rule | Holds |
|---|---|---|
| **In · trend** | QQQ closes above its SMA200 **and** is calm | 99% QLD |
| **In · dip trade** | below SMA200 a dip trade opens when RSI(2) < 5; it closes on the first close above SMA5 | 99% QLD |
| **Out · jumpy** | above SMA200 but not calm, and no dip trade open | 49.5% GLD, rest cash |
| **Out** | below SMA200 and no dip trade | 49.5% GLD, rest cash |

**Calm** means: the standard deviation of QQQ's last 20 daily changes is **below the 80th percentile** of the same number over the last 252 trading days (today included). So the filter is relative to the last year. It does not use a fixed level, and it turns off on roughly the jumpiest fifth of days. An open dip trade always runs to its exit, even on a jumpy day.

The strategy page shows today's volatility and its threshold in the checks, a **Volatility** pane under the RSI, and a purple ribbon on jumpy days.

## What it holds

QLD (2x Nasdaq-100) while in. When out: **half GLD (gold), half cash** (the default since 31 Oct 2026). Nothing else.

Two settings in Parameters decide where the parked money waits:
- *Gold share when out (%)*: 50 = half in GLD (default), 0 = none, 100 = all.
- *When out, hold*: empty = plain cash (default); BIL = T-bills, as the research did.

**Why cash, not BIL:** every trip into BIL and back costs 0.22% in Webull fees, and BIL needs about three weeks out to earn that back at 4% a year. This strategy's out spells are often shorter (the jumpy-market exits), so plain cash came out ahead in every period of the bot's backtest, even counting cash at 0% interest.

**Why half gold:** gold tends to rise in the stressed markets when this strategy is out.

The bot's backtest, Webull's fee, prices to 26 Oct 2026 (a year / worst fall):

| When out | 1 year | 3 years | 5 years | 10 years | Since Oct 2007 |
|---|---|---|---|---|---|
| all BIL (the research's way) | +9.3% / −18.6% | +44.5% / −21.6% | +35.1% / −22.5% | +42.0% / −24.5% | +34.9% / −34.4% |
| all cash | +9.8% / −18.6% | +45.7% / −21.1% | +36.7% / −22.5% | +43.2% / −24.3% | +36.6% / −33.5% |
| half GLD + half BIL | +12.3% / −18.6% | +52.1% / −19.8% | +41.2% / −22.5% | +45.9% / −23.9% | +38.6% / −29.7% |
| **half GLD + half cash (default)** | **+12.6% / −18.6%** | **+52.7% / −19.6%** | **+42.0% / −22.5%** | **+46.5% / −23.8%** | **+39.5% / −29.2%** |
| all GLD | +14.7% / −18.6% | +59.6% / −19.9% | +47.0% / −22.5% | +49.6% / −23.9% | +42.0% / −30.3% |

Across 120 neighbouring settings, half gold (with half BIL) beat all-T-bills on return per unit of risk in every one, and on return in 92% of them before 2016 (before the recent gold boom). The cost: gold can fall while the money waits in it (−28% in 2013, about −28% from its January 2026 high), and in about half of those settings the worst fall was deeper (by about 2 points in the middle setting). 50% keeps most of the gain with less gold risk than 100%.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart, so a change is done in about 45 minutes. The filter adds trades: about **12 a year** against 9 for the plain version.

## Backtest results

The tables below are the original settings (parked all in BIL); the table above has today's default, about 4 points a year more over 10 years. Numbers from the bot's own backtest code on 30 Oct 2026, run on prices up to 26 Oct 2026: the strategy's live code over Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). Open the strategy → **Backtest** for today's numbers, the chart and every trade.

| Period | A year | Worst fall | Sharpe | Plain Trend + bear-dip | QLD held a year / worst fall | QQQ held a year / worst fall |
|---|---|---|---|---|---|---|
| 1 year | **+9.3%** | −18.6% | 0.45 | +19.4% / −22.7% | +19.0% / −25.2% | +13.6% / −12.2% |
| 3 years | **+44.5%** | −21.6% | 1.32 | +55.6% / −26.1% | +48.5% / −42.3% | +27.6% / −22.9% |
| 5 years | **+35.1%** | −22.5% | 1.13 | +32.5% / −30.1% | +16.8% / −63.8% | +13.5% / −35.6% |
| 10 years | **+42.0%** | −24.5% | 1.31 | +36.5% / −42.7% | +32.4% / −63.8% | +19.7% / −35.6% |
| Oct 2007 – Oct 2026 | **+34.9%** | −34.4% | 1.15 | +30.5% / −42.7% | +22.8% / −84.0% | |

- **Worst fall:** −34.4%, from 5 Jun 2008 to 9 Oct 2008, in the 2008 crash. Back at the old high on 13 Nov 2008. Over the last 10 years the worst fall was −24.5% (29 Aug – 24 Dec 2018).
- **In the market** 71% of the days (plain version 83%) · **12 trades a year** · 56% of round trips made money (average +6.1%).
- Volatility 30% a year (plain version 34%).

### Year by year

| Year | Strategy | Plain Trend + bear-dip | QLD held | QQQ held |
|---|---|---|---|---|
| 2026 (part) | **+15.7%** | +26.4% | +26.0% | +16.1% |
| 2025 | **+46.5%** | +49.6% | +30.1% | +20.2% |
| 2024 | **+27.2%** | +42.2% | +42.4% | +24.8% |
| 2023 | **+65.7%** | +65.7% | +116.9% | +53.8% |
| 2022 | **+15.0%** | −16.2% | −60.6% | −33.1% |
| 2021 | **+54.5%** | +54.5% | +54.7% | +26.8% |
| 2020 | **+113.0%** | +63.9% | +88.9% | +47.6% |
| 2019 | **+45.8%** | +45.8% | +81.4% | +37.8% |
| 2018 | **+12.2%** | −4.3% | −8.4% | −1.0% |
| 2017 | **+50.7%** | +69.8% | +70.3% | +31.5% |
| 2016 | **+6.9%** | −4.0% | +9.9% | +5.9% |
| 2015 | **+3.6%** | +3.5% | +14.6% | +8.3% |
| 2014 | **+9.8%** | +37.1% | +37.3% | +17.4% |
| 2013 | **+78.1%** | +77.8% | +81.7% | +35.1% |
| 2012 | **+10.9%** | +10.9% | +34.6% | +16.7% |
| 2011 | **+9.1%** | +3.3% | +0.0% | +2.5% |
| 2010 | **+33.7%** | +14.2% | +36.9% | +19.0% |
| 2009 | **+83.3%** | +83.3% | +121.2% | +53.8% |
| 2008 | **+39.4%** | +39.3% | −72.9% | −41.9% |

It beat the plain version in 6 years and lagged it in 5 (the other 8 were the same). The lags all came in nervous bull markets: 2014, 2017, 2024, 2025 and this year.

## The research

**ETF Strategy Lab v3 (Research on ETF, 30 Oct 2026)**, Oct 2007 – Oct 2026, with a 0.05% cost: **38.4% a year, worst fall −33.0%, Sharpe 1.17**. The same rules without the filter made 32.9% (−42.5%).

My own re-implementation, written from the rules rather than the research code, gave 37.8% / −33.1% / Sharpe 1.21 under the research's assumptions, and 36.9% / −33.7% with Webull's real fee. The bot's live code takes the same position as that re-implementation on every one of the 5,793 days. The bot's backtest is about 2 points lower (34.9%) because it trades in lots at the real open.

**Be careful with the 38%.** The research chose this filter (20 days, 80th percentile, SMA200) as the best of about 60 neighbouring settings:

- The **median** neighbour made about 32% a year with a −35.6% worst fall.
- Choosing the best setting on 2007–2016 data only and running it on 2016–2026 gave 28.8% a year.

What does hold up across the neighbours is the **risk** side: 90% of the neighbouring settings had a smaller worst fall than the plain version, and 77% had a better Sharpe. Only 42% had a higher yearly return. So treat the filter as a way to make the falls smaller, not as a way to earn more.

### Also tried (30 Oct 2026)

- **Reading the signal from QLD itself** instead of QQQ: not better. Over 120 neighbouring settings the median was about the same over 10 years (33.8% against 33.3%), but lower since 2007 (23.1% against 27.8%) with much deeper falls (−60% against −40%). This page's exact settings on QLD's own price: 32.6% / −49.9% since 2007, against 36.9% / −33.7% from QQQ.
- **The same idea on USD (2x semis) and ROM (2x tech):** the filter again made the falls smaller (80–99% of neighbouring settings) without adding return. On USD nothing beat the bot's USD Trend + IBS-dip, which already sizes by volatility. On ROM, switching the filter on in ROM Trend + RSI(2) (*Volatility filter: percentile* = 80) kept the 10-year return (51.1% against 51.3%) and cut the 10-year worst fall from −37.9% to −28.8%. That is optional, and the full write-up is in the project notes.
- **Ichimoku ensemble + Vol + dip** on USD and ROM: no better than the Trend + bear-dip versions, so it was not added.

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). This entry uses the bot's own backtest (34.9%), not the research's 38.4%, because of the selection effect above. The return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:qld_tbdv-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **2x Nasdaq:** a crash that starts calm (one big gap down) still hits at twice the drop before the filter reacts. The filter uses closes, so it needs a few jumpy days to switch off.
- **Lags in nervous bull markets:** over the last 12 months it was out for about 27% of the days (31 Mar – 24 Apr, 5 Jun – 27 Jul and 30 Jul – 19 Aug 2026), so it made +9% against +19% for the plain version.
- **More trades:** the filter flips in and out a few extra times a year, and each round trip costs about 0.22% in fees.
- **Same index as other strategies:** it is almost the same strategy as QLD + Trend + bear-dip (correlation 0.82), and overlaps with QLD regime, QLD IBS-dip and C2-7 Momentum. Running both bear-dip versions doubles the same bet.
- Webull: QLD needs the Leveraged & Inverse ETF permission.

## Check it on TradingView

QQQ daily: **Moving Average** 200 and 5, **Relative Strength Index** length 2. TradingView's **Historical Volatility** indicator is annualised and uses log changes, so it will not match exactly. Compare with the bot's Volatility pane instead (daily %, and the 1-year 80th percentile line). The strategy's **Health** check recomputes the filter separately, the long way.
