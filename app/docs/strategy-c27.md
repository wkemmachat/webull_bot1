<!--{"title": "C2-7 Momentum (1x and 2x)", "group": "The strategies"}-->
# C2-7 Momentum (1x and 2x)

Holds the **7 strongest of the 12 largest Nasdaq-100 companies** — equal money each — but only while the QQQ signal is on; gold and
T-bills when it is off. **C2-7 Momentum 1x** holds the shares; **C2-7 Momentum 2x** holds each one through its 2x single-stock ETF
(NVDL for Nvidia, AAPU for Apple, …) when one exists.

## How it decides

**Every day after the US close — the on/off signal from QQQ:**

| Part | Rule |
|---|---|
| Trend | **Supertrend(ATR 14, ×4) up AND QQQ close above its SMA200** |
| Dip trade | opens when **RSI(2) < 5**, ends on the first close above **SMA5** |
| Signal | **on** if trend or dip trade, else **off** |

**Every Friday after the close — the list:** rank the Nasdaq-100 by market cap (close × shares outstanding). Of the **12 largest**,
the **7 with the best 6-month (126 trading days) return** are the list for the next week. A new company needs 6 months of prices
before it can be picked.

**Next open — the trades:**

| Situation | What the bot does |
|---|---|
| Signal turns **off** | sell all stocks; **50% GLD (gold) + 50% SGOV (T-bills)** |
| Signal turns **on** | sell the parking ETFs; buy the 7 names with 1/7 of the money each, largest first |
| On, and the **list changes** | sell names that left the list; buy new names with 1/7 of the money (limited to the cash); park what is left |
| On, list unchanged | nothing: winners are **never trimmed**, losers never topped up |

## What it holds

- **1x:** the shares themselves (e.g. NVDA, AAPL, MSFT, META, TSLA, MU, AMD in late October 2026).
- **2x:** each share's 2x ETF when one exists — NVDA→NVDL, AAPL→AAPU, GOOGL→GGLL, MSFT→MSFU, AMZN→AMZU, META→METU, AVGO→AVGX,
  TSLA→TSLL, MU→MUU, AMD→AMUU, NFLX→NFXL, PLTR→PLTU, ORCL→ORCX (editable in Parameters). Companies without one (ASML, Costco,
  Walmart, SpaceX …) are held 1x, so the real leverage is about 1.4–1.9x. If Webull refuses an ETF, the bot holds the share instead.
- **Off:** 50% GLD + 50% SGOV.

The strategy page shows this week's list: size rank, market cap, 6-month return, and (2x) the ETF used.

## When it trades

The signal is decided after each US close and the list after each Friday close; orders start at the **next market open**, 10 lots
5 minutes apart. The Nasdaq-100 ranking comes from the research file until 23 Oct 2026; from then on the bot ranks the members itself
every weekend (Yahoo market caps; Logs shows "Nasdaq-100 ranking updated"). The list often changes by one name, so it trades
much more often than the ETF strategies (see "trades a year" below).

## Backtest results

Numbers from the bot's own **Backtest** tab on 25 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, 0.05% cost per side. Open the strategy → **Backtest** for today's numbers, the chart and every trade. The ranking and stock prices for 2016–2026 are the research's own (Alpaca total-return prices, SEC share counts),
so this backtest uses the same data as the research; 2x uses the real 2x ETFs from 10 days after their launch (2022–2024) and,
before that, 2× each stock's daily move minus the T-bill rate + 6.9% a year (the ETFs' typical cost).

### C2-7 Momentum 1x

| Period | A year | Worst fall | Sharpe | QQQ held a year / worst fall |
|---|---|---|---|---|
| 1 year | **+49.2%** | −13.5% | 1.44 | +15.9% / −12.0% |
| 3 years | **+54.8%** | −15.4% | 1.70 | +26.3% / −22.8% |
| 5 years | **+46.7%** | −15.4% | 1.67 | +14.0% / −35.1% |
| 10 years | **+34.0%** | −19.5% | 1.39 | +20.5% / −35.1% |
| All (from 31 Oct 2016) | **+34.0%** | −19.5% | 1.39 | +20.5% / −35.1% |

- **Worst fall:** −19.5%, from 1 Sep 2020 to 30 Oct 2020; back at the old high on 7 Jan 2021.
- **$10,000 became** $186,127 (+1,761%) from 31 Oct 2016 to 23 Oct 2026.
- **In the market** 65% of the days · **29.6 trades a year** · 68% of round trips made money (average +5.7%).
- Volatility 21% a year.

### C2-7 Momentum 2x

| Period | A year | Worst fall | Sharpe | QQQ held a year / worst fall | QLD held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+99.6%** | −26.4% | 1.48 | +15.9% / −12.0% | +22.3% / −25.1% |
| 3 years | **+98.3%** | −30.0% | 1.59 | +26.3% / −22.8% | +44.0% / −42.3% |
| 5 years | **+80.0%** | −30.0% | 1.55 | +14.0% / −35.1% | +16.6% / −63.7% |
| 10 years | **+56.8%** | −33.0% | 1.32 | +20.5% / −35.1% | +32.6% / −63.7% |
| All (from 31 Oct 2016) | **+56.8%** | −33.0% | 1.32 | +20.5% / −35.1% | +32.6% / −63.7% |

- **Worst fall:** −33.0%, from 1 Sep 2020 to 30 Oct 2020; back at the old high on 7 Jan 2021.
- **$10,000 became** $887,011 (+8,770%) from 31 Oct 2016 to 23 Oct 2026.
- **In the market** 65% of the days · **29.6 trades a year** · 70% of round trips made money (average +10.0%).
- Volatility 38% a year.

### Year by year

**1x**

| Year | Strategy | QQQ held |
|---|---|---|
| 2026 (part) | **+49.1%** | +15.1% |
| 2025 | **+42.6%** | +20.8% |
| 2024 | **+59.6%** | +25.6% |
| 2023 | **+68.2%** | +54.9% |
| 2022 | **+12.6%** | −32.6% |
| 2021 | **+29.8%** | +27.4% |
| 2020 | **+69.7%** | +48.4% |
| 2019 | **+16.5%** | +39.0% |
| 2018 | **+4.9%** | −0.1% |
| 2017 | **+12.2%** | +32.7% |
| 2016 (part) | **−4.1%** | +1.6% |

**2x**

| Year | Strategy | QQQ held | QLD held |
|---|---|---|---|
| 2026 (part) | **+104.1%** | +15.1% | +22.5% |
| 2025 | **+64.7%** | +20.8% | +30.4% |
| 2024 | **+101.6%** | +25.6% | +42.8% |
| 2023 | **+116.4%** | +54.9% | +117.7% |
| 2022 | **+18.7%** | −32.6% | −60.5% |
| 2021 | **+40.1%** | +27.4% | +54.7% |
| 2020 | **+134.5%** | +48.4% | +88.9% |
| 2019 | **+24.0%** | +39.0% | +81.7% |
| 2018 | **+5.0%** | −0.1% | −8.3% |
| 2017 | **+25.3%** | +32.7% | +70.3% |
| 2016 (part) | **−4.9%** | +1.6% | +2.7% |

## The research

*Research on single Stock Nasdaq* (October 2026), chosen signal, 50/50 gold & T-bill parking:

| | 20 years (Dec 2006 – Oct 2026) | 2006–2016 (never used to choose the rules) | 2016–2026 | Last 5 years |
|---|---|---|---|---|
| **1x** | 27.4% a year, −19.7%, Sharpe 1.34 | 20.4%, −17.2% | 34.7%, −19.7%, Sharpe 1.50 | 46.9%, −15.6% |
| **2x** | 45.5%, −37.7%, Sharpe 1.17 (model) | 32.4%, −34.4% (model) | 59.6%, −37.7% (model) | 72.7%, −30.6% (real ETFs) |
| QLD + same QQQ signal | 33.4%, −36.4%, Sharpe 1.10 | 25.4%, −36.4% | 41.8%, −31.7% | 48.8%, −21.6% |
| QQQ held | 16.0%, −52.7% | 11.6%, −52.7% | 20.5%, −35.2% | 14.2%, −35.2% |

**Cross-check:** the bot's own backtest over the same 10 years (its code, the research's ranking and prices, Yahoo for QQQ, GLD and
the ETFs) gives **1x 34.0% a year, −19.5%, Sharpe 1.39** (research 34.7%, −19.7%, 1.50) and **2x 56.8%, −33.0%, Sharpe 1.32**
(research 59.6%, −37.7%, 1.31 — the research modelled 2x on every stock; the bot uses the real ETFs from 2022–2024). The small
differences come from the QQQ prices (Yahoo vs the research's dividend-adjusted series) and the 1% cash buffer.

- Over 45 signal settings, Momentum 2x beat "QLD + the same signal" in every window; the median worst fall of 2x was −39% to −42%,
  the worst setting −57% (2006–2016).
- 1x has the best risk-adjusted result (Sharpe 1.34); 2x adds about 18 points a year but doubles the falls and lowers the Sharpe.
- The 6-month lookback matters: 3 and 12 months were only as good as plain "7 largest".

## Risks and what to expect

- **Chosen on 2016–2026,** the best decade ever for mega-caps. The research's planning number for a normal decade is about **20% a
  year** (1x) with worst falls of −20% to −30%; for 2x roughly 30% a year and falls of −35% to −55%.
- **It can trail the index for years:** in 2017 and 2019 the 1x version made 12% and 17% while QQQ made 33% and 39%.
- **2x single-stock ETFs** are young (2022+), cost about 7% a year above T-bills, decay in choppy markets, can have wide spreads and
  can close. Overnight gaps are doubled (a −26% stock day is about −52% for its 2x ETF).
- **Webull Thailand** must allow each ETF: check NVDL, AAPU, MSFU … with Go-live → Test trade on your Live account first. Refused ETFs
  fall back to the share automatically.
- **Same signal family as QLD + Trend + bear-dip:** they go out together. Treat C2-7 as a candidate to replace a QLD strategy, not
  as diversification.
- **Whole shares:** with little money per name (e.g. $1,400 = 1/7 of $10,000), expensive shares (Costco, ASML) round down; give it
  at least $7,000–$10,000.
- The ranking needs Yahoo market caps every weekend; if it fails, the bot keeps last week's list and retries hourly.

## Check it on TradingView

QQQ daily: **Supertrend** (ATR length 14, factor 4), **Moving Average** 200 and 5, **Relative Strength Index** length 2. The
6-month return of a stock: its close today ÷ its close 126 trading days ago − 1 (use total-return prices for dividend payers).
