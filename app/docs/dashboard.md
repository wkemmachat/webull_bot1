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
- **Account split**: how the broker account is divided between the strategies, bot unassigned and *not for the bot*.
- **Money in strategies**: a donut of how the money in the strategies is split — the total is all strategies combined; bot unassigned money is not counted. Switch between **Value now** and **Money put in**. Hover or tap a slice for its share; tap a name to open the strategy.
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
- **Strategies**: value, return, today's profit or loss (since the last US close; the last session when the market is
  closed), a 30-day line, the worst fall and longest time underwater from its backtest, the current state and the next check.
- **Look**: light green by default (Settings → Theme for dark or follow the device). The mode switch shows **Live** in green.
- **Layout**: the page stays in a centered column (at most about 1,480 px wide) on large monitors. The top bar lines up with
  it, so your eyes don't travel to the far left and right edges.
- **Next up**: queued plans, the next 4H bar close, the next regime decision, the cross-check and the LINE digest, all in
  Bangkok time.
