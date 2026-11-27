<!--{"title": "CWEB · Trend + Hang Seng crash buys", "group": "The strategies"}-->
# CWEB · Trend + Hang Seng crash buys

This strategy trades **CWEB (Direxion Daily CSI China Internet Bull 2X)**, a 2x ETF on Chinese internet companies (Alibaba, Tencent, PDD, Meituan and others). It is the bot's first strategy outside US markets, so it does not move with your US tech strategies.

It combines three parts and holds whichever one is **largest** at the time; otherwise it holds cash.

1. A **trend** part: hold CWEB while KWEB breaks out and FXI is above its 200-day average, with a trailing stop.
2. A **big-crash** buy: after the Hang Seng closes 3% or more down, buy 100% CWEB at that day's US open.
3. A **small-crash** buy: after a Hang Seng drop of 1.75% to 3%, a limit buy for 40% at 1% under CWEB's previous close, for that day only.

This is **Pick 4+** of the research *CWEB (2x China internet): best buy/sell rules* (26 Nov 2026): Pick 4 plus a 15% trailing stop on the trend part. You chose it over Pick 4 after comparing their falls: about the same return, with shallower falls in most years.

Added on 26 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money. **Before any Live money, run a Webull test trade of CWEB** (Go-live → test trade).

## Why CWEB needs different rules

- Holding CWEB lost 93% over 10 years (worst fall −98.7%), 69% in the last year and 92% over 5 years.
- Over those 10 years CWEB's **gains came while US markets were closed** (Hong Kong hours) and its **losses came during US hours**. A dip bought after the US close arrives after the bounce has already happened.
- The Hang Seng closes at **15:00 Bangkok**, six and a half hours before the US open. Its close is known before CWEB trades, so the bot can buy at the open, before the bounce.

## How it decides

| State | Rule | Holds |
|---|---|---|
| **In · Hang Seng crash** | The Hang Seng closed **3% or more down** today | **100% CWEB** from the US open the same day |
| **In · small crash (1 day)** | The Hang Seng closed **1.75% to 3% down** today | A day limit buy for **40%** at 1% under CWEB's previous close; a fill is sold at the next open |
| **In · trend** | **KWEB** has broken out **and** **FXI** closes above its 200-day average | CWEB at **30% ÷ CWEB's 20-day volatility** (at most 100%) |
| **Out · trailing stop** | Trend on, but CWEB closed 15% under the run's highest close | Cash (crash buys still count) |
| **Out** | No trend, no crash | Cash |

When parts overlap, the largest wins. A 100% crash buy while the trend part holds 35% means 100%. A small-crash buy while the trend part already holds 60% adds nothing.

- **Breakout (KWEB, daily)**: turns **on** at a close above the highest high of the previous 20 days. It turns **off** at a close below the lowest low of the previous 15 days. In between nothing changes. TradingView: *Donchian Channels* length 20 for the entry, 15 for the exit.
- **Gate (FXI)**: FXI's close above its 200-day simple average.
- **Size**: 30% ÷ CWEB's 20-day volatility a year (the standard deviation of its last 20 daily % changes × √252), at most 100%.
  - CWEB is usually 50–70% volatile, so the trend part is usually 40–60%.
  - It is resized only when the size moves 20 points or more.
- **Trailing stop** (trend part only): from the first day of a trend run, the bot tracks CWEB's highest close. A close 15% or more under it ends the trend part. The trend part comes back only after the trend signal turns off and then on again.
- **Dividends**: KWEB and FXI pay a dividend each December. The bot reads their prices **with dividends added back**, as the research did, so a dividend does not look like a fall. On plain prices the January 2026 breakout came 6 trading days later, and the last year's result fell from +5.2% to about 0%. To match the bot's numbers in TradingView, turn on *Adjust data for dividends*.

### Big-crash buy (Hang Seng −3% or worse)

1. **15:15 Bangkok** (after Hong Kong's closing auction): the bot reads the Hang Seng's close. If it is 3% or more under the previous close, the target becomes 100% CWEB and a plan is made for **that day's US open**.
2. **The next US open**: if CWEB **opens 4% or more above the buy** (the open of the crash day), the crash part is sold at once, about a minute after the open (the bot needs the first minute's price).
3. Otherwise the crash buy is held that day too and **sold at the open two trading days after the buy**.

A Hang Seng crash on a day the US market is closed does nothing (the backtest does the same).

### Small-crash buy (Hang Seng −1.75% to −3%)

- One **day limit order**: buy 40% of the strategy's money at **1% under CWEB's previous close**.
- The order is placed at the US open and **rests all day at that price**. It is not re-priced and not sent again. Two minutes before the close it is cancelled if it has not filled.
- If it fills, the buy is **sold at the next open**. The Orders page and Logs show *Day limit not filled* when it does not.
- In the backtest it fills when the day's low reaches the limit, at the limit (or at the open, if CWEB opens lower).

### Orders

- **Trend changes** are decided after the US close and traded at the next open.
- Plans use **5 lots, 1 minute apart**, from the open (the type's default; Execution can change it).
- Between signals the trend part is traded back to its size when it drifts **5 points** or more (the rebalance band). The research kept it at its size every day; 5 points gives the same result with fewer trades.
- **Timing matters a lot here.** If every order filled one day late, the backtest made 11.3% a year with a −62.8% fall. Keep *Entries start* on "as soon as the market is open".

## Backtest results

These are from the bot's own code for this strategy (type `hk_crash`) on Yahoo daily prices to 25 Nov 2026:

- Trend changes trade at the next open. Crash buys trade at the open of the Hang Seng's date. The take-profit trades at the next open. The small-crash limit fills when the day's low reaches it.
- Webull's real fee is paid (0.11% per buy and per sell). Cash earns nothing.
- **CWEB before 2 Jan 2018** is built from 2 × KWEB minus a 5.3% yearly drag, as in the research: CWEB traded too thinly before 2018 (often under 100 shares a day).
- The bot's numbers match the research within about a point a year.

| Period | **This strategy** | Pick 4 (no trailing stop) | Research Pick 4+ | CWEB held | KWEB held |
|---|---|---|---|---|---|
| 1 year | **+5.2% / −12.4%** | +5.2% / −12.4% | +5.4% / −12.4% | −69.1% / −73.1% | −40.5% / −45.0% |
| 3 years | **+24.1% / −15.1%** | +23.1% / −18.6% | +25.2% / −13.8% | −25.3% / −77.7% | −5.5% / −48.8% |
| 5 years | **+42.3% / −19.7%** | +40.8% / −19.7% | +43.2% / −19.7% | −38.8% / −91.8% | −11.1% / −56.6% |
| 10 years | **+40.5% / −24.7%** | +39.4% / −27.2% | +40.4% / −23.0% | −23.7% / −98.7% | −3.5% / −80.9% |
| Since Aug 2013 | **+37.7% / −31.1%** | +36.7% / −31.1% | — | −16.7% / −98.7% | +0.2% / −80.9% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. 10-year Sharpe: 1.17 (Pick 4: 1.13).

- About **43 trades a year** over 10 years (a crash round trip is 2 trades; the small-crash buys are most of them), 56% of round trips won, +2.0% on average each.
- It held CWEB on 35% of days, 22% of its money on average.
- In years when KWEB was below its 200-day average it made 52.5% a year (CWEB held: −26.3%); above it, 29.3% (CWEB held: −14.8%).

### Pick 4+ against Pick 4

The trailing stop changes only the trend part. Over 10 years:

- It makes 1.1 points a year more and the worst fall is 2.5 points smaller (−24.7% against −27.2%).
- A rebuild of the research (26 Nov 2026) found the strategy **15% or more below its high on 70 trading days**, against 227 for Pick 4.
- It was better in 2018, 2019, 2021, 2023 and 2024. It was worse in 2020 (+136% against +151%: the stop sold the trend part early in the year) and 2025 (+40.1% against +42.9%).
- **The level is sensitive.** In the research, at 16% the 10-year gain disappeared and at 20% the stop did nothing. The shallower falls held at 10–15%.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** |
|---|---|
| Normal (fee 0.11% a side) | **40.5% / −24.7%** |
| Fee 0.25% a side | 36.5% / −26.0% |
| Every order a day late | 11.3% / −62.8% |
| Pick 4 (no trailing stop) | 39.4% / −27.2% |

Fees cost little; **lateness costs almost everything**. The edge is buying at the open after Hong Kong's close and selling soon after. A day late, the bounce is gone.

### Year by year

| Year | **This strategy** | CWEB held | KWEB held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+5.2%** | −66.0% | −37.8% |
| 2025 | **+40.1%** | +29.0% | +23.5% |
| 2024 | **+26.7%** | +0.1% | +12.0% |
| 2023 | **+9.5%** | −32.9% | −9.1% |
| 2022 | **+166.3%** | −59.4% | −17.2% |
| 2021 | **+24.2%** | −79.4% | −49.0% |
| 2020 | **+136.3%** | +116.4% | +58.2% |
| 2019 | −0.3% | **+51.2%** | +29.9% |
| 2018 | **+16.9%** | −62.9% | −33.8% |
| 2017 | +63.5% | **+162.9%** | +69.7% |
| 2016 | **+45.4%** | −25.4% | −8.5% |
| 2015 | **+34.7%** | +20.8% | +18.4% |
| 2014 | **+0.4%** | −16.1% | −1.5% |
| 2013 (from Aug) | +15.2% | **+50.2%** | +25.3% |

It made money in 11 of the 12 full years (2014–2025). It lost a little in 2019 (−0.3%) and lagged CWEB in its strong up years (2017, 2019).

## What to expect

- **Plan on much less than the backtest: about 17–24% a year.**
  - 2020 and 2022 carry most of the 10-year profit.
  - In the research's walk-forward check, the rules were picked each New Year from the past only. That made about 37–39% a year from 2018. But that pool of rules was built knowing the earlier rounds' results, so the research advises planning on 17–24%.
  - The research found **no rule that beats this one in all five periods**. Each further round of searching added less.
- **The edge rests on a few trades.**
  - Pick 4's 10-year edge over Pick 3 came from two trades: 12 Mar 2020 and 7 Apr 2025.
  - Without the 3 best big-crash trades the research's Pick 4 still made 30.5% a year.
- **Spreads on crash days.** CWEB can open with a wide spread after a big Hang Seng fall. The crash buy goes in lots over the first minutes. Watch the first Live crash buy's fills against the open.
- **Risks outside the rules**: Chinese regulation, US–China tensions and delisting talk move these stocks overnight, and a 2x ETF can lose most of its value in a bad year (CWEB: −79% in 2021).
- **Now (after the 25 Nov 2026 close) it is out, in cash.**
  - KWEB's breakout is off (21.17 against a 20-day high of 25.15).
  - FXI is 10.5% under its 200-day average (31.30 against 34.99).
  - The last big-crash buy was on 22 Oct 2026 (Hang Seng −3.03%). The last small-crash buy filled on 20 Nov 2026.

## Expected return

<!--expected:cweb_trend_crash-->

Like every strategy, the figure is the bot's own 10-year backtest (Oct 2016 – Oct 2026) minus the planning haircut. For this strategy the research advises **17–24% a year**, less than the haircut leaves, so treat the Dashboard's figure as the top of the range. How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- It spreads your risk away from US tech. *What your money is in* shows it in the **China** group, together with CHAU · Half trend + half dip (S4) (China A-shares, added 27 Nov 2026).
- It sits in cash about two thirds of the time. Money given to it waits in cash between signals.
- **Start small.** The rules depend on prompt orders at the open, and the first Live crash buy is the real test of the fills.

*A backtest is a history, not a promise. This is not financial advice.*
