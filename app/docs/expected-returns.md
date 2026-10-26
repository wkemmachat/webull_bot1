<!--{"title": "Expected returns", "group": "The strategies"}-->
# Expected returns

The **Expected return** panel on the Dashboard and on Strategies answers one question: *if my money stays split the way
the pie shows, what could it be worth in 1, 2 and 3 years?* Only money inside strategies counts (bot unassigned money and
cash not given to the bot are left out, like the pie).

For every period it shows three numbers:

- **Typical**: the middle case, from the research return minus the planning haircut.
- **Weak case**: about 1 period in 10 ends lower than this.
- **Good case**: about 1 period in 10 ends higher than this.

It also shows the worst fall your split had in the backtest, what each strategy adds, and how your real results compare
with the plan so far.

## Where each strategy's number comes from

1. **The research.** Every default strategy has a research yearly return: the number from the research folder it came from
   (shown on the strategy's page under *The research*). The bot keeps these numbers in one file,
   `app/research/expected.json`. The Backtest tab, the strategy pages and the Dashboard all read that same file, so they
   never disagree.
2. **Lowered for Webull's real fee** (since 26 Oct 2026). The research charged about 0.05% per switch; Webull charges 0.107% on
   every buy and every sell. The bot runs its backtest at both costs (and, where the bot now uses lower-cost settings, with
   those settings) and lowers the research return in proportion. Example: USD Trend + IBS-dip, research 66.8%; the bot's
   10-year backtest went from 62.5% to 58.7% a year, so the plan starts from **62.9%**. The panel shows these as
   *research, real fee*.
3. **Minus the planning haircut** (30% by default). A research return of 40% a year becomes a plan of **28% a year**.
4. **The bot's own backtest replaces the research in two cases:**
   - you changed a strategy's settings, so the research no longer applies;
   - the research has no 10-year return for the strategy on its own (2x Semis regime).

### Why take 30% off

Backtests nearly always beat real trading:

- The rules were picked because they worked on this history.
- Real fills, spreads and taxes can cost more than the backtest charges (the fee itself is now charged at Webull's rate).
- Markets change.

The 30% haircut builds that gap into the plan, so a normal year does not feel like a failure. You can pick 0%, 15%, 30%
or 50% in the panel. The choice changes every expected number, in the panel and in these pages.

## The weak and good cases

They come from each strategy's own **volatility** (how much it swings) in the bot's backtest of the last 10 years. The
calculation treats the yearly growth as normally distributed in log terms and takes its 10th and 90th percentiles:

- weak = typical growth × e^(−1.28 × volatility × √years)
- good = typical growth × e^(+1.28 × volatility × √years)

The range grows with time in dollars, but shrinks per year: three good and bad years partly cancel out. Real markets have
fatter tails than this model, so the strategy table also shows each strategy's **worst 12 months in the backtest**. Read the
two together: the weak case is a normal bad year, and the worst 12 months is what a very bad year looked like.

## Your split of money

- **Each strategy's money grows on its own.** It is its own sub-account, and the bot never moves money between strategies.
  The typical total is the sum over strategies of money × (1 + plan)^years. Put more money in a strategy with a higher
  plan and the total expected return goes up; put it in a lower one and it goes down.
- **The range of the total is narrower than its parts** when the strategies do not move together. The panel uses the
  correlations between the strategies' weekly backtest returns: gold and silver hardly move with Nasdaq, while QLD and
  Nasdaq stocks move together. So the weak case of a mix is better than the average of its strategies' weak cases.
- **Worst fall of this split.** The panel replays today's split on the backtest's weekly closes, over the weeks every
  funded strategy has data (about 2 years when gold or silver is in the mix, 10 years for the US strategies only). It
  also shows the fall if every strategy had its own worst fall at the same time, which is a rough worst case.

## Ratio planner: choose a ratio, then give money by it

Press **Plan a ratio** in the panel. The tiles turn into your planned split, and every strategy gets a slider and a % box.

1. **Plan for (USD)**: the amount to plan with. It starts at the money in strategies plus bot unassigned.
2. **Start from**: *My current split*, your *Saved ratio*, *Equal*, or *All 0%*.
3. **Move the sliders** or type a % for each strategy. The 1-, 2- and 3-year tiles, the weak / good range and the worst fall
   update as you move. Each row shows the dollar amount, what the strategy holds now, and the difference (+ to add, − above
   the ratio). The bar above the rows shows the ratio total. *Fill to 100%* (or *Scale to 100%*) spreads the gap over the
   strategies in proportion to their ratios.
4. **Save this ratio**: kept on the server, so you see it on any device. When the planner is closed, the panel shows
   *Your saved ratio* with its typical 1/2/3-year return, and the Money column shows each strategy's ratio next to its real
   share.
5. **Give unassigned money by this ratio**: opens the usual *Give to strategies* dialog, already filled in. The amounts take
   your bot unassigned money and add it where a strategy is below its ratio. The target is the money in strategies plus
   unassigned, times each ratio. If unassigned money is not enough, every gap is filled in the same proportion. Strategies
   already above their ratio get nothing; the dialog names them, so you can withdraw or move that money on the Money page if
   you want an exact match. Check or change any amount, choose *Now* or *Wait for the next buy signal*, then confirm. Nothing
   trades before that.

To put new money in from Webull, first press **Money → Allocate to bot**, then come back and press *Give unassigned money by this ratio*.

## Real vs expected

For every strategy, and for all of them together, the bot takes each amount you added, withdrew or moved, and grows it at
the plan rate from the day it happened. It then compares that expected value with what the strategy is really worth now.

| Status | Means |
|---|---|
| Too early | Under 3 months since the first money: a few weeks say nothing. |
| Ahead | Worth more than the plan. |
| Behind | Below the plan but above the weak case: normal, most strategies spend long stretches here. |
| Below weak case | Below what about 9 periods in 10 would give. Look at the strategy: read its page, check its Backtest and Trades. |

Do not change a strategy because of one quarter. A reasonable rule: act only when a strategy is **below the weak case at two
yearly reviews in a row**, or when its bot backtest falls below its plan number.

## All strategies now

<!--expected:all-->

## The yearly review

Every number above carries the date it was reviewed. Keeping them current takes two steps.

**1. Automatic, by the bot**

- **First start:** after the update, the bot re-runs every strategy's backtest in the background. It stores each
  strategy's volatility, worst and best 12 months, 10-year return and weekly values. This gives the weak / good ranges.
- **Every year after that:** it runs the same check again and sends a LINE message (event *Expected returns: yearly
  check*). The message lists each strategy's research return, plan and bot backtest now. It names any strategy whose
  backtest has dropped below its plan number.
- **Any time:** press *Re-run the check* in the panel (takes about a minute).

**2. With Claude, once a year**

- While the review is due, the bot sends a LINE reminder once a month, and the panel shows **Yearly review due**.
- Ask Claude: *"do the yearly expected-return review"*. Claude will:
  1. read the research folders (read only, nothing is written there);
  2. re-run the comparisons with the latest year of prices;
  3. update `app/research/expected.json` (new returns, the reviewed dates and a line in the log);
  4. update the strategy pages and *All strategies compared*;
  5. give you the usual push and pull commands.
- The strategy pages and this page then show the new numbers by themselves: their tables are filled in from the file each
  time a page opens.

## Review log

<!--expected:log-->

*Expected returns are estimates from past backtests and research, not a promise and not investment advice.*
