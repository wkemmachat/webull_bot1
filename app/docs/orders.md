<!--{"title": "Orders & split execution", "group": "Using the app"}-->
# Orders & split execution

A **plan** moves one strategy from what it holds to its target.

- **Rounds**: N lots, M minutes apart. In each round the sells go first, then the buys, so cash is freed before it is spent.
- **Start time**: *at a set Bangkok time* (default 22:00 for the metals) or *at the market open* (default for the regimes). The
  time means "not before": a signal that arrives later while the market is open starts at once. Lots that would fall outside US
  regular hours move to the next session.
- **Exits** start as soon as the market is open by default (selling is usually more urgent).
- **Sizing**: sells are fixed share counts decided when the plan is made. Buys are sized when each lot is sent, from the
  strategy's free cash and how far each symbol is from target, so the last lot uses what is left.
- **Limit price**: ask + 0.10% for buys, bid − 0.10% for sells. Unfilled lots are cancelled after the interval and re-sent at a fresh
  price, up to 3 times; then the lot is marked failed and LINE tells you (critical).
- **Small plans** use fewer lots so each lot is at least $200 (Execution → Smallest lot).
- **Fractional shares** (Execution → Fractional shares, on for Live since 27 Oct 2026): lots buy whole shares and the last lot of
  each ETF adds the leftover fraction; exits sell fractions too. Fractions use 2 decimals (33.62), as Webull reports them.
- **Safety**: every order has a unique client order id. If Webull does not answer, the bot looks the order up before it ever sends
  a replacement. It never sells more shares than the account really holds.

**Orders** shows each plan with a lot grid (dashed = scheduled, green = filled, amber = filled after a retry, red = failed),
**Start now** and **Cancel plan**.

## Regimes and the next open

The research behind QLD regime and 2x Semis filled at the **next open** after the decision (39.7% a year vs 37.4% at the same
close for F, 2016–2026), so the bot decides after the US close and trades from the next market open.
