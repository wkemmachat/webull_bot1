<!--{"title": "Buy zones: when to add money", "group": "The strategies"}-->
# Buy zones: when to add money

Every strategy spends time **below its last high** ("under water"). The bot measures, once a day after the US close, how deep
each strategy is below its own backtest high and compares it with all its days in the last **20 years** (the C2-7 baskets:
since 2016; gold and silver: the 2 years of backtest they have). Until 28 Oct 2026 the window was 10 years; 20 years is
stricter because the 2008 crash and the 2011–2016 falls count too, so the same depth gets a lower percentile. The research
table below was measured on 10 years.

| Colour | Zone | Meaning |
|---|---|---|
| Green · **▲ Buy zone** | 70th–80th percentile | Deeper under water than on 70–80% of its past days |
| Solid dark green · **▲▲ Strong buy zone** | 80th percentile or deeper | Deeper than on 80% of its past days: banner on Home and one LINE message |

The badge shows the percentile and how far below the high it is, for example **▲▲ Strong buy zone · 86th pct · −26%**. Hover it for the
70th / 80th / 90th percentile depths of that strategy. The LINE message comes once per dip; the next one only after the
strategy has climbed back above its 70th percentile. Turn it on or off in LINE alerts → "Strong buy zone".

## Why it can help (research, 27 Oct 2026)

The bot's own strategy code on TradingView prices, Webull's real fee. Buying on days in the zone, compared with any day,
over the last 10 years (12 months later: median return / share of times up):

| Strategy | Any day | 80–100 zone | Worst further fall after buying: any day → 90–100 |
|---|---|---|---|
| ROM Trend + RSI(2) | +55% / 96% | +74% / 100% | −38% → −23% |
| USD Trend + IBS-dip | +53% / 94% | +70% / 100% | −38% → −15% |
| 2x Semis regime | +57% / 85% | +77% / 98% | −46% → −17% |
| QLD regime | +42% / 87% | +65% / 94% | −37% → −15% |
| QLD + Trend + bear-dip | +46% / 83% | +52% / 96% | −43% → −19% |
| QLD Trend + IBS-dip | +35% / 97% | +35% / 100% | −27% → −14% |

Checked two stricter ways (from 2008, and with each day's zone set only from the days before it):

- **QLD regime, QLD + Trend + bear-dip, QLD Trend + IBS-dip:** held up in every test — up a year later 93–98% of the time,
  and smaller further falls.
- **2x Semis regime:** more often up, but returns no better than any day in the stricter test.
- **USD Trend + IBS-dip:** no better than any day from 2008 (2014–2016 kept sliding for 19 months).
- **ROM Trend + RSI(2):** excellent since 2016, but in 2008 a deep dip fell another 52%.

## How to use it

- It is a statistic, **not a promise**. Three months after buying in a dip, results were often no better: dips often go deeper
  first. The advantage showed at 6–12 months.
- Deep zones are rare (the 90–100 zone is 10% of days) and can be a year or more apart. Waiting with all the cash costs the
  gains of the waiting time.
- A sensible use: put part of the money in now and add the rest when a strategy turns **solid dark green** (Strong buy zone).
- The zone is about the strategy's backtest, not about your own entry price.

**Why green:** analyst ratings use green for Buy and dark green for Strong buy (for example Zacks), and Webull shows gains in green. Buy zone is a light green pill with a green edge; Strong buy zone is a solid dark-green pill, the strongest mark on the page, so it invites the eye first.
