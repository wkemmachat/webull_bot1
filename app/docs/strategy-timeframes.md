<!--{"title": "Daily vs 4h vs 2h bars", "group": "The strategies"}-->
# Daily vs 4h vs 2h bars (2x ETF strategies)

**Short answer: keep the 2x ETF strategies on daily bars.** Checking them on 4-hour or 2-hour bars made none of the six clearly
better, and four of them clearly worse. Tested 27 Oct 2026.

## What was tested

- **The bot's own strategy code** (the same code that trades), fed with TradingView bars of QQQ, SMH, IYW, QLD, USD, ROM and GLD.
  Each bar is treated like a "day": the bot decides at the bar's close and buys or sells at the **next bar's open**, paying
  Webull's real fee (0.11% of every buy and every sell). Cash earns nothing in this test, on every timeframe.
- Daily on the same data matches the server's Backtest tab within about one point a year (QLD regime 37.0% vs 36.4%, USD
  Trend + IBS-dip 57.1% vs 58.7%), so the comparison is fair.
- **Two ways to move a strategy to shorter bars:**
  - *Same numbers*: what you get by switching the TradingView chart to 4h or 2h. SMA200 becomes 200 four-hour bars (about
    100 days), RSI(2) covers 2 bars, IBS is measured on each 4-hour bar.
  - *Same time span*: the day windows are multiplied by the bars in a day (4h: ×2, so SMA200 → SMA400; 2h: ×4, SMA800), so the
    strategy looks at the same history but decides 2 or 4 times a day. The Supertrend width is scaled to match, and the
    volatility limits are measured the same way as on days.
- **History available:** TradingView keeps 4h bars from January 2016 (10 years) but 1h bars only from January 2023, so the 2h
  results (built from 1h bars exactly like TradingView's 2h chart) cover the last 3 years only.

## Results (a year / worst fall)

### 10 years (Nov 2016 – Oct 2026): daily vs 4h

| Strategy | **Daily (now)** | 4h, same numbers | 4h, same time span | Trades a year (daily / 4h same numbers / 4h same span) |
|---|---|---|---|---|
| QLD regime | **+37.0% / -36.6%** | +18.6% / -41.2% | +37.8% / -34.2% | 5.9 / 15.4 / 5.7 |
| 2x Semis regime | **+55.8% / -46.4%** | +22.5% / -61.4% | +46.3% / -56.6% | 8.7 / 22.4 / 8.9 |
| QLD + Trend + bear-dip | **+36.7% / -42.7%** | +30.1% / -42.0% | +41.8% / -46.6% | 5.6 / 19.0 / 9.8 |
| ROM Trend + RSI(2) | **+50.8% / -37.7%** | +33.2% / -42.4% | +42.5% / -51.6% | 5.0 / 22.2 / 8.0 |
| QLD Trend + IBS-dip | **+35.1% / -27.2%** | +8.8% / -48.7% | +17.4% / -42.3% | 25.1 / 58.2 / 50.2 |
| USD Trend + IBS-dip | **+57.1% / -38.3%** | +4.9% / -72.7% | +17.8% / -62.8% | 62.4 / 128.4 / 123.0 |

### 3 years (Nov 2023 – Oct 2026): daily vs 4h vs 2h

| Strategy | **Daily (now)** | 4h, same numbers | 4h, same time span | 2h, same numbers | 2h, same time span |
|---|---|---|---|---|---|
| QLD regime | **+44.2% / -26.6%** | +22.5% / -26.6% | +39.6% / -30.0% | +23.0% / -29.4% | +41.1% / -26.1% |
| 2x Semis regime | **+108.0% / -37.8%** | +24.5% / -61.4% | +92.7% / -49.8% | +56.5% / -54.7% | +103.3% / -43.4% |
| QLD + Trend + bear-dip | **+50.7% / -26.1%** | +36.5% / -23.8% | +50.7% / -26.1% | +33.2% / -24.6% | +41.1% / -28.8% |
| ROM Trend + RSI(2) | **+53.3% / -31.7%** | +43.8% / -42.4% | +36.9% / -49.9% | +34.5% / -40.2% | +49.5% / -45.5% |
| QLD Trend + IBS-dip | **+51.9% / -21.8%** | +2.0% / -29.9% | +26.7% / -20.5% | -6.5% / -41.3% | +3.8% / -37.7% |
| USD Trend + IBS-dip | **+67.8% / -32.5%** | -3.7% / -71.3% | +21.4% / -62.8% | +4.3% / -60.1% | +22.0% / -52.7% |

### Sharpe ratio (10 years; 3 years for 2h)

| Strategy | Daily | 4h same numbers | 4h same span | 2h same span (3y) | Daily (3y) |
|---|---|---|---|---|---|
| QLD regime | **1.16** | 0.72 | 1.17 | 1.16 | 1.26 |
| 2x Semis regime | **1.15** | 0.67 | 1.0 | 1.46 | 1.55 |
| QLD + Trend + bear-dip | **1.05** | 0.95 | 1.14 | 1.12 | 1.29 |
| ROM Trend + RSI(2) | **1.21** | 0.93 | 1.02 | 1.07 | 1.17 |
| QLD Trend + IBS-dip | **1.27** | 0.46 | 0.75 | 0.28 | 1.67 |
| USD Trend + IBS-dip | **1.25** | 0.33 | 0.6 | 0.66 | 1.39 |

### By period: daily vs 4h same time span (a year)

| Strategy | 2016–19 daily / 4h | 2020–22 daily / 4h | 2023–26 daily / 4h | last 12 months daily / 4h |
|---|---|---|---|---|
| QLD regime | +35.8% / +40.2% | +26.5% / +28.4% | +45.5% / +42.7% | +29.1% / +20.6% |
| 2x Semis regime | +42.3% / +43.6% | +18.1% / +8.4% | +106.8% / +86.5% | +52.1% / +50.4% |
| QLD + Trend + bear-dip | +33.0% / +40.8% | +27.3% / +32.3% | +47.0% / +50.1% | +20.0% / +16.1% |
| ROM Trend + RSI(2) | +53.7% / +49.1% | +41.5% / +36.6% | +54.9% / +42.0% | +21.8% / +32.0% |
| QLD Trend + IBS-dip | +19.4% / +19.0% | +31.0% / +3.7% | +52.3% / +27.1% | +48.2% / +23.9% |
| USD Trend + IBS-dip | +42.2% / +21.5% | +45.2% / +0.5% | +80.3% / +29.1% | +66.1% / +19.9% |

## What this means

- **"Same numbers" (switching the chart) is worse for every strategy.** It trades 2–4 times as often and is fooled by moves
  inside the day: QLD regime falls from 37% to 19% a year, 2x Semis from 56% to 23%.
- **The IBS-dip strategies only work on daily bars.** IBS (where the close sits in the day's range) captures how a whole
  US session ends; a 4-hour or 2-hour bar does not carry that information. Even with no fees at all, USD Trend + IBS-dip on
  4h made 24–38% a year against 70% daily.
- **"Same time span" mostly ties or loses.** QLD regime is the same (37.8% vs 37.0%), 2x Semis and ROM lose 8–10 points a year
  with deeper falls (−57% and −52% vs −46% and −38%).
- **The one exception is QLD + Trend + bear-dip on 4h, same time span:** about 4–5 points a year more over 10 years (41.8% vs
  36.7%; over 15 nearby settings the middle result was 38.9% vs 34.8%). But its worst fall is deeper (−46.6% vs −42.7%), the
  gain came in 2016–2022, and it was behind daily over the last 2 years. Not enough to change a working strategy; it stays a
  research note.
- **2h** (3 years) is no better than daily for any strategy. 2x Semis on 2h same span came closest (103% vs 108% a year).
- **Gold and silver** already decide on 4-hour gold and silver futures bars (that is how their research was done); nothing
  changes for them.

## Why daily wins here

1. These strategies were designed and tuned on daily closes. Moving them changes the rule, not just the speed.
2. Shorter bars see more false turns: more trades, more fees, and more times sold just before a rebound.
3. A good part of US stock returns arrives overnight. A strategy that reacts during the day sells into intraday dips and
   misses the next morning's gap up more often.

## If you still want to try 4h

Only QLD + Trend + bear-dip is worth a look, in **paper**, next to the daily version for a few months. It would need the bot to
read 4-hour QQQ bars and decide at about 01:30 and 04:00 Bangkok (13:30 and 16:00 New York), which is a code change. Ask first;
the evidence today does not justify it.
