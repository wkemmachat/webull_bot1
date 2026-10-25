<!--{"title": "All strategies compared", "group": "The strategies"}-->
# All strategies compared

| Strategy | A year (10 years) | Worst fall | Sharpe | Last year | Risk |
|---|---|---|---|---|---|
| QLD + Trend + bear-dip | **+37.3%** | −42.3% | 1.00 | +23.3% | high |
| QLD regime | **+37.2%** | −35.9% | 1.09 | +32.5% | high |
| 2x Semis regime | **+57.3%** | −45.9% | 1.12 | +62.8% | very high |
| C2-7 Momentum 1x | **+34.0%** | −19.5% | 1.39 | +49.2% | medium |
| C2-7 Momentum 2x | **+56.8%** | −33.0% | 1.32 | +99.6% | high |
| QLD Trend + IBS-dip | **+34.5%** | −29.6% | 1.11 | +49.8% | medium |
| USD Trend + IBS-dip | **+62.5%** | −37.0% | 1.28 | +79.6% | high |
| Gold #1 · Supertrend + ADX | +10.3% † | −13.2% † | — | +38.9% | medium |
| Gold #2 · Supertrend 30/2.5 | +11.5% † | −13.4% † | — | +32.2% | medium |
| Silver #1 · Donchian 30/15 | +15.5% † | −33.9% † | — | −11.1% | very high |
| Silver #2 · Supertrend 10/3 | +17.2% † | −34.3% † | — | +13.4% | very high |

Bot backtests on real prices, 25 Oct 2026. † Gold and silver: the research's 10-year ETF test (Yahoo has only 2 years of hourly futures prices). QQQ held over the same 10 years: about 20% a year, worst fall −35%.

| Strategy | Holds | Since 2007 (or its start): a year / worst fall | Last 5 years |
|---|---|---|---|
| QLD + Trend + bear-dip | QLD or BIL | +33.0% / −42.3% (from 2007) | +34.2% |
| QLD regime | QLD / BIL / GLD | +26.6% / −39.1% (from 2007) | +28.8% |
| 2x Semis regime | USD / BIL / GLD | +36.7% / −46.7% (from 2007) | +69.4% |
| C2-7 Momentum 1x | 7 Nasdaq stocks or GLD+SGOV | +34.0% / −19.5% (from 2016) | +46.7% |
| C2-7 Momentum 2x | 7 stocks via 2x ETFs or GLD+SGOV | +56.8% / −33.0% (from 2016) | +80.0% |
| QLD Trend + IBS-dip | QLD (vol-capped) or GLD+BIL | +30.0% / −29.6% (from 2007) | +44.9% |
| USD Trend + IBS-dip | USD (vol-capped, 100% on dips) or GLD+BIL | +41.7% / −43.2% (from 2007) | +81.3% |
| Gold #1 · Supertrend + ADX | UGL or SGOV | see the strategy page | — |
| Gold #2 · Supertrend 30/2.5 | UGL or SGOV | see the strategy page | — |
| Silver #1 · Donchian 30/15 | AGQ or SGOV | see the strategy page | — |
| Silver #2 · Supertrend 10/3 | AGQ or SGOV | see the strategy page | — |

## How to read this

- **A year** is the compound yearly return; **worst fall** is the biggest drop from a previous high. A −40% fall means $10,000
  became $6,000 for a while: decide first which falls you can sit through, then look at the returns.
- **Sharpe** is return per unit of risk (above T-bills): above 1 is very good for a single strategy.
- Gold and silver use the research's 10-year numbers (Yahoo has only 2 years of hourly futures prices).
- All numbers are backtests: the rules were chosen on this history, so the future will usually be worse.

## Which ones move together

| Group | Strategies | Why |
|---|---|---|
| Nasdaq | QLD regime, QLD + Trend + bear-dip, QLD Trend + IBS-dip, C2-7 Momentum 1x/2x | same index, SMA200-type signals: in and out at similar times (QLD Trend + IBS-dip the least: monthly correlation about 0.7) |
| Semiconductors | 2x Semis regime, USD Trend + IBS-dip | both hold USD; 2x Semis reads SMH, USD Trend + IBS-dip reads USD itself (monthly correlation about 0.6) |
| Gold | Gold #1, Gold #2 | same futures, similar Supertrend: usually both long or both flat |
| Silver | Silver #1, Silver #2 | same futures; silver crashes hit both |

Spreading money **across groups** (Nasdaq + gold + some silver) lowers the total worst fall; adding more strategies **inside**
one group mostly adds the same bet.

## Before giving a strategy real money

1. Read its page: rules, worst fall, risks.
2. Open its **Backtest** tab and look at the worst year and the longest time below a high.
3. **Go-live → Test trade** its ETFs on your Live account (leveraged ETFs need Webull's permission; some may not be offered in Thailand).
4. Start small, compare the bot's Trades with Webull's order history for 2 weeks, then add money step by step.

*This is information about how the strategies behaved in the past, not investment advice.*
