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
