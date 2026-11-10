<!--{"title": "SSO · Calm guard + dips", "group": "The strategies"}-->
# SSO · Calm guard + dips

Holds **SSO (ProShares Ultra S&P 500, 2x the S&P 500)** while **SPY** (the 1x S&P 500 ETF) is calm or in an uptrend and its volatility is below a fixed cap; when that guard is off it buys short **dips** of SSO; otherwise cash. It is the rule of the research *DDM · RXL · SSO: 1x signals and a better rule* (10 Nov 2026), the same rule and settings as DDM · Calm guard + dips. The signals are read from the 1x ETF: SPY has the real volume and a longer history, and a 2x ETF's price drifts down in choppy markets, which makes averages on it say "down" too often.

Added on 10 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## How it decides

After each US close, from SPY's and SSO's daily bars:

| State | Rule | Holds |
|---|---|---|
| **In · guard on** | (SPY calm **or** SPY above its SMA100) **and** SPY volatility under 25% a year | 99% SSO |
| **In · dip** | guard off and a dip trade is open (see below) | 99% SSO |
| **Out · dips allowed** | guard off, no dip yet | cash |
| **Out · too jumpy** | guard off and SPY volatility at 40% a year or more | cash |

- **Volatility** = standard deviation of SPY's daily log changes over **20 days** (× √252 for "a year").
- **Calm** = that volatility is at or below its **80th percentile** of the last **252 days** (SPY's usual range for the past year).
- **Cap:** the guard is never on while the volatility is **25% a year or more**. In a long bear market (2008) the percentile adapts and calls a jumpy market "calm"; the fixed cap stops that.
- **Dip:** with the guard off, a dip trade opens when SSO's **IBS** = (close − low) ÷ (high − low) is **below 0.15** (it closed near its low) while SPY's volatility is under **40% a year**. It closes on the **first close above the previous day's high** or after **5 days**. A guard day takes over from a dip (still held).

## What it holds

SSO or cash, about 88% of the days in SSO. Nothing else (options in Parameters: *When out, hold*, *Gold share when out*).

## When it trades

Decided after each US close; orders start at the **next market open**, 10 lots 5 minutes apart. About **5–6 round trips a year**.

Stress (10 years, research): fee 0.25% per side → 27.0% a year (28.8% at the real 0.11%), fills one day late → 27.9%. It is not fragile to fees or timing.

## Backtest results

The bot's own code for this strategy (type `calm_guard`) on TradingView prices to 6 Nov 2026 (no dividends), decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell), cash earning nothing. The research engine gave the same position on every day since 2007 (5,126 days); an independent plain-loop recompute matched too. The **Backtest** tab shows the server's numbers on Yahoo prices.

| Period | A year | Worst fall | Sharpe | SSO held |
|---|---|---|---|---|
| 1 year | +4.3% | −18.2% | 0.29 | +13.2% / −18.3% |
| 3 years | +28.0% | **−21.8%** | 1.06 | +32.4% / −35.3% |
| 5 years | **+16.5%** | −37.1% | 0.67 | +12.4% / −46.8% |
| 10 years | **+28.0%** | **−37.1%** | 1.04 | +22.3% / −59.3% |
| Since 2008 | **+22.6%** | **−44.1%** | 0.85 | +14.4% / −82.1% |

### Year by year

| Year | This strategy | SSO held |
|---|---|---|
| 2026 (to 6 Nov) | +1.5% | +10.2% |
| 2025 | +25.9% | +25.2% |
| 2024 | +39.0% | +42.2% |
| 2023 | +45.9% | +46.4% |
| 2022 | **−19.5%** | −39.3% |
| 2021 | +59.8% | +60.2% |
| 2020 | **+51.9%** | +21.1% |
| 2019 | +52.3% | +62.5% |
| 2018 | −4.1% | −15.2% |
| 2017 | +43.4% | +43.7% |
| 2016 | +44.0% | +20.9% |
| 2015 | −0.5% | −1.8% |
| 2014 | +14.7% | +25.1% |
| 2013 | +66.2% | +69.9% |
| 2012 | +29.8% | +30.1% |
| 2011 | −9.9% | −3.5% |
| 2010 | +28.3% | +25.7% |
| 2009 | +33.7% | +45.6% |
| 2008 | **−22.5%** | −68.3% |

It keeps most of SSO's bull-market years (it is in SSO most days) and cuts the bear markets: 2008, 2018, 2022. It lags after a sharp fall and quick rebound (2026: out in the spring dip, back in late).

### Market falls

| Fall | This strategy | SSO held |
|---|---|---|
| 2008 crash (Oct 2007 – Mar 2009) | −49.1% | −85.5% |
| Q4 2018 | −20.5% | −36.6% |
| COVID crash (Feb – Mar 2020) | −16.9% | −59.3% |
| 2022 bear market | −36.5% | −46.8% |
| 2025 tariff crash | −19.7% | −35.3% |

## Research checks (10 Nov 2026)

- **Compared with the earlier pick** (SSO held while SPY calm or above SMA100, no cap, no dips): 10 years 28.8% vs 26.8% a year; since 2007 21.3% / −49.5% vs 17.0% / −71.8%. The cap fixed 2008; the dips add a few points.
- **Nearby settings** (calm percentile 75–85 × cap 20–30% × IBS 0.10–0.20 × dip cap 30–50% × SMA 50–150): median 23.8% a year / −38.9%; 78% beat holding SSO over 10 years, 100% since 2007.
- **Out of sample** (settings chosen on 2007–16, scored on 2016–26): median Sharpe 0.82 vs SSO held 0.75.
- **2,000 simulated decades:** median 22.4% a year (SSO held 15.0%); a fall worse than −60% in 6.1% of them (SSO held 51%).
- **Without the dips:** 25.0% / −34.4%. **Without the cap:** the 2008 fall goes back to about −71%.

## Expected return

<!--expected:sso_calm_guard-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Risks and what to expect

- **Lags sharp V-shaped rebounds.** After a fast fall it waits for calm or the SMA100; the last 1 year was +4% while SSO made +13%.
- **Still a 2x ETF most of the time.** Falls of −35% to −50% happened (2008, 2022). It cuts crashes, it does not avoid them.
- **Same market as the Nasdaq strategies, in part.** The S&P 500 is about a third US tech; the Money page counts SSO as S&P 500, not US tech.
- **Webull:** SSO is new to the bot; run its Test trade before giving it money.
- Plan on less than the backtest: the rule was found after looking at this history (the nearby-settings median is the fairer guide).

## Check it on TradingView

SPY daily: **Moving Average** 100; **Historical Volatility** length 20. TradingView's HV counts 365 days a year, so it reads about 1.17× the bot's figure: the 25% cap is about **29** there and the 40% dip cap about **47**. *Calm* compares today's value with the last 252, so the scale does not matter for it. SSO daily: IBS = (close − low) / (high − low). AMEX:SPY, AMEX:SSO.
