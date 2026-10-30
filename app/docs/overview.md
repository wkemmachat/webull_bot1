<!--{"title": "What this bot does", "group": "Start here"}-->
# What this bot does

Webull Strategy Bot runs **twelve research strategies** on **one Webull Thailand account**, keeps a separate book for each,
sends every order as **split lots from a start time you choose**, tells you on **LINE**, and **cross-checks itself every night**.

| Strategy | Reads | Trades | Timeframe |
|---|---|---|---|
| Gold #1 · Supertrend + ADX | COMEX gold GC=F | UGL (2x gold) · cash | 4H bars |
| Gold #2 · Supertrend 30/2.5 | COMEX gold GC=F | UGL · cash | 4H bars |
| Silver #1 · Donchian 30/15 | COMEX silver SI=F | AGQ (2x silver) · cash | 4H bars |
| Silver #2 · Supertrend 10/3 | COMEX silver SI=F | AGQ · cash | 4H bars |
| QLD regime | QQQ daily | QLD (2x Nasdaq) · BIL · GLD | daily, after the US close |
| 2x Semis regime | SMH daily | USD (2x semis) · BIL · GLD | daily, after the US close |
| QLD + Trend + bear-dip | QQQ daily | QLD · BIL | daily, after the US close |
| QLD Trend + bear-dip + Vol | QQQ daily + its 20-day volatility | QLD · BIL | daily, after the US close |
| QLD Trend + IBS-dip | QLD daily (own price) + QQQ volatility | QLD (size capped) · GLD · cash | daily, after the US close |
| USD Trend + IBS-dip | USD daily (own price and volatility) | USD (2x chips, size capped, 100% on dip days) · GLD · cash | daily, after the US close |
| ROM Trend + RSI(2) | IYW daily | ROM (2x US tech) · cash | daily, after the US close |
| C2-7 Momentum 1x | QQQ daily + weekly Nasdaq-100 ranking | 7 Nasdaq stocks · GLD · SGOV | daily signal, weekly list |
| C2-7 Momentum 2x | QQQ daily + weekly Nasdaq-100 ranking | 7 stocks via 2x ETFs (on Webull TH: the stocks, works like 1x) · GLD · SGOV | daily signal, weekly list |

## How a trade happens

1. Every 30 seconds the bot refreshes prices and **evaluates every strategy**. A strategy never trades by itself: it says what it
   wants to hold, its **target** (for example *99% UGL*, or *25% QLD + 74% BIL*).
2. When the target changes, or a holding drifts more than the rebalance band from it (for example after you add money), the bot
   makes a **plan**: N rounds of limit orders, M minutes apart, from the start time. In each round sells go first, then buys.
3. Each lot is a limit order slightly through the market. A lot that does not fill is cancelled and re-sent at a fresh price,
   up to 3 times; each retry moves the limit at least 0.5% further (at most 2% beyond the first one), and a price with no
   trade yet that day (a thin ETF at the open) gets 0.5% more room. Fills are booked to the strategy that placed them.
4. LINE tells you what happened, either at once or in the digest, as you choose.
5. After the US close the **Health check** compares the bot's books with the broker and checks data, orders and backups.

## Three trading modes

- **Paper**: pretend money inside the bot, live prices. Each strategy starts with $10,000.
- **Webull test**: Webull's test server with test keys. Real API calls, no real money.
- **Live**: your real Webull account. Switching it on asks you to type LIVE.

Every mode that is on runs at the same time, with its own money and books. The switch at the top of each page chooses
which one you are looking at.

> Research and signals are for education, not financial advice. Leveraged ETFs can lose a lot quickly.
