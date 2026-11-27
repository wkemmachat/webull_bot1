<!--{"title": "URAA · Uranium dip legs with a Cameco check (S1++)", "group": "The strategies"}-->
# URAA · Uranium dip legs with a Cameco check (S1++)

This strategy trades **URAA**, a 2x daily ETF on uranium miners and nuclear fuel companies. It reads its signals from **URA** (the 1x uranium ETF) and **CCJ** (Cameco, the largest uranium miner).

It is **Strategy 1++** of the URAA research (27 Nov 2026), the main pick after four rounds.

**It only holds URAA for a few days after sharp uranium dips**, about 6% of days, and is in cash the rest of the time. It holds the largest of three dip legs:

| Leg | Buy when (at the close) | Size | Sell |
|---|---|---|---|
| **A · dip in a strong uptrend** | URA's 50-day average is at least **3% above** its 200-day average, URA is above its close of a year ago, URA's **2-day RSI < 8**, **and** CCJ's 2-day RSI < 30 | **100%** | At the open after URA's first up close (a close above the one before), 5 closes at most |
| **B · sharp drop in an uptrend** | URA is above its 200-day average **or** above a year ago, URA fell **4% or more over 3 days**, its RSI2 < 10, **and** CCJ's RSI2 < 30 | **100%** | The same |
| **C · crash, any trend** | URA fell **8% or more over 3 days** and its RSI2 < 5 | **50%** | The same |

- **RSI2** is Wilder's 2-day RSI of the closes.
- **The Cameco check** (legs A and B) skips dips where Cameco itself isn't oversold. Since 2011 it skipped only 6 trades, which lost 9.7% on average.
- **Prices for the signals have dividends added back** (URA, CCJ).
- **Idle cash stays cash.** The research's T-bill parking did worse than cash at 0.25% per trade in the research itself, and URAA trades thinly.
- **Orders** go out at the next open, 5 lots 1 minute apart.

Added on 27 Nov 2026 **with no money** and LINE off. You allowed it on Live; run a **Webull test trade of URAA** first (Go-live checklist). The test trade also confirms that Webull Thailand lets you buy URAA.

## Backtest results

These are from the bot's own code for this strategy (type `three_leg_dips`) on Yahoo daily prices to 25 Nov 2026. Each order is decided at the close and traded at the next open, with Webull's real fee (0.11% per buy and per sell) and cash earning nothing.

**URAA listed on 26 Jun 2024.** Before then the backtest uses a **model of URAA**: 2 × URA's daily move minus 14% a year. That covers the fund's fee, its financing and the extra drag of a 2x fund on a choppy index; the research fitted this to the real fund. Because the strategy holds so rarely, the model's cost matters little. The backtest starts in Nov 2011, when URA has a year of history.

| Period | **S1++ (this strategy)** | Without the Cameco check (S1+) | URAA held* | URA held |
|---|---|---|---|---|
| 1 year | **+87.9% / −10.3%** | +73.0% / −10.3% | −68.7% / −85.2% | −33.9% / −56.7% |
| 3 years | **+66.5% / −10.3%** | +61.8% / −10.3% | −25.2% / −85.2% | +2.9% / −56.7% |
| 5 years | **+53.5% / −10.3%** | +50.9% / −10.3% | −20.3% / −85.2% | +5.4% / −56.7% |
| 10 years | **+30.0% / −11.0%** | +27.9% / −21.1% | −6.4% / −92.5% | +12.0% / −61.5% |
| Real URAA only (Jun 2024 –) | **+76.3% / −10.3%** | +70.3% / −10.3% | | |
| Since Nov 2011 | **+18.9% / −21.9%** | | −27.0% / −99.7% | −2.2% / −86.8% |

Each cell is the return a year (the 1-year cell is the total) / the worst fall. *URAA held uses the model before Jun 2024.

- **Research comparison:**

  | Period | Research | Bot |
  |---|---|---|
  | 1 year | +89.3% / −10.4% | +87.9% / −10.3% |
  | 10 years | 30.6% / −11.1% | 30.0% / −11.0% |
  | 2011–2016 (holdout) | −0.3% / −12.9% | −0.5% / −12.8% |
  | Real URAA only | 79.1% / −10.4% | 76.3% / −10.3% |

- **Worst falls:**
  - Over 10 years: Feb → Mar 2017 (−11%).
  - Since 2011: −21.9%, Apr 2014 → Mar 2017, **not back to that peak until Apr 2021**, seven years later.
- **Activity:** about 19 trades a year (about 10 round trips), 71% of round trips won. It held URAA on only 6% of days.
- **Where the return comes from:** leg A (dips in a strong uptrend) made most of it. Legs B and C add smaller gains in falling markets.

### Stress tests (10 years, a year / worst fall)

| Test | **Bot** | Research |
|---|---|---|
| Normal (fee 0.11% a side) | **30.0% / −11.0%** | 30.6% / −11.1% |
| Fee 0.25% a side | 26.8% / −11.9% | 27.3% (S1++ without T-bills) |
| Every order a day late | **6.1% / −40.2%** | 7.1% / −40.5% |

**Orders at the open are essential.** The trades last a day or two, and a day late almost all of the edge is gone.

### Year by year

| Year | **S1++** | URAA held* | URA held |
|---|---|---|---|
| 2026 (to 25 Nov) | **+90.6%** | −68.9% | −35.2% |
| 2025 | **+99.0%** | +88.3% | +67.2% |
| 2024 | **+12.2%** | −28.5% | −0.6% |
| 2023 | +13.3% | **+71.1%** | +46.3% |
| 2022 | **+41.1%** | −46.2% | −11.3% |
| 2021 | **+83.8%** | +71.2% | +57.6% |
| 2020 | +0.3% | **+51.6%** | +41.3% |
| 2019 | **0.0%** | −21.4% | −3.5% |
| 2018 | **+9.5%** | −51.1% | −22.1% |
| 2017 | +0.7% | 9.7% | **+19.4%** |
| 2016 | −10.3% | −20.4% | **−1.3%** |
| 2015 | **−2.8%** | −68.4% | −37.1% |
| 2014 | **+10.3%** | −52.4% | −22.5% |
| 2013 | **−1.4%** | −49.5% | −21.4% |
| 2012 | **+1.0%** | −48.2% | −18.6% |

From 2012 to 2020 it went nowhere (uranium's long bear market), but it avoided the −50% years of holding. Nearly all its gains came in the 2021–2026 uranium bull market.

## What to expect

- **Plan far lower than the backtest.**
  - The 10-year figure leans on 2021–2026. Since 2011 it made 18.9% a year.
  - The research's resampled 10-year histories had a median of 19.8% a year, and 1 in 10 was below 13%.
  - The expected return below uses **18.9% a year**.
- **Size for a −40% fall, not −11%.** On the Fukushima weekend (Mar 2011), URAA would have opened about −35% while the rules held a dip. The research's full history (1999–2026) has a −42.5% worst fall, and the expected return uses that.
- **Long idle spells.** It can go months without a trade, and years without making money (2012–2020).
- **Now (after the 25 Nov 2026 close) it is out, in cash:**
  - URA is in a downtrend: its 50-day average is 20.7% under its 200-day, it is down 32.9% over a year, and it is 38.3% under its 200-day average. So legs A and B can't buy.
  - Leg C (crash) bought half on 14 Oct and 20 Nov 2026, and both were sold the next day after an up close.
  - URA's RSI2 is 41.7, so there's no dip.

## Expected return

<!--expected:uraa_s1pp-->

How it is worked out: [Expected returns](#/docs/expected-returns).

## Moving money to it

- URAA trades about $1.2 million a day (median $1.0 million over the last 60 days), at $9.58 a share on 25 Nov 2026. Keep the money in it modest, and check the first fills against the open price.
- *What your money is in* shows it as its own **Uranium** group. It moves mostly apart from the tech, chip and gold strategies, so it genuinely spreads your risk. Because it is in cash about 94% of the time, the money in it mostly waits.

*A backtest is a history, not a promise. This is not financial advice.*
