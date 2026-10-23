<!--{"title": "Gold #1 \u00b7 Supertrend + ADX", "group": "The strategies"}-->
# Gold #1 · Supertrend + ADX

- **Signal**: COMEX gold futures (Yahoo GC=F), 4-hour bars aligned with TradingView (session opens 18:00 New York).
- **Buy** when a 4H bar closes with Supertrend(30, 2.5) up **and** ADX(14) above 20 (the market is trending). If Supertrend turns up
  while ADX is 20 or lower, it waits for the first close with ADX above 20.
- **Sell** when a 4H bar closes below the Supertrend line. ADX does not matter for the exit.
- **Holds** UGL (2x gold) while long, SGOV (T-bills) while flat, with a 1% cash buffer.
- 10-year ETF test (Apr 2016 – Oct 2026, from the Gold & Silver research): 10.3% a year, worst fall −13.2%.
