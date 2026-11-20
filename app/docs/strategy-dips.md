<!--{"title": "Buy zones: when to add money", "group": "The strategies"}-->
# Buy zones: when to add money

Every strategy spends time **below its last high** ("under water"). Once a day after the US close the bot measures how deep
each strategy is below its own backtest high and compares it with its days in the last **20 years** (the C2-7 baskets: since
2016; the 4-hour metals: the 2 years of backtest they have).

| Pill | Zone | Meaning |
|---|---|---|
| Green · **▲ Buy zone** | 70th–84th percentile | Cheaper than usual |
| Solid dark green · **▲▲ Good time to add** | 85th percentile or deeper | The add window: a strategy whose past deep falls were followed by gains |
| Grey · **▼ Deep fall** | 70th or deeper | The same depth, but in this strategy's backtest deep falls kept falling: no reason to add |

Until 20 Nov 2026 the dark green pill started at the 80th percentile ("Strong buy zone") for every strategy, gold and silver
included.

## Good time to add money? (20 Nov 2026)

Each strategy's **Overview** starts with a card that answers this in four steps, from its own backtest:

1. **Where it is now**: a bar from "at its high" through "cheap" (70th) to "add money" (85th+), with today on it.
2. **What happened the last times it got this cheap**: one bar per past time it reached the 85th percentile, showing how
   much it was up a year later (for example ROM · Split 2C: 30 of 30 were up, typically +51%).
3. **If you add $1,000 on a day like this**: a bad year (1 in 10), a typical year and a good year a year later, next to the
   same on a normal day, and how far it typically dipped first.
4. **The rule**: add *extra* money you keep aside; don't hold back money you'd add anyway — for the Nasdaq/S&P strategies waiting for a
   dip was better less than half the time (40–48%) and cost 1–6% on average.

The card opens by itself when the strategy is in the add window; otherwise it is one line ("Not a special time to add" or
"No add-money signal for this strategy") with **Show why**.

**Which strategies:** the verdict compares days in the zone with any day of the same backtest:

- **Good time** — up a year later more often, by more, and a smaller fall first; at least 9 of 10 of the times it got there
  were up (ROM · Split 2C, QLD · Split 2C, QLD Trend + bear-dip + Vol, ROM · Trend + Vol, DDM, RXL Ichimoku, C2-7).
- **OK, safer** — more often up and a smaller fall first, but not by more (USD · Trend split).
- **Mixed** — about like any day (USD Trend + IBS-dip, SSO MACD): the card shows the odds, no LINE message.
- **No signal** — worse than any day, or fewer than 6 past falls to judge (USD · SMH, gold, silver).

Each day is ranked only against the days before it (3 years of warm-up, so the odds start in 2009): no hindsight.

**Dashboard:**

- **"… just got cheap"** — a green alert at the top when a strategy entered the add window in the last week (the same day
  the LINE message goes out): how far below its high, its record as dots ("30 of 30 were higher a year later"), and
  **Add money to it** (the usual Add money form with that strategy picked), **Why?** (its page) and **Dismiss**. Several in
  the same week share one alert.
- **"Good places for extra money now"** — a card per strategy in the window (Good time and Safer, the newest first, then the
  deepest): what $1,000 typically became a year later, one dot per past time (green = up a year later), how deep it is and
  how much you have in it, and an **Add money** button. "Mixed" strategies get a "Less sure" line under the cards.
  **Hide** folds it to one line, and it opens again by itself when another strategy enters the window. Dismiss and Hide are
  remembered in this browser.
- **Menu badge** — the green number next to Dashboard is how many strategies are in the window (stopped ones not counted).

**LINE "Good time to add money"** (LINE alerts → "Good time to add money"): once per fall, when a Good-time or OK-safer
strategy reaches its 85th percentile, armed again only after it climbs back above its 70th. It carries the same odds: the
times it got there and how many were up a year later, $1,000 → typical and bad year, and the dip to expect first. Strategies
that are stopped get no message.

**Honest check:** these are backtests of strategies picked on these same years, so real results will be less tidy; and at
the 100th percentile no past day was quite this deep. History, not a promise.

## Earlier research (27 Oct 2026)

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
- A sensible use: put the money you planned in now, and keep extra money aside for the ▲▲ Good time to add pill.
- The zone is about the strategy's backtest, not about your own entry price.

**Why green:** analyst ratings use green for Buy and dark green for Strong buy (for example Zacks), and Webull shows gains in green. Buy zone is a light green pill with a green edge; Strong buy zone is a solid dark-green pill, the strongest mark on the page, so it invites the eye first.
