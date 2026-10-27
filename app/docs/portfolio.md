<!--{"title": "Portfolio and idle cash", "group": "Using the app"}-->
# Portfolio and idle cash

## Idle cash box (each strategy page)

A strategy can hold cash it does not use yet. When it does, a box at the top of its page says how much, why, and what
would happen if you act:

- **Waiting for a buy signal**: money you added with *Wait for the next buy signal*. It stays cash until the strategy's
  next BUY (for a regime: a step up, e.g. off → 1x or 0.5x → 2x). **Invest now** puts it to work at today's target.
- **Left over inside the rebalance band**: a small top-up (e.g. $150 on a $2,500 strategy = 6%) is smaller than the
  strategy's rebalance band (10% for most), so the bot leaves it as cash until the next signal or a bigger gap.
  **Top up now** buys toward today's target with that cash only; it never sells anything.

The box also shows the strategy's **next buy signal** in plain words with today's numbers, its **Buy zone** pill when it is
in one, and roughly what the button would buy (e.g. "≈1.92 USD"). Both buttons make a normal split plan from the next check
(limit orders, fractional shares when they are on). Leave it alone and nothing changes. C2-7 baskets never top up (equal
money per stock); their cash joins at the weekly list change.

## Portfolio page (sidebar → Portfolio)

All the money in the mode you are looking at, together:

- **Mix now vs your plan**: each strategy's share next to the ratio you saved (Expected return → ratio planner, or *Try a
  mix → Save as my plan* here). Plan = (money in strategies + bot unassigned) × ratio. **Moves** that close the gaps are
  listed (bot unassigned first, then from the most over-weight strategy); each button opens the usual Money dialog filled in.
  Nothing moves until you confirm there. Gaps under $50 are ignored.
- **What the money holds**: by market across all strategies (two strategies holding USD both count as semiconductors 2x;
  T-bills, gold, cash and bot unassigned shown separately).
- **Your mix in the backtest**: today's split, each strategy's money growing on its own as in the bot (never rebalanced),
  from each strategy's weekly backtest at the real fee (the expected-returns check). 10 years or all years. Shows a year,
  worst fall, longest under water, worst 12 months and return ÷ fall. Strategies with a much shorter backtest (the metals:
  about 2 years of 4H futures) are left out and named, so they do not cut the whole history short.
- **Try a mix**: change the percentages and the backtest compares your split now (solid) with the new one (dashed).
  **Save as my plan** stores it as the ratio plan. Nothing is bought or sold.
- **Which strategies fall together**: correlations of weekly backtest returns. 1 = they move (and fall) together.
- **Real result so far**: time-weighted since the first money (adding or taking out money is not a gain or loss), with the
  worst fall so far.

A backtest is a history, not a promise.

## Weekly report and trading costs

Every **Saturday from 09:00 Bangkok** (after Friday's US close) LINE gets a weekly report for each mode that is on (Live
and Webull test; Paper only when no real mode is on). LINE alerts → *Weekly report* turns it off.

- **Real vs backtest this week**, per strategy: the real week, time-weighted (money added or taken out is not a gain or
  loss), next to the same strategy's backtest over the same days. A strategy whose money started during the week is
  compared from that day. The **gap** shows whether Live follows the backtest; small gaps are normal (fill prices, cash
  waiting for a signal, the weekly ranking of the baskets).
- **Trading this week** and **since the first Live order**: fees Webull charged, and every fill against that day's
  **opening price**, where the daily backtests buy and sell. That difference is the real cost of trading on top of the
  backtest (spread, limit offset, timing, retries); + = cost. The costliest fill of the week is named. For the 4H metals
  strategies, which trade at other times, it is a rough guide.

The Portfolio page shows the latest report, the earlier weeks, trading costs per strategy and the latest fills.
**Make this week's report** shows this week so far without LINE; **Send it to LINE** sends it now.
