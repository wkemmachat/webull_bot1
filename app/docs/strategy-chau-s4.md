<!--{"title": "CHAU · Half trend + half dip, yuan filter (S4)", "group": "The strategies"}-->
# CHAU · Half trend + half dip, yuan filter (S4)

This strategy trades **CHAU (Direxion Daily CSI 300 China A Share Bull 2X)**, a 2x ETF on the 300 largest companies listed in Shanghai and Shenzhen ("A-shares"). It reads its trend from **ASHR** (the 1x CSI 300 ETF) and **FXI** (large Chinese companies listed in Hong Kong), and its yuan filter from **USD/CNY**. CHAU has traded since April 2015, so the whole backtest runs on its real prices.

It is **S4** of the CHAU research (26 Nov 2026), kept after round 4 found nothing better.

| | Rule |
|---|---|
| **Yuan filter** (both halves) | Trade only while **USD/CNY** is below its **50-day average**, meaning the yuan is firm. When it turns off, both halves go to cash |
| **Trend half: 50%** | Hold while **ASHR's Supertrend (10, 2)** is up **and FXI** is above its **200-day average** |
| **Dip half: 50%** | After CHAU closes near its low (**IBS < 0.2**) while **CHAU** is above its **100-day average** and credit is healthy (**LQD ÷ IEF** above its 100-day average), buy. Sell at a close with **IBS > 0.8**, or after **5 closes** |
| **Otherwise** | Cash |

- **IBS** = (close − low) ÷ (high − low) of CHAU's day.
- **Supertrend** is the TradingView indicator (ATR 10, factor 2), read on ASHR's daily bars.
- The two halves add up: trend on and a dip open = 100%; only one = 50%.
- **Prices for the signals have dividends added back** (ASHR, FXI, CHAU, LQD, IEF), as in the research.
- **Yuan timing:** the bot uses **that day's** USD/CNY close, read at 16:05 New York. The yuan's onshore market closes at 15:30 UTC, before the US close, so that day's rate is already known. The research's numbers depend on this. With the previous day's close instead, the 10-year result drops from +288% to +253% (setting *Yuan: use the close of*).
- **Orders** go out at the next open, 5 lots 1 minute apart. A held position is traded back to its target after a 10-point drift.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of CHAU** first (Go-live checklist).

## Backtest results

These are from the bot's own code for this strategy (type `half_trend_dip`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing.

| Period | **S4 (this strategy)** | CHAU held | ASHR held |
|---|---|---|---|
| 1 year | **+9.4% / −3.8%** | −18.1% / −40.2% | −6.4% / −21.7% |
| 3 years | **+19.7% / −24.4%** | +4.6% / −59.9% | +7.9% / −33.1% |
| 5 years | **+14.3% / −24.4%** | −14.3% / −71.8% | −3.5% / −44.1% |
| 10 years | **+14.5% / −24.4%** | −1.1% / −78.6% | +2.7% / −51.3% |
| Since Sep 2015 | **+12.7% / −24.4%** | +1.2% / −78.6% | +3.4% / −51.3% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. Over 10 years S4 turned $1 into $3.88 (+288%), while CHAU held lost 11%.

- **Research comparison (totals):**
  - 10 years: research +291% / −23.2%; its plain share-and-cash account (what the bot does) +285% / −24.3%; bot **+288% / −24.4%**.
  - 5 years: research +93.4%, bot +95.2%. 3 years: research +74.0%, bot +71.5%. 1 year: research +9.7%, bot +9.4%.
- **The two halves (10 years, each alone at 50%):** trend half 11.5% a year / −23.8%; dip half 3.0% / −15.2%. The trend half carries most of the return and the worst fall.
- **Worst fall:** −24.4%, from 7 Oct 2024 to 1 May 2025 (trend half). It has not yet regained that Oct 2024 peak.
- **Activity:** about 29 trades a year, 53% of round trips won. It held CHAU on only 29% of days and was in cash the rest.

### Stress tests (10 years, a year / total / worst fall)

| Test | **Bot** | Research |
|---|---|---|
| Normal (fee 0.11% a side) | **14.5% / +288% / −24.4%** | +291% / −23.2% |
| Fee 0.30% a side | 11.3% / +191% / −25.4% | +189% |
| Every order a day late | 11.3% / +192% / −20.7% | +188% / −18.9% |
| Yuan: previous day's close | 13.4% / +253% / −24.1% | — |

It keeps most of its return with higher costs or late orders, unlike the 2x chip strategies.

### Year by year

| Year | **S4** | CHAU held | ASHR held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+8.2%** | −24.3% | −10.2% |
| 2025 | +18.0% | **+47.7%** | +27.0% |
| 2024 | **+34.4%** | +6.6% | +12.0% |
| 2023 | **+17.3%** | −28.3% | −12.5% |
| 2022 | **−3.5%** | −49.2% | −27.5% |
| 2021 | −4.8% | −2.8% | **−1.6%** |
| 2020 | +30.1% | **+72.0%** | +36.3% |
| 2019 | +34.0% | **+70.0%** | +36.5% |
| 2018 | **−2.7%** | −51.0% | −28.5% |
| 2017 | +23.5% | **+74.9%** | +33.5% |
| 2016 | **−1.2%** | −26.9% | −15.6% |
| 2015 (from Sep) | 0.0% | **+48.1%** | +21.0% |

It lags CHAU in strong up years (2017, 2019, 2020, 2025) and avoids most of the falls (2016, 2018, 2022, 2023, 2026).

## What to expect

- **A small, steady China slice, not a main strategy.** About 14–15% a year over 10 years, against 30–100% for the Nasdaq and chip strategies. It spends about 70% of days in cash.
- **Expect less live.** The rules were picked over three rounds on the same years. On other ETFs, rules picked this way kept 47–96% of their backtest return on years they were not picked on.
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - The yuan filter is on (USD/CNY 6.6640, below its average 6.6848).
  - ASHR's Supertrend is down (29.50 under its line 30.16), and FXI is 10.5% under its 200-day average, so the trend half is off.
  - CHAU is 20.8% under its 100-day average and credit is weak (LQD ÷ IEF 0.8% under its average), so no dips start.

## Expected return

<!--expected:chau_s4-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- **CHAU trades very little:** about $0.9 million a day over the last 60 days, at $15.67 a share on 25 Nov 2026. Keep the money in it small, and check the first fills against the open price. The bot's orders are limit orders.
- *What your money is in* counts it in the **China** group together with CWEB. CHAU is mainland A-shares and CWEB is China internet companies listed in Hong Kong and the US. They are related but not the same.

*A backtest is a history, not a promise. This is not financial advice.*
