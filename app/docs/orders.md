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

## Opposite orders between strategies (settled inside the bot)

Several strategies trade the same ETFs in one Webull account: USD (2x Semis regime, USD Trend + IBS-dip), QLD (QLD regime,
QLD + Trend + bear-dip, QLD Trend + IBS-dip), GLD and BIL (idle money). On some days one strategy sells what another buys:
in the 20-year backtests about 2 days a year for USD, 2 for QLD, 5 for GLD and 3 for BIL. Sending both to Webull would pay
the fee and the spread twice (about 0.2% per side) for no change in the account.

So, with Execution → **Opposite orders between strategies** on (the default):

- Once either side's lot is due during US regular hours, the bot moves the shares from the selling strategy to the buying one
  **inside its books**: one price for both (the middle of bid and ask, else the last price), **no fee**, no Webull order.
- How many: the smaller of what the seller still has to sell and what the buyer still needs and can pay for.
- **Only the rest goes to Webull** as usual. The seller's last waiting lots shrink first; the buyer's buys are sized from its
  books, so they shrink by themselves (and close when nothing is left to buy).
- **Tracking:** each side gets a filled lot marked *inside the bot* (Orders → Lots sent, and Trades, with the other
  strategy's name). Shares and cost move with the shares; the seller's cash goes up and the buyer's goes down by the same
  amount. The account's shares and cash do not change, so the strategies' books still add up to Webull's numbers and the
  Health check and money guard see no difference.
- The next-open preview shows what will be settled inside the bot and the net that goes to Webull.
- Not for Hong Kong symbols (board lots), and nothing happens while trading is paused or the market is closed.
- Turn it off to send both sides to Webull again.

**Orders** shows each plan with a lot grid (dashed = scheduled, green = filled, amber = filled after a retry, red = failed),
**Start now** and **Cancel plan**.

## Regimes and the next open

The research behind QLD regime and 2x Semis filled at the **next open** after the decision (39.7% a year vs 37.4% at the same
close for F, 2016–2026), so the bot decides after the US close and trades from the next market open.
