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

### Weekly 2x ETF search (2x only)

After each weekend's Nasdaq-100 ranking the bot looks for a 2x ETF for every stock among the 15 largest (the 12 it picks from,
plus the next 3, so a newcomer is seen a week early) that it would hold as shares. **It only suggests; it never adds one by itself.**

- **Where it looks:** Yahoo's search for the ticker with "daily", "2x", "bull" and "long". 2x single-stock funds are named like
  "GraniteShares 2x Long NVDA Daily ETF", "Direxion Daily TSLA Bull 2X Shares" or "Corgi AMD 2x Daily ETF". Short, inverse, 1.5x and
  3x funds, foreign listings and crypto wrappers are skipped.
- **What a suggestion must pass:**
  - it moves like 2x the stock: daily beta 1.7–2.3 and correlation of at least 0.90 over the last 60 trading days;
  - it has traded at least 63 days (about 3 months);
  - it trades at least $2 million a day (20-day average);
  - its spread is under 0.5%, when Yahoo shows one.
- **When one passes:** a LINE message (event *New 2x ETF found*), and the strategy page's **2x ETF search** card shows it with
  **Add** and **Dismiss**.
  - **Add** writes the pair into the strategy's "2x ETFs" setting. From then on, whenever that stock is on the weekly list the bot
    buys the ETF instead. If the stock is on this week's list, its shares switch to the ETF at the next plan.
  - **Dismiss** hides that ETF; a different one found later is suggested again.
- **After adding:** run **Go-live → Test trade** for the ETF on Live. Every ETF in the 2x list now appears there, not only this
  week's.
- **The card also lists every stock checked:** what it is held as, and why candidates failed (e.g. "too young").
  **Search now** runs the search at any time.
- **Before you add,** look up the ETF yourself: issuer, cost, and whether Webull Thailand offers it. The checks prove it behaves
  like 2x and trades enough. They don't prove it will last.

## When it trades

The signal is decided after each US close and the list after each Friday close; orders start at the **next market open**, 10 lots
5 minutes apart. The Nasdaq-100 ranking comes from the research file until 23 Oct 2026; from then on the bot ranks the members itself
every weekend (Yahoo market caps; Logs shows "Nasdaq-100 ranking updated"). The list often changes by one name, so it trades
much more often than the ETF strategies (see "trades a year" below).

## Backtest results

Numbers from the bot's own **Backtest** tab on 26 Oct 2026: the strategy's live code over real Yahoo prices (dividends included), traded at the bot's real times, paying Webull's real fee (0.11% of every buy and every sell; single-stock 2x ETFs 0.16%). Open the strategy → **Backtest** for today's numbers, the chart and every trade. The ranking and stock prices for 2016–2026 are the research's own (Alpaca total-return prices, SEC share counts),
so this backtest uses the same data as the research; 2x uses the real 2x ETFs from 10 days after their launch (2022–2024) and,
before that, 2× each stock's daily move minus the T-bill rate + 6.9% a year (the ETFs' typical cost).

### C2-7 Momentum 1x

| Period | A year | Worst fall | Sharpe | QQQ held a year / worst fall |
|---|---|---|---|---|
| 1 year | **+45.0%** | −13.6% | 1.34 | +15.9% / −12.0% |
| 3 years | **+52.2%** | −15.7% | 1.63 | +26.3% / −22.8% |
| 5 years | **+43.5%** | −16.2% | 1.57 | +14.0% / −35.1% |
| 10 years | **+31.5%** | −19.8% | 1.30 | +20.5% / −35.1% |
| All (from 31 Oct 2016) | **+31.5%** | −19.8% | 1.30 | +20.5% / −35.1% |

- **Worst fall:** −19.8%, from 1 Sep 2020 to 30 Oct 2020; back at the old high on 7 Jan 2021.
- **$10,000 became** $153,796 (+1,438%) from 31 Oct 2016 to 23 Oct 2026.
- **In the market** 65% of the days · **29.6 trades a year** · 66% of round trips made money (average +5.5%).
- Volatility 21% a year.

### C2-7 Momentum 2x

| Period | A year | Worst fall | Sharpe | QQQ held a year / worst fall | QLD held a year / worst fall |
|---|---|---|---|---|---|
| 1 year | **+93.9%** | −26.4% | 1.43 | +15.9% / −12.0% | +22.3% / −25.1% |
| 3 years | **+94.8%** | −30.3% | 1.55 | +26.3% / −22.8% | +44.0% / −42.3% |
| 5 years | **+76.1%** | −30.3% | 1.50 | +14.0% / −35.1% | +16.6% / −63.7% |
| 10 years | **+53.8%** | −33.3% | 1.27 | +20.5% / −35.1% | +32.6% / −63.7% |
| All (from 31 Oct 2016) | **+53.8%** | −33.3% | 1.27 | +20.5% / −35.1% | +32.6% / −63.7% |

- **Worst fall:** −33.3%, from 1 Sep 2020 to 30 Oct 2020; back at the old high on 7 Jan 2021.
- **$10,000 became** $733,801 (+7,238%) from 31 Oct 2016 to 23 Oct 2026.
- **In the market** 65% of the days · **29.6 trades a year** · 70% of round trips made money (average +9.7%).
- Volatility 38% a year.

### Year by year

**1x**

| Year | Strategy | QQQ held |
|---|---|---|
| 2026 (part) | **+45.6%** | +15.1% |
| 2025 | **+40.3%** | +20.8% |
| 2024 | **+58.1%** | +25.6% |
| 2023 | **+64.9%** | +54.9% |
| 2022 | **+8.0%** | −32.6% |
| 2021 | **+27.8%** | +27.4% |
| 2020 | **+68.2%** | +48.4% |
| 2019 | **+14.2%** | +39.0% |
| 2018 | **+2.8%** | −0.1% |
| 2017 | **+11.1%** | +32.7% |
| 2016 (part) | **−4.5%** | +1.6% |

**2x**

| Year | Strategy | QQQ held | QLD held |
|---|---|---|---|
| 2026 (part) | **+99.3%** | +15.1% | +22.5% |
| 2025 | **+62.1%** | +20.8% | +30.4% |
| 2024 | **+99.7%** | +25.6% | +42.8% |
| 2023 | **+112.3%** | +54.9% | +117.7% |
| 2022 | **+13.8%** | −32.6% | −60.5% |
| 2021 | **+37.9%** | +27.4% | +54.7% |
| 2020 | **+132.4%** | +48.4% | +88.9% |
| 2019 | **+21.5%** | +39.0% | +81.7% |
| 2018 | **+2.9%** | −0.1% | −8.3% |
| 2017 | **+24.0%** | +32.7% | +70.3% |
| 2016 (part) | **−5.3%** | +1.6% | +2.7% |

## The research

*Research on single Stock Nasdaq* (October 2026), chosen signal, 50/50 gold & T-bill parking:

| | 20 years (Dec 2006 – Oct 2026) | 2006–2016 (never used to choose the rules) | 2016–2026 | Last 5 years |
|---|---|---|---|---|
| **1x** | 27.4% a year, −19.7%, Sharpe 1.34 | 20.4%, −17.2% | 34.7%, −19.7%, Sharpe 1.50 | 46.9%, −15.6% |
| **2x** | 45.5%, −37.7%, Sharpe 1.17 (model) | 32.4%, −34.4% (model) | 59.6%, −37.7% (model) | 72.7%, −30.6% (real ETFs) |
| QLD + same QQQ signal | 33.4%, −36.4%, Sharpe 1.10 | 25.4%, −36.4% | 41.8%, −31.7% | 48.8%, −21.6% |
| QQQ held | 16.0%, −52.7% | 11.6%, −52.7% | 20.5%, −35.2% | 14.2%, −35.2% |

**Cross-check:** the bot's own backtest over the same 10 years (its code, the research's ranking and prices, Yahoo for QQQ, GLD and
the ETFs) gave **1x 34.0% a year, −19.5%, Sharpe 1.39** (research 34.7%, −19.7%, 1.50) and **2x 56.8%, −33.0%, Sharpe 1.32**
(research 59.6%, −37.7%, 1.31 — the research modelled 2x on every stock; the bot uses the real ETFs from 2022–2024) at a 0.05%
cost. The small differences come from the QQQ prices (Yahoo vs the research's dividend-adjusted series) and the 1% cash buffer.
At **Webull's real fee** (0.107% a trade, used as 0.11%; 2x ETFs 0.16% for their wider spread) the bot's backtest gives
**1x 31.5%** and **2x 53.8%** a year: about 30 trades a year, each a full stock position, cost 2.5–3 points a year.

- Over 45 signal settings, Momentum 2x beat "QLD + the same signal" in every window; the median worst fall of 2x was −39% to −42%,
  the worst setting −57% (2006–2016).
- 1x has the best risk-adjusted result (Sharpe 1.34); 2x adds about 18 points a year but doubles the falls and lowers the Sharpe.
- The 6-month lookback matters: 3 and 12 months were only as good as plain "7 largest".

## Expected return

What the bot plans with for this strategy (the Dashboard's *Expected return* panel uses the same numbers). The research
return minus the planning haircut is the typical case; the weak and good cases are about 1 period in 10 worse or better.

<!--expected:c27_mom-->

<!--expected:c27_mom2x-->

How it is worked out and how the yearly review keeps it current: [Expected returns](#/docs/expected-returns).

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

## Stock charts: every trade on its chart

The **Stock charts** tab on this strategy's page has a candle chart for **each symbol it trades**: QQQ (the signal), every stock or
2x ETF it has held, and the parking ETFs (GLD, SGOV). Tap a symbol, or tap a stock in *This week's list* on the Overview tab.

| On the chart | Meaning |
|---|---|
| ▲ green **Buy** / ▼ red **Sell** | The backtest bought or sold this symbol at that day's open |
| ▲ **On** / ▼ **Off** (QQQ only) | The close where the signal changed; the stocks trade at the next open |
| ● blue / orange **Bot** | The bot's own fills for this strategy (Paper, Webull test or Live) |
| *2x sim* | A trade from before the 2x ETF existed: the backtest used 2× the stock's daily move, so it is drawn on the stock |

Below the chart, **Round trips** lists each buy and sell with price, change, days held and why it went in and out (signal on/off, joined
or left the weekly list). Tap a row to zoom the chart to that trade. Candles are Yahoo daily prices, split-adjusted but **without dividends**,
the same as TradingView and Webull, so you can put the two side by side. The backtest itself counts dividends, so its numbers differ slightly.
Use **Open in TradingView** to check the same day there.

## Check it on TradingView

QQQ daily: **Supertrend** (ATR length 14, factor 4), **Moving Average** 200 and 5, **Relative Strength Index** length 2. The
6-month return of a stock: its close today ÷ its close 126 trading days ago − 1 (use total-return prices for dividend payers).
