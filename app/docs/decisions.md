<!--{"title": "Design decisions", "group": "Help"}-->
# Design decisions (October 2026)

- **Three money layers**: Webull account → allocated to the bot (strategies + bot unassigned) → strategies. Cash you do not
  allocate is never used. Withdrawals go back to bot unassigned; *Return to Webull* hands money back.
- **Money per strategy**: each strategy has its own dollar capital you add or withdraw (as in the AI x Alpaca bot), not a
  percentage of one pot. Paper starts every strategy with $10,000 in a $100,000 paper account.
- **New money**: invest at today's signal by default; switch to *wait for the next buy signal* in Execution → When new money arrives
  (or per deposit). Waiting money stays as plain cash in the strategy, outside its plans.
- **QLD + Trend + bear-dip** (added 23 Oct 2026 from the ETF Strategy Lab): same timing as the regimes (decide after the close,
  trade from the next open), T-bills via BIL when out, $10,000 paper money like the others.
- **Regime timing**: decided after the US close, traded from the next market open with split lots (the research filled at the next
  open, which tested better than the same close).
- **UGL in Gold #1 and Gold #2**: each strategy keeps its own orders and books; orders are not merged (simpler and easier to audit).
- **Metals entries** start not before 22:00 Bangkok (after the US open has settled); exits start as soon as the market is open.
- **Login**: one login only (yours): username or email + password. No sign-up page for anyone else; the first login can only
  be created on the bot's own computer (or from `.env` on the server). 5 wrong tries → 15-minute lock and a LINE alert.
- **Charts**: TradingView Lightweight Charts drawing the bot's own indicator values, so the chart always matches what was traded.
- **Language**: English, with Thai terms in the glossary.
