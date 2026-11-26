<!--{"title": "QPUX · Dip + trend + RSI, Bitcoin check (Safe)", "group": "The strategies"}-->
# QPUX · Dip + trend + RSI, Bitcoin check (Safe)

This strategy trades **QPUX (Defiance 2x Daily Long Pure Quantum ETF)**, a 2x ETF on an equal-weight basket of quantum-computing companies (IonQ, Rigetti, D-Wave, Quantum Computing Inc. and newer listings). It does not move with your other strategies' markets.

It has **three legs**. Each leg needs **Bitcoin above its 100-day average** (the *Safe* version). The money in QPUX is the legs' weights added up, at most 100%; the rest stays in cash.

| Leg | Buys when | Weight | Held |
|---|---|---|---|
| **Dip** | The quantum-stock basket closes weak (**IBS < 0.20**) while the basket is above its **200-day average** | 0.4 | One day (next open to the open after) |
| **Trend** | QPUX is above its **50-day average** and **QQQ** is above its **200-day average** | 0.5 × size | While both hold; size = 60% ÷ QPUX's 20-day volatility (usually about 30%) |
| **RSI bounce** | QPUX's **RSI(2) < 10** while above its 50-day average | 0.25 | Until a close above its 5-day average |

This is the **Safe version of round 3** of the research *QPUX: two best strategies per window* (26 Nov 2026). The research's main pick put the Bitcoin check on the trend leg only. You chose Safe (Bitcoin on every leg) after comparing the three versions' growth and falls: it had the shallowest falls and the fewest days deep down.

Added on 26 Nov 2026 **with no money** and LINE off. You allowed it on Live, but first:
- run a **Webull test trade of QPUX** (Go-live checklist): Webull Thailand must offer it;
- **start small**.

## Read this first

- **The fund is collapsing.** QPUX is down 98.8% from its October 2025 high, at $2.82 (25 Nov 2026). About $2.5 million trades a day. A one-cent spread costs about 0.35% a trade, and a small leveraged ETF that shrinks like this can be **closed by its issuer**. If that happens, Defiance sells the holdings and pays out cash.
- **Most of the history is a model.** QPUX listed on 7 Aug 2025. Before that, the backtest builds it as 2 × the daily move of the basket (QUBT and IONQ from Oct 2021, RGTI from Mar 2022, QBTS from Aug 2022) minus 21.3% a year of cost, fitted on real QPUX. The research found the dip edge comes mostly from those modelled years.
- **The research's walk-forward check failed.** Picking the best rule every 6 months using only the past lost 26% a year over 2 years, with a −94% fall. For CWEB the same kind of check held up; for QPUX it did not.

## How it decides

After each US close, from daily bars; orders go out at the next open:

- **Basket**: each day the average move of IONQ, RGTI, QBTS and QUBT from their previous close, for the open, high, low and close. **IBS** = (close − low) ÷ (high − low) of that basket bar.
- **Bitcoin check**: Bitcoin's (BTC-USD) **previous day's close** (UTC) above the average of the 100 closes before it. At the US close (04:00 Bangkok) the current Bitcoin day is not over yet, so the bot uses the last finished one.
- **Market check** (trend leg only): QQQ's close above its 200-day simple average.
- **Size** of the trend leg: 60% ÷ QPUX's 20-day volatility a year (standard deviation of daily % changes × √252), at most 100%. It is resized only on a move of 5 points or more.
- **RSI(2)**: Wilder's RSI over 2 days on QPUX's closes.
- **Money in QPUX** = min(100%, 0.4 × dip + 0.5 × trend size + 0.25 × RSI). Example: trend size 30% and a dip day gives 0.5 × 30% + 0.4 = 55%.
- **Orders**: the next open, 5 lots 1 minute apart. Between signals the holding is traded back to its target when it drifts 5 points (the rebalance band).

TradingView: QPUX daily with *Moving Average* 50 and 5 and *RSI* length 2; QQQ with *Moving Average* 200; BTCUSD daily with *Moving Average* 100 (the bot compares the previous day's close with the average of the 100 closes before it).

## Backtest results

These are from the bot's own code for this strategy (type `quantum_mix`) on Yahoo daily prices to 25 Nov 2026:

- Decided at the close, traded at the next open, Webull's real fee (0.11% per buy and per sell). Cash earns nothing.
- The backtest starts on 20 Jul 2022, when the basket first has a 200-day average. **There is no 5- or 10-year result.**

| Period | **This strategy (Safe)** | Bitcoin check on the trend leg only | QPUX held | QQQ held |
|---|---|---|---|---|
| 1 year | **+30.2% / −6.8%** | +47.8% / −6.8% | −95.2% / −96.9% | +4.6% |
| 3 years | **+166% / −16.9%** | +178% / −19.8% | −4.5% / −99.0% | +18.4% |
| Since Jul 2022 (4.3 years) | **+124% / −23.3%** | +129% / −26.8% | −46.0% / −99.0% | +19.2% |
| Real QPUX only (Aug 2025 – Nov 2026) | **+122% / −6.8%** | | −95.1% | |

Each cell is the return a year (the 1-year cell is the total) / the worst fall.

- **The research's own numbers are lower over 1 year**: Safe +9.5% / −6.6%, 3 years +151% / −14%, 5 years +97% / −22%, real QPUX only +81%. The bot's code and a separate rebuild agree with each other, and both come out higher than the research on the 1-year return. The worst falls match. Trust the falls more than the returns.
- About 36 trades a year. It held QPUX on 27% of days, with 6% of its money on average.
- It was out all of 2022 (QQQ and the basket were below their averages, and Bitcoin was weak).

### Stress tests (Jul 2022 – Nov 2026, a year / worst fall)

| Test | **Safe** |
|---|---|
| Normal (fee 0.11% a side) | **124% / −23.3%** |
| Fee 0.50% a side (about the real cost with QPUX's spread) | 115% / −24.9% |
| Every order a day late | 71% / −28.4% |

Late orders cost much more than fees: a day late, the 1-year result falls from +30% to +20%, and the 3-year from 166% to 83% a year.

### Year by year

| Year | **Safe** | QPUX held (modelled before Aug 2025) | QQQ held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+30.2%** | −94.2% | +3.6% |
| 2025 | **+321%** | −70.8% | +20.8% |
| 2024 | +285% | **+5,154%** (modelled) | +25.6% |
| 2023 | **+59.9%** | −14.8% | +54.9% |
| 2022 (from Jul) | 0% (out) | −91.1% | −11.8% |

## What to expect

- **The Dashboard plans with 15% a year and a −40% fall**, not the backtest. The real history is 1.3 years, the rest is modelled, and the walk-forward check lost money. Raise it only after a year of real results.
- **It sits in cash most of the time**: 73% of days in the backtest. Since June 2026 Bitcoin has been under its 100-day average, so every leg has been out.
- **Fills matter.** QPUX trades thinly. The research found that buying at midday instead of the open cut the dip leg's 1-year result to −7%. Keep *Entries start* on "as soon as the market is open", and check the first Live fills against the open.
- **Now (after the 25 Nov 2026 close) it is out, in cash.**
  - Bitcoin 59,748 is 23% under its 100-day average 77,562.
  - The basket is 50% under its 200-day average.
  - QPUX (2.82) is far under its 50-day average (7.93), and QQQ is 7.3% under its 200-day average.

## Expected return

<!--expected:qpux_safe-->

How it is worked out: [Expected returns](#/docs/expected-returns). This strategy uses a deliberately low planning figure instead of its backtest, because its history is short and mostly modelled.

## Moving money to it

- It is the only strategy in **Quantum computing** (*What your money is in* shows it as its own group).
- Run the Webull test trade first. If Webull refuses QPUX, the strategy cannot trade on Live.
- Keep it small. A fund that fell 99% in a year can fall to nothing, and it can be closed.

*A backtest is a history, not a promise. This is not financial advice.*
