<!--{"title": "Health check (error cross-check)", "group": "Using the app"}-->
# Health check (error cross-check)

Runs every trading day at 16:45 New York (03:45 or 04:45 Bangkok) and with **Run check now**. It only **reads**: it never places,
changes or cancels an order. Each line is ok, warning or problem, with what to do.

1. Scheduler heartbeat: the bot ticked without long gaps.
2. Every strategy evaluated in the last 15 minutes.
3. Prices are fresh.
4. **Indicators match an independent recompute**: Supertrend, ADX, Donchian, SMA and volatility are recalculated by a second,
   separately written routine and compared bar by bar.
5. For each mode that is on: connection, **bot books = account positions**, cash adds up, no strategy below $0, no refused
   orders, lots without retries, no stuck orders, Webull login valid.
6. LINE delivered, and last night's database backup exists.

Problems go to LINE at once (critical); warnings go in the digest. The **Indicator cross-check** table lets you type
TradingView's value next to the bot's for any bar.

## Checking against TradingView

- Gold/silver: chart `COMEX:GC1!` or `COMEX:SI1!`, 4-hour, and add the built-in **Supertrend** (ATR length and factor as in the
  strategy), **ADX** (DI length 14, smoothing 14) or **Donchian Channels**. Small differences can come from contract-roll
  back-adjustment (Settings → Data lists the rolls).
- Regimes: `QQQ` / `SMH` daily, **Moving Average** 200 and 50, and **Historical Volatility** 20.
