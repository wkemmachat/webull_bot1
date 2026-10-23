<!--{"title": "QLD + Trend + bear-dip", "group": "The strategies"}-->
# QLD + Trend + bear-dip

From the **ETF Strategy Lab (23 Oct 2026)** research (`code/choose.py`, `tbd_pos` / `run_tbd`). After each US close, from **QQQ**'s
daily closes:

| State | Rule | Holds |
|---|---|---|
| In · trend | QQQ closes above its SMA200 | 100% QLD (99% with the buffer) |
| In · dip trade | Below SMA200, a dip trade opens when RSI(2) < 5 and closes on the first close above SMA5 | 100% QLD |
| Out | Below SMA200 and no dip trade open | 100% BIL (T-bills) |

Orders start at the next market open in split lots (the research filled at the next open, 0.05% per side).

## Research numbers (Oct 2007 – Oct 2026, 19 years)

- CAGR **32.9%** a year, worst fall **−42.5%**, Sharpe 0.95 (QQQ held: 15.1% a year, −53.3%).
- In QLD about 84% of the time (trend 82%, dip trades about 3%); about 4 entries a year, 33 dip trades.
- 60 neighbouring settings (SMA 150–250, RSI 3–15, exit SMA 3–10): CAGR 22–33%, median 27.6%; the default is among the best,
  so expect less in the future.
- Calendar years: 2008 **+48%** (dip trades), 2022 −10%, 2016 −1.7%, 2018 −3.4%.

## Cross-check of the bot's rule (23 Oct 2026)

- The bot's code gives **exactly the same position as the research code** on every day of four random test series (automated tests).
- On the research's own QQQ data, the bot's positions match the research's QLD returns on 99.8% of the 2,644 clearly readable days; the
  few others are days where QLD did not move like 2× QQQ in the data (QQQ was 14–24% above its SMA200, clearly "in").
- The nightly Health check recomputes SMA200 and RSI(2) with a separate routine and replays the rule bar by bar.

## TradingView

QQQ daily: **Moving Average** 200 and 5, **Relative Strength Index** length 2 (TradingView's RSI = the bot's, Wilder averages).

> RSI(2) needs only a few days of history, but the very first value depends on how the average starts; the research used pandas'
> exponential average, the bot TradingView's. They agree after about 20 bars, so signals are the same.
