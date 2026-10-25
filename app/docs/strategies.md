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
- **Parameters**: the rules (periods, multipliers, symbols, weights). Changes apply from the next evaluation.
- **Execution**: the strategy's own lots, spacing and start time (empty = defaults).
- **History**: its plans and money movements.

## Adding a strategy

**Strategies → + Add strategy** offers every strategy type: Supertrend (with optional ADX filter), Donchian breakout, Regime,
Trend + bear-dip, Trend + IBS-dip with a volatility cap (used for QLD and for USD; options for full-size dip days and the comparison symbol), and Momentum basket (C2-7: the strongest of the largest Nasdaq-100 stocks, 1x or 2x). For example a *TQQQ regime* or a *Supertrend on silver with different settings*. New strategies start with paper money
only. Completely new rule types are Python plugins (see *Add a strategy plugin*).
