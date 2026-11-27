<!--{"title": "AIBU · Breakout + calm + fast stop + dips (S2++)", "group": "The strategies"}-->
# AIBU · Breakout + calm + fast stop + dips (S2++)

This strategy trades **AIBU (Direxion Daily AI and Big Data Bull 2X)**, a 2x ETF on about 30–40 US companies in artificial intelligence and big data. It reads its trend from **AIBU's own price**, its dips from **QQQ**, and its credit check from **LQD ÷ IEF**.

It is **Strategy 2++** of the AIBU research (27 Nov 2026), after four rounds. You chose it over the half S1++ / half S2++ mix: it has the best 1–3 year results and the smallest recent falls.

| | Rule |
|---|---|
| **Trend** | **On** when AIBU closes above its **previous 30-day high**; **off** when it closes below its **previous 20-day low**. Held only while AIBU is **calm** (20-day volatility at or below its 80th percentile of 252 days) **and** credit is healthy (**LQD ÷ IEF** above its 100-day average) |
| **Size** | **60% ÷ AIBU's 20-day volatility**, at most 100%. At 60% volatility a year it holds 100%; at 100% it holds 60% |
| **Fast stop** | When AIBU falls **more than 13% in 5 days**, the trend part goes to cash for **7 trading days** (dip buys are still allowed) |
| **Dips** | After **QQQ's 2-day RSI** closes **below 6**: **100%** for one day (bought at the next open, sold at the following open unless the next close is another dip day) |
| **Otherwise** | Cash |

- **RSI2** is Wilder's 2-day RSI of QQQ's closes.
- **Volatility** is the standard deviation of AIBU's daily log changes over 20 days, × √252.
- **Prices for the signals:** AIBU's own prices for the trend, calm and stop. QQQ, LQD and IEF have dividends added back.
- **Idle cash stays cash.** The research earned T-bill interest on idle cash, assuming 0.02% per switch. At Webull's fee, buying and selling a T-bill ETF lowered every period (10 years 49.6% a year instead of 51.1%), so it is off.
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 20-point drift, so the volatility sizing doesn't trade every day.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of AIBU** first (Go-live checklist). The test trade also confirms that Webull Thailand lets you buy AIBU.

## Backtest results

These are from the bot's own code for this strategy (type `breakout_calm_dip`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing.

**AIBU listed on 15 May 2024.** Before then the backtest uses a **model of AIBU**: 2.26 × the daily move of a 70% IYW + 30% FDN mix, minus 4% a year for the fund's fee and the cost of its leverage. This is the research's fit, which moved 0.97 with the real fund. IYW alone is used before FDN listed in 2006. **The signals before May 2024 use the model too**, because the trend is read from AIBU itself.

| Period | **S2++ (this strategy)** | Without the fast stop (S2+) | AIBU held* | QQQ held |
|---|---|---|---|---|
| 1 year | **+69.5% / −17.3%** | the same | −14.6% / −46.4% | +4.6% / −19.9% |
| 3 years | **+110.9% / −17.3%** | the same | +37.0% / −51.2% | +18.4% / −22.8% |
| 5 years | **+69.2% / −25.3%** | +65.1% / −25.3% | +9.7% / −76.3% | +10.8% / −35.1% |
| 10 years | **+51.1% / −25.3%** | +47.2% / −25.3% | +31.3% / −77.3% | +19.0% / −35.1% |
| Real AIBU only (May 2024 –) | **+120.7% / −17.3%** | | | |
| Since Dec 2002 | **+31.0% / −34.1%** | | +21.4% / −88.2% | +15.2% / −53.4% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. *AIBU held uses the model before May 2024.

- **Research comparison (without T-bills):**

  | Period | Research | Bot |
  |---|---|---|
  | 10 years | 52.6% / −25% | 51.1% / −25.3% |
  | 2007–2016 | 23.6% / −34.1% | 21.9% / −34.1% |
  | 2003–2007 | 13.7% / −22.1% | 10.0% / −22.2% |
  | Real AIBU only (S2+) | 122.6% / −17.4% | 120.7% / −17.3% |

  S2+ (without the stop) over 10 years: research 48.7% / −25.4%, bot 47.2% / −25.3%.
- **The 2000–02 dot-com crash isn't in the bot's backtest** (its credit data starts in late 2002). The research rebuilt it: S2++ made 43.3% a year there, but with a **−50.4%** worst fall. That's the fall to plan for.
- **Worst falls:**
  - Over 10 years: 19–27 Feb 2020 (the COVID crash, before the stop could act), back by Jul 2020.
  - Since 2002: Jun → Oct 2008.
- **Activity:** about 27 trades a year, 64% of round trips won. It held AIBU on 49% of days.
- **Where the return comes from (10 years):**
  - Almost all of it came from the trend part.
  - The one-day dips added about 2.6×. They also carry the 2025 result, which includes the April 2025 rebound.
- **The fast stop** added 4 points a year over 10 years. It doesn't change the 1–3 year results, because the trend part was out anyway when it fired.

### Stress tests (10 years, a year / worst fall)

| Test | **Bot** | Research |
|---|---|---|
| Normal (fee 0.11% a side) | **51.1% / −25.3%** | 52.6% / −25% (no T-bills) |
| Fee 0.25% a side | 46.9% / −26.2% | 49.7% / −26% (with T-bills) |
| Every order a day late | 18.8% / −37.6% | 17.8% / −37% (S2+ with T-bills) |
| Every order a day late, last year only | **−3.5%** / −32.1% | |

**Orders at the open are essential.** A day late, the last year lost money instead of making 69%.

### Year by year

| Year | **S2++** | AIBU held* | QQQ held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+64.0%** | −10.1% | +3.6% |
| 2025 | **+224%** | +42.3% | +20.8% |
| 2024 | 52.3% | **+73.8%** | +25.6% |
| 2023 | +32.6% | **+168%** | +54.9% |
| 2022 | **+25.6%** | −73.3% | −32.6% |
| 2021 | +21.2% | **+53.0%** | +27.4% |
| 2020 | +82.7% | **+91.7%** | +48.4% |
| 2019 | +42.0% | **+89.5%** | +39.0% |
| 2018 | **+3.6%** | −9.2% | −0.1% |
| 2017 | +42.3% | **+91.8%** | +32.7% |
| 2016 | −9.7% | **+18.3%** | +7.1% |
| 2015 | −5.1% | **+11.1%** | +9.4% |
| 2014 | +13.9% | **+25.5%** | +19.2% |
| 2013 | +17.8% | **+82.6%** | +36.6% |
| 2012 | +25.1% | **+25.5%** | +18.1% |
| 2011 | **+7.4%** | −15.9% | +3.5% |
| 2010 | +11.8% | **+35.0%** | +20.1% |
| 2009 | +90.5% | **+181%** | +54.7% |
| 2008 | **+66.8%** | −78.5% | −41.7% |
| 2007 | +5.8% | **+23.3%** | +19.0% |
| 2006 | +4.3% | **+11.2%** | +7.1% |
| 2005 | −9.7% | −0.2% | **+1.6%** |
| 2004 | **+41.0%** | −6.2% | +10.5% |
| 2003 | +33.2% | **+113%** | +49.7% |

It trails AIBU in most strong years and makes its money in crashes and rebounds (2008, 2022, 2025).

## What to expect

- **Plan far lower than the 10-year backtest.** The 10 years are mostly a model of AIBU, in a decade when big tech led. The expected return below uses the **since-2002 figure** (31.0% a year) with the **research's 2000–02 crash fall (−50.4%)**.
- **It overlaps QLD, ROM, USD and MAGX.** AIBU holds big US tech, so *What your money is in* counts it in **US tech**.
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - AIBU 44.37 is far under its 30-day high (68.24), so the breakout is off.
  - It is not calm (volatility 113% a year, calm line 66%).
  - Credit is weak (LQD ÷ IEF 0.8% under its average).
  - The fast stop is on (AIBU −11.6% in 5 days; it fired on 20 Nov), with 3 more days to run.
  - QQQ's RSI2 is 39.6, so there's no dip. The last dip trades were 2–3 Nov and 20–23 Nov 2026.

## Expected return

<!--expected:aibu_s2pp-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- **AIBU is the thinnest fund in the bot:** about $0.37 million a day traded over the last 60 days (median $0.27 million), at $44.37 a share on 25 Nov 2026. Even a few thousand dollars may be a large part of the day's trading at the open. Keep the money in it small, and check every early fill against the open price.
- **Size it together with the Nasdaq, tech and chip strategies.** It adds to the same bet on big US tech.

*A backtest is a history, not a promise. This is not financial advice.*
