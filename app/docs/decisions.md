<!--{"title": "Design decisions", "group": "Help"}-->
# Design decisions (October 2026)

- **Three money layers**: Webull account → allocated to the bot (strategies + bot unassigned) → strategies. Cash you do not
  allocate is never used. Withdrawals go back to bot unassigned; *Return to Webull* hands money back.
- **Money per strategy**: each strategy has its own dollar capital you add or withdraw (as in the AI x Alpaca bot), not a
  percentage of one pot. Paper starts every strategy with $10,000; a new install's paper account is $150,000 (eleven strategies).
- **New money**: invest at today's signal by default; switch to *wait for the next buy signal* in Execution → When new money arrives
  (or per deposit). Waiting money stays as plain cash in the strategy, outside its plans.
- **QLD + Trend + bear-dip** (added 23 Oct 2026 from the ETF Strategy Lab): same timing as the regimes (decide after the close,
  trade from the next open), T-bills via BIL when out, $10,000 paper money like the others.
- **QLD Trend + IBS-dip** (added 25 Oct 2026 from *Research on single Stock Nasdaq*, strategy 2): the signal comes from QLD's own
  daily bar, the size from QQQ's 60-day volatility (resized only on a 20-point move), parking 50% GLD + 50% BIL (BIL rather than
  SGOV so the backtest reaches back to 2007, like the other QLD strategies). Dip days are one-day trades; resizes are sent to
  LINE as RESIZE messages.
- **USD Trend + IBS-dip** (added 25 Oct 2026, research *USD own-price candidate C, aggressive*): the same strategy type on USD with
  its own volatility (leverage 1, 40% cap, 20 days), Supertrend 20 × 4.5, dips on IBS < 0.15 without an ADX filter held at **100%**
  (option *Dip days at full size*). The research resized every day (~134 trades a year); the bot uses the 20-point resize rule
  (~62 a year, same 10-year result). Backtest compares with SMH (option *Compare with*).
- **Expected returns** (added 25 Oct 2026): the plan per strategy is the research yearly return minus a 30% planning haircut
  (0/15/30/50% selectable). The weak / good cases are the 10th / 90th percentiles from the strategy's volatility in the bot's
  10-year backtest. The total is each strategy's own money compounding at its own plan (sub-accounts are never rebalanced);
  the total's range uses the correlations of weekly backtest returns. The research numbers live in one file,
  `app/research/expected.json`, read by the Backtest tab, the strategy pages and the Dashboard. The bot re-runs the backtests
  once a year (LINE). The research review is done with Claude, prompted by a monthly LINE reminder while it is due.
- **Ratio planner** (25 Oct 2026): set a % per strategy, see 1/2/3 years live, save the ratio on the server (`expected_plan`),
  and give bot-unassigned money by it through the usual Give-to-strategies dialog, prefilled. The target is (money in strategies +
  unassigned) × ratio. Only gaps are filled (scaled down when unassigned is short); nothing is sold automatically.
- **Regime timing**: decided after the US close, traded from the next market open with split lots (the research filled at the next
  open, which tested better than the same close).
- **UGL in Gold #1 and Gold #2**: each strategy keeps its own orders and books; orders are not merged (simpler and easier to audit).
- **Metals entries** start not before 22:00 Bangkok (after the US open has settled); exits start as soon as the market is open.
- **Login**: one login only (yours): username or email + password. No sign-up page for anyone else; the first login can only
  be created on the bot's own computer (or from `.env` on the server). 5 wrong tries → 15-minute lock and a LINE alert.
- **Charts**: TradingView Lightweight Charts drawing the bot's own indicator values, so the chart always matches what was traded.
- **Language**: English, with Thai terms in the glossary.
