<!--{"title": "ROM · Split 2C (today's best 67% + ROC252 & credit 33%)", "group": "The strategies"}-->
# ROM · Split 2C (today's best 67% + ROC252 & credit 33%)

Trades **ROM (ProShares Ultra Technology, 2x US tech)** from the 1x tech ETF **IYW**. The money is **split into two legs**, each a complete strategy with its own rules:

- **67%** follows exactly the rules of [ROM · Trend + Vol + RSI & IBS dips](#/docs/strategy-rom-vol-ibs), the best ROM strategy before this one. Its part parks in cash.
- **33%** follows a different rule: IYW higher than a year ago and **credit OK**, with dip buys. Its part parks half in GLD.

The two legs are set back to 67% / 33% every January. The share in ROM is the sum of the legs that are in: 0, about a third, about two-thirds or all.

This is **split C of round 2** of the research *Strategy research and stress tests* (15 Nov 2026), the ROM pick after three rounds. It keeps today's best 10-year return and cuts the worst fall from −36% to −26%. It passed 9 of 11 stress tests against today's best, and round 3 found nothing better for ROM.

Added on 15 Nov 2026 **with no money**. It trades only after you move money to it (Money → Move), and its LINE alerts start off: turn LINE on in the strategy when you give it money.

## The two legs

After each US close, from the daily bars of IYW, ROM, LQD and IEF. The bot only decides on days where all of them have a closed bar.

| | **Leg 1 · 67%** · ROM · Trend + Vol + RSI & IBS dips | **Leg 2 · 33%** · ROC252 + credit + 3-down & IBS dips |
|---|---|---|
| Trend | IYW close above its **EMA150** | IYW close above its close **252 trading days ago** (ROC252 > 0) |
| Gate | **Calm**: IYW's 20-day volatility below its 90th percentile of 252 days | **Credit OK**: LQD ÷ IEF on dividend-adjusted closes above its 100-day average |
| In the trend | 100% ROM | 100% ROM |
| Trend up, gate shut | out | out |
| Dip trade (trend off) | RSI(2) < 5, sold on a close above SMA5 | **3 lower closes in a row**, sold on a close above SMA5 |
| One-day dip (trend off) | ROM IBS < 0.15 | ROM IBS < 0.20 |
| When out | cash | 50% GLD + 50% cash |

- IBS = (close − low) ÷ (high − low). A one-day dip is held from the next open to the following open.
- **The credit check** asks whether corporate bonds (LQD) are holding up against Treasuries (IEF). It uses dividend-adjusted prices, as the research did and as [USD · Trend split](#/docs/strategy-usd-trend-split) does. LQD pays more interest than IEF, so plain prices would make the check look weak far too often.
- Leg 2 is built from the bot's existing *Trend + calm gate* type with three new options: *Trend average type: ROC*, the *Credit check*, and *Dip trade: opens on 3DOWN*. Each leg's settings are in *Parameters → Legs (JSON)*.

## How the legs are added up

- Each leg is a sub-account. **On the first trading day of each year they are set back to 67% / 33%.** In between, a leg that holds ROM grows or shrinks with it, as separate sub-accounts would.
- The target is each leg's own target weighted by its sub-account's value, with a 1% cash buffer:
  - Both in: 99% ROM.
  - Only leg 1 in: about 66% ROM, plus 16% GLD from leg 2's parking.
  - Only leg 2 in: about 33% ROM; leg 1's part stays in cash.
  - Both out: about 16% GLD, the rest in cash.
- The target changes only when a leg's own target changes or a new year starts. Orders start at the next open, 10 lots 5 minutes apart. Between changes it trades only when a holding drifts more than 20 points from its target (the rebalance band).

## When it trades

About **35 trades a year** over 10 years, against 20 for ROM · Trend + Vol + RSI & IBS dips: the two legs turn on and off separately, plus their dips and GLD. It held ROM on about 87% of days (counting a part-held day by its share).

Both legs buy for **one day** after a dip, so the orders need the **next open**. Keep *Entries start* on "as soon as the market is open" (the default for this type).

## Backtest results

The bot's own code for this strategy (type `split_mix`, both legs `trend_gate`) on Yahoo daily prices to 13 Nov 2026. It decides at the close, trades at the next open and pays Webull's real fee (0.11% per buy and per sell); cash earns nothing.

The bot reproduces the research: 60.9% / −26.3% over 10 years against 60.7% / −26.3%. Calendar years are within 1 point in 17 of 20 years; the largest gap is 3.2 points, in 2020. Leg 2 alone matches the research's implied yearly returns within 0.2 points on average. The **Backtest** tab shows the same on the server.

| Period | **This strategy** | ROM · Trend + Vol + RSI & IBS dips | ROM Trend + RSI(2) | ROM held |
|---|---|---|---|---|
| 1 year | +22.4% / **−26.3%** | +12.1% / −36.4% | +8.5% / −37.1% | **+24.3%** / −37.3% |
| 3 years | **+53.9% / −26.3%** | +41.6% / −36.4% | +38.6% / −37.1% | +37.0% / −48.1% |
| 5 years | **+43.6% / −26.3%** | +37.6% / −36.4% | +33.4% / −37.1% | +13.4% / −67.5% |
| 10 years | **+60.9% / −26.3%** | +59.6% / −36.4% | +48.9% / −37.7% | +35.8% / −67.5% |
| Since 2006 | **+38.7% / −34.6%** | +37.4% / −40.6% | +27.6% / −65.1% | +21.9% / −83.4% |

Each cell is the return a year / worst fall. 10-year Sharpe: 1.43 for this strategy, 1.31 for ROM · Trend + Vol + RSI & IBS dips.

Leg 2 alone made 58.9% / −31.0% over 10 years and 44.0% in the last year. Its trend and its credit check differ from leg 1's, so the two legs are often out at different times. That is where the smaller fall comes from.

### Stress tests (10 years, a year / worst fall)

| Test | **This strategy** | ROM · Trend + Vol + RSI & IBS dips | ROM Trend + RSI(2) |
|---|---|---|---|
| Normal | **60.9% / −26.3%** | 59.6% / −36.4% | 48.9% / −37.7% |
| Fee 0.25% a side | **55.8% / −29.1%** | 55.2% / −36.4% | 47.9% / −37.8% |
| Fee 0.50% a side | 47.0% / −39.4% | **47.7%** / −42.3% | 46.1% / **−38.0%** |
| Every order a day late (bot test) | **48.5% / −28.2%** | 45.4% / −41.2% | 47.6% / −40.1% |
| Every order a day late (research test) | 45.3% | 43.1% | **47.2%** |

It does as well as or better than today's best in every test but the 0.50% fee, where it makes 0.7 points a year less. With orders a day late it keeps a −28% worst fall against −41%. ROM Trend + RSI(2), which trades about 5 times a year, is the least hurt by late orders, but its worst fall since 2006 is −65%. In the research's typical shuffled decade the split made 40.1% / −38.4% against 39.2% / −43.5%.

### Year by year

| Year | **This strategy** | ROM · Trend + Vol + RSI & IBS dips | ROM held |
|---|---|---|---|
| 2026 (to 13 Nov) | **+24.7%** | +12.2% | +24.4% |
| 2025 | **+86.7%** | +60.4% | +35.6% |
| 2024 | +35.5% | **+36.4%** | +31.6% |
| 2023 | +83.6% | +113.1% | **+130.7%** |
| 2022 | **+7.3%** | +0.6% | −63.9% |
| 2021 | +71.2% | +64.0% | **+77.8%** |
| 2020 | +155.9% | **+182.8%** | +80.4% |
| 2019 | +96.3% | +93.8% | **+102.1%** |
| 2018 | +14.2% | **+19.7%** | −9.9% |
| 2017 | +75.5% | +74.3% | **+81.1%** |
| 2016 | **+27.7%** | +18.0% | +23.5% |
| 2015 | **+12.0%** | +4.7% | +3.6% |
| 2014 | +8.6% | +4.8% | **+39.0%** |
| 2013 | +31.0% | +34.7% | **+57.0%** |
| 2012 | +24.5% | **+27.0%** | +19.2% |
| 2011 | −8.2% | −12.0% | **−7.3%** |
| 2010 | +18.4% | **+25.0%** | +19.9% |
| 2009 | +100.9% | +117.5% | **+146.4%** |
| 2008 | **+26.3%** | +7.5% | −73.3% |
| 2007 | +18.6% | +19.3% | **+22.0%** |

Ahead of ROM · Trend + Vol + RSI & IBS dips in 7 of the last 11 calendar years (2016 to 2026). Behind in 2018, 2020, 2023 and 2024, by the most in the big up years 2020 and 2023. The one losing year since 2007 was 2011 (−8.2%, against −12.0%).

## What to expect

- **Plan with less than the backtest.** The research's walk-forward check picked rules using only the past and held them for the next year. On ROM that made about **43% a year** with a −30% worst fall over 10 years, whichever rule is used. ROM · Trend + Vol + RSI & IBS dips' own 59.6% is probably optimistic too. What held up best out of sample was the smaller fall. The Dashboard's expected return uses 61.0% a year (Oct 2016 – Oct 2026) minus the planning haircut.
- **It trails in strong rallies**: the 33% leg sits out while credit is weak and parks half in gold, as in 2020 and 2023.
- **Credit has been weak in 2026.** Leg 2 was held back by the credit check on 112 days, against 105 in 2025 and 37 in 2024. It held 64% of the money in ROM on average (72% in 2025, 81% in 2024).
- **Now (after the 13 Nov 2026 close) it is out.** Leg 1: IYW is below its EMA150 and jumpy. Leg 2: IYW is 14% above its close a year ago, but credit is weak (LQD ÷ IEF 1.1418 against its average 1.1431). It would hold about 21% GLD and the rest in cash.

## Expected return

<!--expected:rom_split_2c-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

Two-thirds of this strategy *is* ROM · Trend + Vol + RSI & IBS dips. Money in both would hold mostly the same position twice, so treat it as a **replacement**, not an addition. To switch, move the money from ROM · Trend + Vol + RSI & IBS dips into this strategy in one step (Money → Move), ideally on a day when both are out, as now, so no ROM is sold and bought back. ROM Trend + RSI(2) is a different rule and can stay as it is.

*A backtest is a history, not a promise. This is not financial advice.*
