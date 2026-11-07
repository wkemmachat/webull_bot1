<!--{"title": "Strategies & controls", "group": "Using the app"}-->
# Strategies & controls

Each strategy is a **sub-account**: its own money, holdings, plans, LINE switch and execution settings.

At the top, **Money in strategies** shows the same donut as the dashboard: each strategy's share of the money in all strategies (unassigned money not counted), as value now or money put in. Below it, the same **Expected return** panel as the Dashboard ([Expected returns](#/docs/expected-returns)).

## Controls

- **Active**: follows every signal (buys, sells, rebalances).
- **Pause buys**: exits and sells still run; nothing new is bought. Cash waits.
- **Stop & sell**: sells everything with a split plan in every mode, then the strategy rests as **Stopped** with cash. Its money can
  then be withdrawn or moved. Set it to Active to start again.

## The strategy page

- **Overview**: value, holding, current signal, next check, the TradingView-style chart with the strategy's own indicators, the
  signal check (the numbers behind today's decision), holdings vs target, and every signal.
  - On the daily charts (US strategies), **today's bar so far** is drawn after the last closed bar, lighter with an outline,
    from the US open (21:30 Bangkok in winter, 20:30 in summer) until the bot stores the closed bar. The legend says *today so far
    (live)*; reload the page to update it (prices refresh every minute). The bot does not use it: signals, indicators and panes
    are worked out on closed daily bars only, so lines like the EMA end at yesterday's close.
  - **Arrows** are trades: *Buy* below the bar, *Sell* above it. A **dot** marks a change with no trade: *Size 60%* when a
    strategy that sizes by volatility changes its size, and *→ dip* / *→ trend* when the reason for holding changes but the
    position stays the same. For example, on 2 Nov 2026 IYW closed below its 150-day average on a day with RSI(2) below 5, so the
    ROM strategies went from the trend straight into a dip trade and kept holding ROM: no arrow, just *→ dip*.
- **Fall from its high** (the fifth card in Overview): how far the strategy is below its backtest high today, next to
  its **worst fall in the last 10 years before this one** (the current fall is left out, so a new record shows as deeper
  than the worst). The bar fills toward the worst (the line); it turns amber at 75% of the way and red past it. Below:
  **your money**, how far your own money in this strategy is below its high since you started (money added or taken out is
  left out). The two differ when you started in the middle of a run: on 5 Nov 2026 ROM Trend + RSI(2) was about 37% below
  its June high, while money that started in October was about 34% below its October high.
  - **LINE** (*Deep fall* in LINE alerts): once a day after the US close, one message when a strategy reaches 75% of its
    worst 10-year fall and one more when it goes past it, with each mode's own money. Once per fall: armed again only after
    a new high. It is a warning only; nothing is sold. An extra stop on top of the strategies' own exits was tested on
    6 Nov 2026 and made things worse ([Design decisions](#/docs/decisions)): to take less risk, hold less in the strategy.
  - Backtests shorter than 5 years show the fall but get no warning: there is too little history to call anything the
    worst. Gold and silver used to be such a case (Yahoo keeps about 2 years of hourly futures); since 7 Nov 2026 their
    backtests go back to December 2008 with OANDA spot before the bot's own bars ([Backtest](#/docs/backtest)).
- **Real** (under the value, when it differs): the result of your own money since you started, **time-weighted**, so
  money added or taken out does not change it. The simple *% on money put in* does change: in Nov 2026 $5,500 went into
  ROM Trend + RSI(2), it fell about 24%, then $2,500 was moved out, so the $940 loss showed as −31% on the $3,000 left
  while the real result was about −24%. The Dashboard cards and the Daily P&L tab show it too, and *Your money* on the
  Fall card is measured the same way.
- **Next US open** (top of Overview): this strategy's orders waiting for the next open (same table as the Dashboard), or
  "no order waiting" when it already holds its target.
- **Growth of $10,000** (on Overview, above Falls to expect): the same backtest and the same dates as Falls to expect, after
  fees. Tiles: what $10,000 became (and the yearly return), what simply holding the traded ETF would have made, how many
  calendar years were up (best and worst), and the worst fall. The chart shows the strategy in its colour, the traded ETF held
  (grey) and its signal index (dashed grey), the worst fall in red, and the years before an ETF existed shaded "built from the
  index". **Log** (default) or **Linear** scale; hover for the values on a day. Once the strategy has real money in the current
  mode, a black **Real** line starts at the backtest's value on its first day, so you can see whether real follows the
  backtest. Under the chart: one bar per calendar year (lighter = part of a year). Point at a bar (or tap it on a phone) to see
  that year's return next to holding the ETF and the index; a click keeps it shown until you click the year again.
- **Falls to expect** (on Overview): how deep and how long the strategy has been below its previous high. Read it before
  giving the strategy money.
  - **Fall now** and **Fall now · percentile** (top row): how far the backtest is below its high today, and how deep that is
    compared with its own past days (the share of days in the last 20 years, or all it has, that were less deep; the 70th,
    80th and 90th percentile depths are listed). 70th–79th shows ▲ Buy zone and 80th or more ▲▲ Strong buy zone, the same
    zones as the Dashboard banner.
  - **From the backtest:** the worst fall (from the high to the bottom, how long it fell and how long it took to recover), the
    longest time underwater (from a high until a new high), the share of days below a previous high, and how often it fell 20%
    or more.
  - An **underwater chart** of the whole history and a table of the 5 worst falls. If the backtest is longer than 10 years, the
    last 10 years are also shown on their own.
  - **Real:** the same numbers for this strategy's real values in the mode you are looking at (money added or withdrawn left
    out), including how far below its high it is now. Also the research's worst fall.
- **Daily P&L**: the real profit or loss for each US trading day.
  - Each row: the value at the close, the day's P&L in $ and %, money added or withdrawn that day (left out of the P&L), and
    the total since start.
  - Tiles at the top: today (or the last session when the market is closed), this month, since start, and days up / down.
  - A bar chart of the last 66 days and **Download CSV** for a spreadsheet.
  - The day's close is the last value the bot recorded that US day; it records every 30 minutes. Webull's statement stays the
    official record.
- **Backtest**, **Stock charts** (C2-7): see their own pages.
- **Parameters**: the rules (periods, multipliers, symbols, weights). Changes apply from the next evaluation.
- **Execution**: the strategy's own lots, spacing and start time (empty = defaults).
- **History**: its plans and money movements.

## Adding a strategy

**Strategies → + Add strategy** offers every strategy type: Supertrend (with optional ADX filter), Donchian breakout, Regime,
Trend + bear-dip (optional volatility filter), Trend + IBS-dip with a volatility cap (used for QLD and for USD; options for full-size dip days and the comparison symbol), and Momentum basket (C2-7: the strongest of the largest Nasdaq-100 stocks, 1x or 2x). For example a *TQQQ regime* or a *Supertrend on silver with different settings*. New strategies start with paper money
only. Completely new rule types are Python plugins (see *Add a strategy plugin*).
