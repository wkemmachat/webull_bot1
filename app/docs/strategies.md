<!--{"title": "Strategies & controls", "group": "Using the app"}-->
# Strategies & controls

Each strategy is a **sub-account**: its own money, holdings, plans, LINE switch and execution settings.

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

**Strategies → + Add strategy** offers every strategy type: Supertrend (with optional ADX filter), Donchian breakout and
Regime. For example a *TQQQ regime* or a *Supertrend on silver with different settings*. New strategies start with paper money
only. Completely new rule types are Python plugins (see *Add a strategy plugin*).
