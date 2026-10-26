<!--{"title": "Backtest", "group": "Using the app"}-->
# Backtest

Every strategy page has a **Backtest** tab. It runs the strategy's **own code** (the same code that trades) over past prices
and shows what $10,000 would have become, next to simply holding the ETF (and the index it follows).

## What you see

| Part | Meaning |
|---|---|
| Tiles | A year (CAGR), worst fall (and when), what $10,000 became, Sharpe (above T-bills), time in the market, trades a year and the share of round trips that made money |
| Chart | Growth of $10,000: the strategy, the ETF held (grey) and the index held (pink, dashed). Log scale on by default so old and new years compare fairly. Below: the fall from the last high, and how much money was in the ETF |
| Period | 1 / 3 / 5 / 10 years or All. Everything on the page follows the period |
| Strategy vs simply holding | The same numbers side by side, including when the worst fall started, its bottom and when the old high came back |
| Compared with the research | The research's headline numbers next to this backtest (marked if your settings differ from the research) |
| Year by year | Calendar-year returns; the current year is marked *part* |
| Trades | Every buy, sell and rebalance with the reason (the same text as the live signal) |
| Try other settings | Change the rules and run again. **Nothing is saved or traded** — the Parameters tab saves |
| Stock charts (C2-7 only) | A separate tab: a candle chart of every stock or ETF the strategy traded, with each backtest buy and sell (and the bot's own fills) marked, to cross-check trades |

## How it is simulated

- **Daily strategies** (QLD regime, 2x Semis regime, QLD + Trend + bear-dip, QLD and USD Trend + IBS-dip): decided on each US close, traded at the **next
  day's open** (as in the research and the bot). Trades happen only when the target changes, or when a holding drifts more than the
  rebalance band.
- **4H metals strategies** (Gold #1/#2, Silver #1/#2): a signal counts when its 4H futures bar closes (plus Yahoo's ~11-minute delay).
  The trade happens at the bot's real start time from **Execution** (entries not before 22:00 Bangkok by default, exits as soon as
  the US market is open), spread over the lots, priced from hourly ETF prices.
- **Prices include dividends** (total return), so BIL and SGOV earn their interest.
- **Webull's real fee on every trade: 0.11% per side** by default — Webull Thailand charges 0.10% commission + 7% VAT
  = 0.107% of each buy and each sell, with no minimum, and 0.11 leaves a little for the spread. Every leg pays it: the ETF,
  and the gold and T-bill parking ETFs too. Single-stock 2x ETFs (C2-7 2x) pay 0.05% more for their wider spread.
  Change it in **Settings → Fees**; every backtest, the docs numbers and the expected returns use that one value.
  (Until 26 Oct 2026 the backtests charged 0.05%, which made the busy strategies look 1–9 points a year better.)
- Not included: whole-share rounding, partial fills, the money guard, money added or withdrawn, taxes.

## How far back

| Strategies | Data | Period |
|---|---|---|
| QLD regime, QLD + Trend + bear-dip | QQQ daily (signal), QLD, BIL, GLD daily | from mid-2007 (when BIL and QLD both exist) |
| QLD Trend + IBS-dip | QLD daily (signal), QQQ daily (size), QLD, GLD, BIL daily | from mid-2007 |
| USD Trend + IBS-dip | USD daily (signal and size), USD, GLD, BIL daily; SMH for comparison | from November 2007 (USD started in February 2007, plus 200 days for its average) |
| 2x Semis regime | SMH daily, USD, BIL, GLD daily | from mid-2007 |
| C2-7 Momentum 1x / 2x | QQQ daily (signal), weekly Nasdaq-100 ranking and stock prices from the research (2016–2026, then the bot's own), 2x ETFs, GLD, SGOV | from late October 2016 (the research's ranking file) |
| Gold #1/#2, Silver #1/#2 | GC=F / SI=F hourly futures, UGL / AGQ / SGOV | about 2 years: Yahoo keeps only 2 years of hourly futures |

The metals research covered 10 years with other data (see each strategy's doc page); the in-app backtest is shorter but uses the
exact live code and timing.

## Reading it honestly

- Past results do not promise future ones. The research picked these settings because they tested well, so expect less.
- Look at the **worst fall** before the yearly return: a −40% fall means $10,000 became $6,000 for a while. Ask yourself whether
  you would have kept the bot running.
- Use **Try other settings** to check robustness: if small changes (SMA 180 instead of 200, ATR 25 instead of 30) give very different
  results, the default may just be lucky.

The price history is downloaded from Yahoo by the server the first time (up to half a minute) and refreshed twice a day. Results are
kept in memory until the data or the settings change.
