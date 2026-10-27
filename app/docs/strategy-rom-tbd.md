<!--{"title": "ROM Trend + RSI(2)", "group": "The strategies"}-->
# ROM Trend + RSI(2)

Holds **ROM (ProShares Ultra Technology, 2x US tech)** while the 1x tech ETF **IYW** is above its 150-day average; below it, only sharp RSI(2) dips are bought and sold on the first close above the 10-day average. Cash the rest of the time. It is the **QLD + Trend + bear-dip** rule set on 2x US technology instead of 2x Nasdaq-100, found in the 2x ETF research of 26 Oct 2026: the best new 2x strategy of 39 ETFs tested, and the one that pairs best with USD Trend + IBS-dip.

## How it decides

After each US close, from **IYW's** daily closes (ROM doubles IYW's index, the Dow Jones U.S. Technology Index):

| State | Rule | Holds |
|---|---|---|
| **In · trend** | IYW closes above its **SMA150** | 99% ROM |
| **In · dip trade** | below SMA150, a dip trade opens when **RSI(2) < 5** and closes on the first close above **SMA10** | 99% ROM |
| **Out** | below SMA150 and no dip trade | cash |

Why IYW and not ROM's own chart: the signal comes from the clean, liquid 1x ETF; ROM's own bars are thinner (about $5M traded a day) and noisier.

## What it holds

ROM or cash. Nothing else. Cash is kept as cash (not a T-bill ETF): the strategy is in the market about 80% of the days and every switch would otherwise pay Webull's fee twice.

## When it trades

Decided after each US close (the bot checks at about 03:10 Bangkok). Orders start at the **next market open** (20:30 Bangkok in US summer time, 21:30 in winter), 10 lots 5 minutes apart. About **5–10 trades a year**: the fewest of the bot's strategies, so Webull's fee costs it under 1 point a year.

ROM trades about $5M a day, so the bot's limit orders matter: they never pay more than the limit (Execution → limit offset).

## Backtest results

Numbers from the bot's own backtest code on 26 Oct 2026, run on TradingView prices (no dividends; ROM pays almost none), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell). The **Backtest** tab shows the server's numbers on Yahoo prices once the server has ROM's history.

| Period | A year | Worst fall | Sharpe | ROM held a year / worst fall | IYW held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+25.6%** | −31.1% | 0.71 | +42.9% / −32.4% | +25.0% / −17.9% |
| 3 years | **+53.8%** | −31.7% | 1.18 | +52.3% / −48.2% | +33.4% / −26.5% |
| 5 years | **+41.2%** | −31.7% | 1.01 | +19.9% / −67.5% | +18.3% / −39.6% |
| 10 years | **+50.0%** | −37.7% | 1.19 | +36.7% / −67.5% | +23.6% / −39.6% |
| All (from 1 Feb 2007) | **+30.0%** | −66.1% | 0.87 | +23.4% / −83.8% | +15.8% / −55.1% |

- **Worst fall:** −66.1%, from 19 Jul 2007 to 20 Nov 2008; back at the old high on 14 Apr 2010.
- **$10,000 became** $1,764,600 (+17,546%) from 1 Feb 2007 to 23 Oct 2026.
- **In the market** 82% of the days · **9.5 trades a year** · 44% of round trips made money (average +8.2%).
- Volatility 39% a year.

### Year by year

| Year | Strategy | ROM held | IYW held |
|---|---|---|---|
| 2026 (part) | **+28.8%** | +46.5% | +25.2% |
| 2025 | **+67.2%** | +35.2% | +25.2% |
| 2024 | **+26.4%** | +31.4% | +30.0% |
| 2023 | **+94.0%** | +130.7% | +64.8% |
| 2022 | **−7.0%** | −63.9% | −35.1% |
| 2021 | **+77.4%** | +77.8% | +35.0% |
| 2020 | **+77.8%** | +80.2% | +46.3% |
| 2019 | **+50.5%** | +101.7% | +45.4% |
| 2018 | **+37.5%** | −10.2% | −1.7% |
| 2017 | **+80.4%** | +81.0% | +35.4% |
| 2016 | **+16.7%** | +23.2% | +12.3% |
| 2015 | **−7.1%** | +3.5% | +2.5% |
| 2014 | **+31.9%** | +38.6% | +18.1% |
| 2013 | **+37.0%** | +56.9% | +25.1% |
| 2012 | **+25.7%** | +19.2% | +10.7% |
| 2011 | **+2.8%** | −7.3% | −0.8% |
| 2010 | **+7.5%** | +19.9% | +11.9% |
| 2009 | **+113.8%** | +145.8% | +62.9% |
| 2008 | **−42.6%** | −73.4% | −43.4% |
| 2007 (part) | **−8.5%** | +15.5% | +13.0% |

## The research

**2x ETF Strategy Research (26 Oct 2026)**: 39 active 2x ETFs that are not single stocks, 4 strategy families, about 20,000 backtests at Webull's real fee. Only the tech ETFs (ROM, QLD, USD) gave high returns with timing rules. For ROM the Trend + RSI(2) rule was best: **50.9% a year over 10 years, worst fall −37.9%, Sharpe 1.20** (research engine; the bot's code gives 50.0%). It is robust: all 24 settings tried had a median of 41% a year, and 2008–2016, which the settings were not chosen on, gave 15% a year.

Compared with the bot's other strategies (10 years):

| | ROM Trend + RSI(2) | USD Trend + IBS-dip | QLD + Trend + bear-dip |
|---|---|---|---|
| A year | 50.0% | 58.7% | 36.4% |
| Worst fall | −37.7% | −38.1% | −42.6% |
| Without its best year | 47.0% (no 2023) | 52.6% (no 2023) | — |
| Worst 12 months | −13.5% | −25.2% | — |
| Longest below a high | 372 days (2022–23) | 381 days (2017–18) | — |

The first two rows are the bot's own backtests; the last three are from the research engine.

**With USD Trend + IBS-dip:** the two move together much less than the bot's QLD strategies do (weekly correlation 0.52). Half the money in each, rebalanced once a year, made **56.6% a year with a worst fall of −28.3%** over 10 years, against 60.6% and −38.5% for USD Trend + IBS-dip alone (research engine).

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:rom_tbd-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **2x tech:** a crash before IYW crosses its SMA150 costs about twice the drop. Worst falls: −38% (Feb–Mar 2020), −32% (Jul–Aug 2024), −31% (Jun–Jul 2026), and −66% in 2007–08 before the signal turned off.
- **Bet on big tech:** ROM's index is dominated by a few giants (Apple, Microsoft, Nvidia and their peers). The last 10 years were tech's decade; in 2008–2016 the strategy made 15% a year, less than QLD + Trend + bear-dip.
- **Same family as the QLD strategies:** with QLD + Trend + bear-dip and QLD regime it moves closely (weekly correlation about 0.8–0.9). Treat it as a better home for part of the QLD money, not as extra diversification.
- **Liquidity:** ROM trades about $5M a day; keep lots modest and use the limit offset.
- **Webull:** ROM needs the Leveraged & Inverse ETF permission (index ETF, not single stock: the 50M THB rule does not apply). Run **Go-live → Test trade** on ROM before giving it real money.

## Check it on TradingView

IYW daily: **Moving Average** 150 and 10, **Relative Strength Index** length 2. ROM: AMEX:ROM.
