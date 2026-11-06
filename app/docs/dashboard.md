<!--{"title": "Dashboard", "group": "Using the app"}-->
# Dashboard

- **Next US open** (top of the page): the orders each strategy will send at the next US open, decided after the close.
  - Each row: the strategy, buy or sell, symbol, shares, last price and ≈ value, why (the signal) and what it will hold after.
  - When the plan starts (Bangkok time, with a countdown) and how many lots.
  - Sells are exact. Buys are estimated from the last price: the bot sizes each lot when it sends it.
  - Totals of buys and sells, and a note when two strategies trade the same ETF.
  - Plans already trading show *running* with the rounds left. **Orders** lets you start a plan now or cancel it.
  - Open it in the morning to check the orders against the chart: the arrow on the last candle is the decision, and this list
    is what goes out at the open.
- **Bot equity**: the value of all strategies in the mode you are looking at, with today's change (money added today is left out), the return on net money in,
  and the difference to **buy & hold** (each strategy's money held in its main ETF since it was added).
- **Profit & loss by strategy** (under Bot equity; click **Today** or **Since start** in Bot equity to jump to it): each
  strategy's part of those numbers, worked out exactly like Bot equity (value change minus money moved in or out), so the rows
  always add up to the Dashboard number.
  - Periods: **Today** (the same window as Bot equity's Today), **1W**, **1M**, **3M**, **Since start**.
  - **Bars**: one bar per strategy, green right of $0, red left, best first; the last row is the total. Show them in **$**,
    **% of its money** (each strategy on its own: P&L ÷ all the money it was given, or ÷ its value at the start of the period;
    these do not add up) or **pts of total** (its share of the total %; these add up to the Bot equity %). Hover a bar for money
    put in, value now, P&L, its share, and for Since start how much is **booked** (sold) and **still open** (on shares it holds).
    Click it to open the strategy's Daily P&L.
  - **Over time**: each strategy's running P&L as a coloured band (gains stacked above $0, losses below) and the total as a dark
    line, from the 30-minute value snapshots taken during the regular US session (pre-market and after-hours prices are thin and
    made spikes, so they are left out; the last point is now). Hover for each strategy's part at that time; click a name to hide it.
  - Strategies that hold no money now but made or lost money earlier (sold or stopped) stay in the list, marked
    *no money now*: their result is still part of the total. Strategies that never had money are listed underneath.
  - The table under the chart has the numbers; click a column header to sort. The period, units and view are remembered on this
    device.
- **Account split**: how the broker account is divided between the strategies (most money first), bot unassigned and *not for the bot* (always last).
- **Money in strategies**: a donut of how the money in the strategies is split — the total is all strategies combined; bot unassigned money is not counted. Switch between **Value now** and **Money put in**. Hover or tap a slice for its share; tap a name to open the strategy.
- **What your money is in** (under the donut): all strategies' holdings together, grouped by what each ETF follows:
  Nasdaq-100 (QQQ, QLD), US tech (IYW, ROM), semiconductors (SMH, USD), Nasdaq-100 stocks (C2-7), S&P 500, gold, silver,
  T-bills and cash. **Acts like** counts a 2x ETF twice: $1,000 in ROM acts like $2,000 in US tech. The top line adds up the
  groups marked with a green edge, because they fall together on a bad tech day (5 Nov 2026: IYW −6.9%, QQQ −5.8%, SMH −8.6%),
  and says what a 10% fall in US tech would cost. That is a rough guide: semiconductors usually move more than the
  Nasdaq-100. It is amber when the US tech part acts like more than 100% of the money.
- **Expected return**: what the money could be worth in 1, 2 and 3 years if it stays split like the donut. Each period shows the
  typical case (research return lowered for Webull's real fee, minus the planning haircut, 30% by default; change it with the
  *Haircut* buttons) and a weak / good case (about 1 in 10 worse / better), plus the worst fall of your split in the backtest.
  The table shows each strategy's plan a year, its 1- and 3-year range, **real vs expected** (Too early / Ahead / Behind /
  Below weak case) and its **bot backtest now** (10 years, at the fee in Settings → Fees; re-run by itself within 10 minutes
  when the fee or a strategy's settings change). It starts with the most profitable strategy (highest plan a year); click any
  column header to sort by it, again to reverse. The choice is remembered on this device.
  **Plan a ratio** opens the ratio planner: a slider and a % for each strategy with the 1/2/3-year result updating live. You can
  save the ratio, then press *Give unassigned money by this ratio*, which opens the Give-to-strategies dialog already filled in.
  *Re-run the check* re-runs
  every backtest for the ranges. Details: [Expected returns](#/docs/expected-returns).
- **Cards**: bot unassigned, active order plans, the last health check, LINE in the last 24 hours.
- **⚠ Near / past its worst fall** on a strategy card: see *Fall from its high* in [Strategies](#/docs/strategies).
- **Strategies**: value, return, today's profit or loss (since the last US close; the last session when the market is
  closed), a 30-day line, the worst fall and longest time underwater from its backtest, the current state and the next check.
- **Look**: light green by default (Settings → Theme for dark or follow the device). The mode switch shows **Live** in green.
- **Layout**: the page stays in a centered column (at most about 1,480 px wide) on large monitors. The top bar lines up with
  it, so your eyes don't travel to the far left and right edges.
- **Next up**: queued plans, the next 4H bar close, the next regime decision, the cross-check and the LINE digest, all in
  Bangkok time.
