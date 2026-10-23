<!--{"title": "QLD regime", "group": "The strategies"}-->
# QLD regime

Strategy **F** of the *Strategy to beat QQQ* research (AI x Alpaca). After each US close, from QQQ's daily closes:

| State | Rule | Holds |
|---|---|---|
| 2x | QQQ > SMA200, SMA50 > SMA200, 20-day volatility < 30% | 100% QLD (99% with the buffer) |
| 0.5x | as 2x but volatility ≥ 30% | 25% QLD, 74% BIL |
| 1x | QQQ > SMA200 but SMA50 ≤ SMA200 | 50% QLD, 49% BIL |
| Off | QQQ ≤ SMA200 | 99% GLD |

Volatility is the standard deviation of the last 20 daily log returns, × √252. The bot trades only on a state change (about 6 a
year in 2016–2026) or when a holding drifts more than 10% from target. Orders start at the next market open.
