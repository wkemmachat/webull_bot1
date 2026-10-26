<!--{"title": "All strategies compared", "group": "The strategies"}-->
# All strategies compared

| Strategy | A year (10 years) | Worst fall | Sharpe | Last year | Risk |
|---|---|---|---|---|---|
| QLD + Trend + bear-dip | **+36.4%** | −42.6% | 0.98 | +22.7% | high |
| QLD regime | **+36.4%** | −36.6% | 1.07 | +32.0% | high |
| 2x Semis regime | **+55.9%** | −46.4% | 1.10 | +61.1% | very high |
| C2-7 Momentum 1x | **+31.5%** | −19.8% | 1.30 | +45.0% | medium |
| C2-7 Momentum 2x | **+53.8%** | −33.3% | 1.27 | +93.9% | high |
| QLD Trend + IBS-dip | **+34.4%** | −27.2% | 1.25 | +51.1% | high |
| USD Trend + IBS-dip | **+58.7%** | −38.1% | 1.22 | +84.6% | very high |
| Gold #1 · Supertrend + ADX | +7.7% † | −13.2% † | — | +36.1% | medium |
| Gold #2 · Supertrend 30/2.5 | +9.0% † | −13.4% † | — | +29.5% | medium |
| Silver #1 · Donchian 30/15 | +12.7% † | −33.9% † | — | −13.1% | very high |
| Silver #2 · Supertrend 10/3 | +14.4% † | −34.3% † | — | +10.9% | very high |

Bot backtests on real prices, 26 Oct 2026. C2-7 Momentum 2x needs single-stock 2x ETFs, which Webull Thailand allows only from
50M THB: on your account it works like C2-7 Momentum 1x (see its page). † Gold and silver: the research's 10-year ETF test, lowered by what Webull's real fee costs in the bot's 2-year backtest (Yahoo has only 2 years of hourly futures prices). QQQ held over the same 10 years: about 20% a year, worst fall −35%.

| Strategy | Holds | Since 2007 (or its start): a year / worst fall | Last 5 years |
|---|---|---|---|
| QLD + Trend + bear-dip | QLD or BIL | +31.7% / −42.6% (from 2007) | +32.9% |
| QLD regime | QLD / BIL / GLD | +25.5% / −39.6% (from 2007) | +28.2% |
| 2x Semis regime | USD / BIL / GLD | +35.4% / −49.1% (from 2007) | +67.7% |
| C2-7 Momentum 1x | 7 Nasdaq stocks or GLD+SGOV | +31.5% / −19.8% (from 2016) | +43.5% |
| C2-7 Momentum 2x | 7 stocks via 2x ETFs or GLD+SGOV | +53.8% / −33.3% (from 2016) | +76.1% |
| QLD Trend + IBS-dip | QLD (vol-capped) or GLD + cash | +29.1% / −30.6% (from 2007) | +44.8% |
| USD Trend + IBS-dip | USD (vol-capped, 100% on dips) or GLD + cash | +36.7% / −51.5% (from 2007) | +76.7% |
| Gold #1 · Supertrend + ADX | UGL or cash | see the strategy page | — |
| Gold #2 · Supertrend 30/2.5 | UGL or cash | see the strategy page | — |
| Silver #1 · Donchian 30/15 | AGQ or cash | see the strategy page | — |
| Silver #2 · Supertrend 10/3 | AGQ or cash | see the strategy page | — |

## How to read this

- **A year** is the compound yearly return; **worst fall** is the biggest drop from a previous high. A −40% fall means $10,000
  became $6,000 for a while: decide first which falls you can sit through, then look at the returns.
- **Sharpe** is return per unit of risk (above T-bills): above 1 is very good for a single strategy.
- Gold and silver use the research's 10-year numbers (Yahoo has only 2 years of hourly futures prices).
- All numbers are backtests: the rules were chosen on this history, so the future will usually be worse.
- For planning, the bot takes 30% off the expected returns (research, lowered for Webull's real fee) and shows what your own split of money could become in 1–3 years:
  [Expected returns](#/docs/expected-returns) (Dashboard → *Expected return*).

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
