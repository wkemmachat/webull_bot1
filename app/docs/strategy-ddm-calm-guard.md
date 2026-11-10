<!--{"title": "DDM · Calm guard + dips", "group": "The strategies"}-->
# DDM · Calm guard + dips

Holds **DDM (ProShares Ultra Dow30, 2x the Dow Jones)** while **DIA** (the 1x Dow ETF) is calm or in an uptrend and its volatility is below a fixed cap; when that guard is off it buys short **dips** of DDM; otherwise cash. It is the rule of the research *DDM · RXL · SSO: 1x signals and a better rule* (10 Nov 2026), the same rule and settings as SSO · Calm guard + dips. The signals are read from DIA: it has the real volume and a longer history, and a 2x ETF's price drifts down in choppy markets, which makes averages on it say "down" too often. It is the bot's first strategy on the Dow, a market that moves less with US tech.

Added on 10 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from DIA's and DDM's daily bars:

| State | Rule | Holds |
|---|---|---|
| **In · guard on** | (DIA calm **or** DIA above its SMA100) **and** DIA volatility under 25% a year | 99% DDM |
| **In · dip** | guard off and a dip trade is open (see below) | 99% DDM |
| **Out · dips allowed** | guard off, no dip yet | cash |
| **Out · too jumpy** | guard off and DIA volatility at 40% a year or more | cash |

- **Volatility** = standard deviation of DIA's daily log changes over **20 days** (× √252 for "a year").
- **Calm** = that volatility is at or below its **80th percentile** of the last **252 days**.
- **Cap:** the guard is never on while the volatility is **25% a year or more**. In a long bear market (2008) the percentile adapts and calls a jumpy market "calm"; the fixed cap stops that.
- **Dip:** with the guard off, a dip trade opens when DDM's **IBS** = (close − low) ÷ (high − low) is **below 0.15** while DIA's volatility is under **40% a year**. It closes on the **first close above the previous day's high** or after **5 days**. A guard day takes over from a dip (still held).

## What it holds

DDM or cash, about 89% of the days in DDM. Nothing else (options in Parameters: *When out, hold*, *Gold share when out*).

## When it trades

Decided after each US close; orders start at the **next market open**, 10 lots 5 minutes apart. About **5 round trips a year**.

Stress (10 years, research): fee 0.25% per side → 24.4% a year (26.1% at the real 0.11%), fills one day late → 23.5%. It is not fragile to fees or timing.

## Backtest results

The bot's own code for this strategy (type `calm_guard`) on TradingView prices to 6 Nov 2026 (no dividends), decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell), cash earning nothing. The research engine gave the same position on every day since 2007 (5,126 days); an independent plain-loop recompute matched too. The **Backtest** tab shows the server's numbers on Yahoo prices.

| Period | A year | Worst fall | Sharpe | DDM held |
|---|---|---|---|---|
| 1 year | +5.3% | −19.4% | 0.33 | +12.6% / −19.6% |
| 3 years | +21.7% | **−19.8%** | 0.91 | +23.6% / −31.9% |
| 5 years | **+10.9%** | −32.8% | 0.52 | +8.9% / −40.5% |
| 10 years | **+25.3%** | **−32.8%** | 0.99 | +18.0% / −63.1% |
| Since 2008 | **+20.8%** | **−37.4%** | 0.83 | +12.3% / −78.8% |

### Year by year

| Year | This strategy | DDM held |
|---|---|---|
| 2026 (to 6 Nov) | +1.3% | +8.3% |
| 2025 | +26.5% | +19.3% |
| 2024 | +16.3% | +20.3% |
| 2023 | +23.8% | +24.0% |
| 2022 | **−2.4%** | −20.2% |
| 2021 | +32.5% | +41.7% |
| 2020 | **+78.1%** | +1.6% |
| 2019 | +44.1% | +47.0% |
| 2018 | −16.3% | −14.1% |
| 2017 | +57.8% | +58.2% |
| 2016 | +44.8% | +29.9% |
| 2015 | −0.2% | −4.5% |
| 2014 | +8.5% | +17.0% |
| 2013 | +61.4% | +63.9% |
| 2012 | +17.1% | +17.3% |
| 2011 | −5.7% | +9.8% |
| 2010 | +30.0% | +24.4% |
| 2009 | +30.9% | +37.2% |
| 2008 | **−11.3%** | −62.5% |

It keeps most of DDM's bull-market years and cuts the bear markets (2008, 2020, 2022). It lags after a sharp fall and quick rebound (2026: out in the spring dip, back in late; 2011).

### Market falls

| Fall | This strategy | DDM held |
|---|---|---|
| 2008 crash (Oct 2007 – Mar 2009) | −46.0% | −82.2% |
| Q4 2018 | −30.2% | −34.0% |
| COVID crash (Feb – Mar 2020) | −17.1% | −62.7% |
| 2022 bear market | −23.3% | −37.9% |
| 2025 tariff crash | −18.6% | −29.8% |

## Research checks (10 Nov 2026)

- **Compared with the first pick** (gated IBS dip: DDM IBS dips only while the IBD distribution-day rule on DIA is in or DDM is above SMA200): 10 years 26.1% vs 16.3% a year, worst fall −33.0% vs −27.9%; since 2007 19.4% / −46.6% vs 12.5% / −37.0%. More return, somewhat deeper falls, and far less sensitive to fees and timing (the gated IBS dip fell to about 9% a year with fills a day late). It replaced the gated IBS dip on 10 Nov 2026 before either traded.
- **Nearby settings** (calm percentile 75–85 × cap 20–30% × IBS 0.10–0.20 × dip cap 30–50% × SMA 50–150): median 21.6% a year / −36.5%; 98% beat holding DDM over 10 years, 100% since 2007.
- **Out of sample** (settings chosen on 2007–16, scored on 2016–26): median Sharpe 0.81 vs DDM held 0.66.
- **2,000 simulated decades:** median 19.9% a year (DDM held 13.2%); a fall worse than −60% in 6.1% of them (DDM held 49%).
- **Without the dips:** 21.2% / −26.7% (smaller falls, less return). **Without the cap:** the 2008 fall goes back to about −71%.

## Expected return

<!--expected:ddm_calm_guard-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Lags sharp V-shaped rebounds.** After a fast fall it waits for calm or the SMA100; the last 1 year was +5% while DDM made +13%.
- **Still a 2x ETF most of the time.** Falls of −30% to −46% happened (2008, 2018, 2022). It cuts crashes, it does not avoid them.
- **DDM is thin** (a few $M a day): use the limit offset and modest lots.
- **Webull:** DDM is new to the bot; run its Test trade before giving it money.
- Plan on less than the backtest: the rule was found after looking at this history (the nearby-settings median is the fairer guide).

## Check it on TradingView

DIA daily: **Moving Average** 100; **Historical Volatility** length 20. TradingView's HV counts 365 days a year, so it reads about 1.17× the bot's figure: the 25% cap is about **29** there and the 40% dip cap about **47**. *Calm* compares today's value with the last 252, so the scale does not matter for it. DDM daily: IBS = (close − low) / (high − low). AMEX:DIA, AMEX:DDM.
