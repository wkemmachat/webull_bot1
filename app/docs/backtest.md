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

## The Backtest page (every strategy at once)

**Backtest** in the side menu puts every strategy side by side, from the last expected-returns check (no backtests run, so
it opens at once). Gold and silver on their default settings use the research's 10 years (OANDA prices) because Yahoo keeps
only about 2 years of hourly metals prices; the table marks those *research*.

| Part | Meaning |
|---|---|
| Summary | Money in strategies; what you would lose if every strategy had its worst 10-year fall at once; money by holding, with a warning when one holding is more than half |
| Table | Your money (and in red under it what you would lose if the 10-year worst fall came back), 1, 3 and 10 years a year, worst fall, **return ÷ fall** (sorted best first by default), years up, share of weeks below the last peak, and **Now**: how far below its high it is and how that ranks in its own past (the same dip zone as Money). Click a column to sort, a strategy to open its own backtest |
| Return against worst fall | A dot per strategy: higher = more return, further left = smaller fall. Size = your money in it |
| Growth of $10,000 | Every strategy on one log chart (weekly closes, profit reinvested) |
| Do they move together? | Correlation of weekly returns. Money split across strategies that move together (dark squares) is not really spread |
| Try a mix | Sliders for each strategy's share; blue = your money as split now, green = your mix. Shows a year, worst fall, return ÷ fall, the dollar fall and the worst 12 months. Nothing moves money |

## More on a strategy's Backtest tab (5 Nov 2026)

| Part | Meaning |
|---|---|
| Compounding / Fixed $10,000 | Compounding keeps profit in (the position grows, like Auto contracts on the TFEX bot). Fixed $10,000 takes profit out and tops up losses, so every trade is the same size (like 1 contract); the line then is $10,000 + total profit, on a normal scale |
| 12-month rolling return | The return over the 12 months up to each day. Long stretches below zero are the years that test your patience |
| Month by month | Every month's return; a run of red is how a bad stretch feels from inside |
| Range of outcomes | The last 10 years (or all there is) cut into 13-week pieces and shuffled 2,000 times: a bad case (1 in 10 worse), the middle case, the typical worst fall and the chance of a fall past −30/40/50%. Gold and silver on default settings use the research's 10 years |
| What if trading goes worse than planned? | The same backtest with fees of 0.25% and 0.50% a side and every order late: one trading day for daily strategies and C2-7, one 4-hour bar for gold and silver (often no change for them: an entry waits for the 22:00 start and an exit for the US open anyway). A strategy whose return collapses here depends on the bot trading on time. Gold and silver: only the ~2 years of hourly prices Yahoo keeps, marked on the box — compare the rows with each other, not with the 10-year numbers |
| Good markets and bad markets | Return a year while the strategy's index was above / below its 200-day average (the day before), next to holding the ETF. A good strategy keeps most of the up-trend and loses less in the down-trend |

The range of outcomes and the stress test are worked out **once a day after the US close** (about 17:00 New York, in the
background) and saved, so the tab opens at once, also after a restart. If you change a strategy's settings, the execution
settings or the fee, that strategy's are worked out again the next time you open its tab (a few seconds). The box says when
they were worked out.

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
| QLD Trend + IBS-dip | QLD daily (signal), QQQ daily (size), QLD, GLD daily | from mid-2007 |
| USD Trend + IBS-dip | USD daily (signal and size), USD, GLD daily; SMH for comparison | from November 2007 (USD started in February 2007, plus 200 days for its average) |
| 2x Semis regime | SMH daily, USD, BIL, GLD daily | from mid-2007 |
| C2-7 Momentum 1x / 2x | QQQ daily (signal), weekly Nasdaq-100 ranking and stock prices from the research (2016–2026, then the bot's own), 2x ETFs, GLD, SGOV | from late October 2016 (the research's ranking file) |
| Gold #1/#2, Silver #1/#2 | GC=F / SI=F hourly futures, UGL / AGQ (cash while flat) | about 2 years: Yahoo keeps only 2 years of hourly futures |

The metals research covered 10 years with other data (see each strategy's doc page); the in-app backtest is shorter but uses the
exact live code and timing.

## Reading it honestly

- Past results do not promise future ones. The research picked these settings because they tested well, so expect less.
- Look at the **worst fall** before the yearly return: a −40% fall means $10,000 became $6,000 for a while. Ask yourself whether
  you would have kept the bot running.
- Use **Try other settings** to check robustness: if small changes (SMA 180 instead of 200, ATR 25 instead of 30) give very different
  results, the default may just be lucky.

**20 years for every daily strategy.** The 2x ETFs started trading in 2006–2007 (QLD 21 Jun 2006, ROM and USD early
2007) and BIL in May 2007. For the months before that, back to January 2006, the backtest builds their daily prices from
the index: 2 × the daily move of QQQ (QLD), SMH (USD) or IYW (ROM), minus the fund's 0.95% yearly fee and the cost of
borrowing the second 1× (the T-bill rate of that year); BIL grows at the T-bill rate. The built prices are chained back
from the ETF's first real close, so the real history is unchanged. With the indicators' warm-up every daily strategy
starts in 2006 (about 20 years). The Falls card names the symbols and shades that part of the chart. Checked on years
where the ETFs exist: QLD and ROM built this way follow the real ETF closely (daily correlation 0.997); USD less so (0.975),
because it tracks a different semiconductor index than SMH.

The price history is downloaded from Yahoo by the server the first time (up to half a minute) and refreshed twice a day. Results are
kept in memory until the data or the settings change.
