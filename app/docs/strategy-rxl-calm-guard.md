<!--{"title": "RXL · Calm guard + dips", "group": "The strategies"}-->
# RXL · Calm guard + dips

Holds **RXL (ProShares Ultra Health Care, 2x US health care)** while **XLV** (the 1x health care ETF) is calm and its volatility is below a fixed cap; when that guard is off it buys short **dips** of RXL; otherwise cash. It is the rule of the research *DDM · RXL · SSO: 1x signals and a better rule* (10 Nov 2026), the same settings as for SSO but without the uptrend clause (on health care it hurt: 16.2% a year with it). Health care moves little with US tech, so it spreads the bot's risk.

Added on 10 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from XLV's and RXL's daily bars:

| State | Rule | Holds |
|---|---|---|
| **In · guard on** | XLV calm **and** XLV volatility under 25% a year | 99% RXL |
| **In · dip** | guard off and a dip trade is open (see below) | 99% RXL |
| **Out · dips allowed** | guard off, no dip yet | cash |
| **Out · too jumpy** | guard off and XLV volatility at 40% a year or more | cash |

- **Volatility** = standard deviation of XLV's daily log changes over **20 days** (× √252 for "a year").
- **Calm** = that volatility is at or below its **80th percentile** of the last **252 days**.
- **Cap:** the guard is never on while the volatility is **25% a year or more** (stops a long bear market from looking calm).
- **Dip:** with the guard off, a dip trade opens when RXL's **IBS** = (close − low) ÷ (high − low) is **below 0.15** while XLV's volatility is under **40% a year**. It closes on the **first close above the previous day's high** or after **5 days**. A guard day takes over from a dip.

## What it holds

RXL or cash, about 86% of the days in RXL. Nothing else (options in Parameters: *When out, hold*, *Gold share when out*).

## When it trades

Decided after each US close; orders start at the **next market open**, 10 lots 5 minutes apart. About **9 round trips a year**.

It needs the next-open orders. Stress (10 years, research): fee 0.25% per side → 17.5% a year (20.8% at the real 0.11%), fills **one day late → 14.4%**, below holding RXL (17.6%).

## Backtest results

The bot's own code for this strategy (type `calm_guard`) on TradingView prices to 6 Nov 2026 (no dividends), decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell), cash earning nothing. The research engine gave the same position on every day since RXL started (Feb 2007, 4,953 days); an independent plain-loop recompute matched too. The **Backtest** tab shows the server's numbers on Yahoo prices.

| Period | A year | Worst fall | Sharpe | RXL held |
|---|---|---|---|---|
| 1 year | +34.1% | −21.4% | 1.15 | +50.6% / −21.6% |
| 3 years | +14.3% | −35.1% | 0.63 | +19.8% / −37.0% |
| 5 years | +6.0% | −35.1% | 0.35 | +6.1% / −37.0% |
| 10 years | **+20.1%** | **−35.1%** | 0.81 | +17.0% / −51.0% |
| Since 2008 | **+19.8%** | **−53.1%** | 0.77 | +15.9% / −67.4% |

### Year by year

| Year | This strategy | RXL held |
|---|---|---|
| 2026 (to 6 Nov) | +20.1% | +34.7% |
| 2025 | +24.2% | +17.8% |
| 2024 | −10.0% | −3.7% |
| 2023 | −4.4% | −3.3% |
| 2022 | **+0.5%** | −15.5% |
| 2021 | +36.4% | +47.9% |
| 2020 | **+39.7%** | +18.9% |
| 2019 | +38.9% | +40.0% |
| 2018 | +13.6% | +3.0% |
| 2017 | +46.3% | +46.7% |
| 2016 | +5.4% | −8.9% |
| 2015 | +15.3% | +6.5% |
| 2014 | +35.0% | +52.8% |
| 2013 | +71.6% | +93.5% |
| 2012 | +37.3% | +37.7% |
| 2011 | +40.4% | +17.1% |
| 2010 | −6.7% | +4.1% |
| 2009 | +41.8% | +37.1% |
| 2008 | **−27.5%** | −48.3% |

### Market falls

| Fall | This strategy | RXL held |
|---|---|---|
| 2008 crash (Oct 2007 – Mar 2009) | −53.5% | −67.7% |
| Q4 2018 | −27.3% | −29.5% |
| COVID crash (Feb – Mar 2020) | **−1.9%** | −50.5% |
| 2022 bear market | −12.7% | −29.2% |
| 2025 tariff crash | −20.8% | −18.4% |

Health care falls are often slow (2024, 2025 tariffs); the guard reacts to jumpy markets, so a slow slide is held most of the way.

## Research checks (10 Nov 2026)

- **Compared with the earlier pick** (RXL held while XLV calm, no cap, no dips): 10 years 20.8% vs 20.7% a year, worst fall −35.4% vs −40.5%; 3 years 14.5% vs 6.0%; 5 years 6.3% vs 1.0%. A modest upgrade.
- **Nearby settings** (calm percentile 75–85 × cap 20–30% × IBS 0.10–0.20 × dip cap 30–50%): median 20.9% a year / −35.4%; 100% beat holding RXL over 10 years, 87% since 2007.
- **Out of sample** (settings chosen on 2007–16, scored on 2016–26): median Sharpe 0.85 vs the calm-only family 0.81 and RXL held 0.65.
- **2,000 simulated decades:** median 19.6% a year (RXL held 16.3%, calm only 17.6%); a fall worse than −60% in 10.8% of them.
- **Without the dips:** 20.9% / −40.5% (the dips cut the worst fall).

## Expected return

<!--expected:rxl_calm_guard-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Timing-sensitive.** Fills a day late cut the 10-year return to 14.4% a year. Keep the next-open start.
- **Lags strong rallies after a jumpy patch:** the last year +34% vs RXL +51%; 2013 +72% vs +94%.
- **Slow slides are held.** The 2025 tariff fall was slightly worse than holding RXL.
- **RXL is thin** (a few $M a day): use the limit offset and modest lots.
- **Webull:** RXL is new to the bot; run its Test trade before giving it money.
- Plan on less than the backtest: the rule was found after looking at this history (the nearby-settings median is the fairer guide).

## Check it on TradingView

XLV daily: **Historical Volatility** length 20. TradingView's HV counts 365 days a year, so it reads about 1.17× the bot's figure: the 25% cap is about **29** there and the 40% dip cap about **47**. *Calm* compares today's value with the last 252, so the scale does not matter for it. RXL daily: IBS = (close − low) / (high − low). AMEX:XLV, AMEX:RXL.
