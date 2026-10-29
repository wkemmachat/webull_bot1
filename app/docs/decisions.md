<!--{"title": "Design decisions", "group": "Help"}-->
# Design decisions (October 2026)

- **Three money layers**: Webull account → allocated to the bot (strategies + bot unassigned) → strategies. Cash you do not
  allocate is never used. Withdrawals go back to bot unassigned; *Return to Webull* hands money back.
- **Money per strategy**: each strategy has its own dollar capital you add or withdraw (as in the AI x Alpaca bot), not a
  percentage of one pot. Paper starts every strategy with $10,000; a new install's paper account is $150,000 (twelve strategies).
- **New money**: invest at today's signal by default; switch to *wait for the next buy signal* in Execution → When new money arrives
  (or per deposit). Waiting money stays as plain cash in the strategy, outside its plans.
- **QLD + Trend + bear-dip** (added 23 Oct 2026 from the ETF Strategy Lab): same timing as the regimes (decide after the close,
  trade from the next open), T-bills via BIL when out, $10,000 paper money like the others.
- **QLD Trend + IBS-dip** (added 25 Oct 2026 from *Research on single Stock Nasdaq*, strategy 2): the signal comes from QLD's own
  daily bar, the size from QQQ's 60-day volatility (resized only on a 20-point move), parking 50% GLD + 50% BIL (BIL rather than
  SGOV so the backtest reaches back to 2007, like the other QLD strategies). Dip days are one-day trades; resizes are sent to
  LINE as RESIZE messages.
- **USD Trend + IBS-dip** (added 25 Oct 2026, research *USD own-price candidate C, aggressive*): the same strategy type on USD with
  its own volatility (leverage 1, 40% cap, 20 days), Supertrend 20 × 4.5, dips on IBS < 0.15 without an ADX filter held at **100%**
  (option *Dip days at full size*). The research resized every day (~134 trades a year); the bot uses the 20-point resize rule
  (~62 a year, same 10-year result). Backtest compares with SMH (option *Compare with*).
- **Expected returns** (added 25 Oct 2026): the plan per strategy is the research yearly return minus a 30% planning haircut
  (0/15/30/50% selectable). The weak / good cases are the 10th / 90th percentiles from the strategy's volatility in the bot's
  10-year backtest. The total is each strategy's own money compounding at its own plan (sub-accounts are never rebalanced);
  the total's range uses the correlations of weekly backtest returns. The research numbers live in one file,
  `app/research/expected.json`, read by the Backtest tab, the strategy pages and the Dashboard. The bot re-runs the backtests
  once a year (LINE). The research review is done with Claude, prompted by a monthly LINE reminder while it is due.
- **Ratio planner** (25 Oct 2026): set a % per strategy, see 1/2/3 years live, save the ratio on the server (`expected_plan`),
  and give bot-unassigned money by it through the usual Give-to-strategies dialog, prefilled. The target is (money in strategies +
  unassigned) × ratio. Only gaps are filled (scaled down when unassigned is short); nothing is sold automatically.
- **IBS rounded to 4 decimals** (25 Oct 2026): a true tie (QLD 10 Feb 2022, IBS exactly 0.20) came out as 0.19999… from
  Yahoo and triggered a dip trade the research does not take. Rounding makes the decision independent of the feed's float noise.
- **Costs in the backtest** are charged on every ETF traded (the parking legs too), not once per switch as in the research.
- **Webull's real fee** (26 Oct 2026): Webull Thailand charges 0.10% + 7% VAT = 0.107% of every buy and every sell, with no
  minimum (checked on the live test trades: GLD round trip $0.40 + $0.41). Every backtest now charges **0.11%** per side
  (Settings → Fees; single-stock 2x ETFs 0.16%), paper trading charges 0.107%, and the expected returns are the research's
  numbers lowered by what the fee costs in the bot's backtest. The busy strategies lose most: USD IBS −4, metals −5 to −7,
  C2-7 −3, the regimes about −1 point a year at the old settings.
- **Lower-cost settings** (26 Oct 2026), chosen from about 1,100 bot-engine backtests at the real fee:
  - QLD and USD Trend + IBS-dip keep the T-bill half of the parking as **cash** (*Keep the T-bill part as cash*): every switch
    trades about half as much. It won in 44–50 of 50 rule combinations; the numbers count the lost T-bill interest.
  - QLD Trend + IBS-dip: a dip day needs **IBS < 0.15** (was 0.20): fewer, stronger dips; 0.10–0.15 beat 0.20 for every ADX.
  - The four metals strategies stay in **cash** while flat instead of SGOV (+2 to +4 points a year in the 2-year backtest).
  - Kept as the research chose: Supertrend, SMA, ADX, the 20-point resize rule and dip size (changes there helped some years
    and hurt others). Regimes, QLD + Trend + bear-dip and C2-7 keep BIL / SGOV: they switch 4–9 times a year, so the saving
    is about what the T-bill interest earns.
  - Strategies still on the old defaults were moved once at the restart (Logs: *settings updated to the new default*);
    settings you changed yourself were left alone.
- **Single-stock 2x ETFs refused** (26 Oct 2026, live Test trade of AAPU and AMUU): Webull Thailand's code
  *OPENAPI_ONLY_UHNWE_SINGLE_STOCK_REVERSE_ETF_LIMIT* (below 50M THB). It is treated as a permanent account rule: one refusal
  blocks every single-stock 2x ETF in that mode, C2-7 Momentum 2x holds the stocks (works like 1x) with a warning on the
  strategy, and the weekly 2x search stops sending suggestions. Real money belongs in C2-7 Momentum 1x.
- **Expected-return check follows the settings** (26 Oct 2026): the stored backtest check is re-run (no LINE) within
  10 minutes when the fee or a strategy's settings change, so *Bot backtest now* never shows numbers from other settings.
  The Expected return table sorts by any column; most profitable first by default.
- **Weekly 2x ETF search** (25 Oct 2026, C2-7 Momentum 2x): after the weekend ranking, Yahoo is searched for a 2x ETF for
  each of the 15 largest stocks held as shares. It must pass these checks: beta 1.7–2.3 and correlation ≥ 0.90 over 60 days,
  63+ trading days, $2M+ a day, spread < 0.5% when known. It is only suggested (LINE + Add/Dismiss on the strategy page), never
  added automatically, and Add is followed by a Test trade.
- **Daily P&L and falls** (25 Oct 2026):
  - Daily P&L comes from the equity record, which is taken every 30 minutes. The last record of each US trading day is that
    day's close. P&L = value change minus net money moved that day.
  - Falls (drawdowns) come from the backtest series and from a time-weighted index of the real values: worst fall, longest
    underwater, the share of days below a high and the 5 worst falls.
  - The strategy cards read a saved summary that the yearly backtest check and the strategy page update.
- **Centered layout**: a page column with a maximum width (--page-max 1,480 px) on wide screens; the top bar is aligned to it.
- **Next-open orders** (25 Oct 2026):
  - The Dashboard and each strategy page list the active plans: sells exact, buys estimated as target × the strategy's money
    − what it holds, at the last price (the same sum the plan uses when it sends each lot).
  - LINE event *Orders for the next US open* at 17:30 New York on each trading day; quiet hours hold it until 07:00 Bangkok.
- **One replacement per lot** (25 Oct 2026): found on the Webull test account. The one-time re-check of 24 Oct read old
  orders as expired after the session and gave some lots 2–3 replacement orders waiting for Monday's open. A retry is now
  only created when the lot has no newer attempt and no open order. Each tick also keeps just the newest waiting order per lot
  and marks the extra copies skipped (with a Logs entry).
- **Name and look** (26 Oct 2026): the bot is now called **Webull Strategy Bot**.
  - Light green is the default theme: a mint-tinted page, white cards and a deep green accent (#15803D). The accent has 5.0:1
    contrast with white text and 4.7:1 on the page, both WCAG AA. Dark mode uses #4ADE80.
  - Amber still means a warning and red a loss or an error. Gains and losses also carry + / − signs, so the green accent never
    has to carry meaning on its own.
  - When Live is chosen, the mode switch shows it in green. Settings → Theme can still switch to dark or follow the device.
- **Regime timing**: decided after the US close, traded from the next market open with split lots (the research filled at the next
  open, which tested better than the same close).
- **UGL in Gold #1 and Gold #2**: each strategy keeps its own orders and books; orders are not merged (simpler and easier to audit).
- **Metals entries** start not before 22:00 Bangkok (after the US open has settled); exits start as soon as the market is open.
- **Login**: one login only (yours): username or email + password. No sign-up page for anyone else; the first login can only
  be created on the bot's own computer (or from `.env` on the server). 5 wrong tries → 15-minute lock and a LINE alert.
- **Charts**: TradingView Lightweight Charts drawing the bot's own indicator values, so the chart always matches what was traded.
- **Language**: English, with Thai terms in the glossary.
- **First Live allocation review (27 Oct 2026)**:
  - *Invest now* on a strategy with cash waiting for its next buy signal ends the wait; the bot buys toward today's target from
    the next check (the next market open if it is closed).
  - Stopped and stopping strategies are left out of *Give to strategies* and *Move* targets; + Add to one warns (screen + LINE).
  - *Stop & sell* finishes by itself when no mode holds the strategy's shares or runs a plan for it (before, a strategy with
    nothing to sell stayed "stopping" for good).
  - Health's independent recompute now covers the C2-7 baskets (SMA, RSI, Supertrend and the state rule); it reported a false
    error for both before.
  - Go-live → Test trade lists only the ETFs of strategies that are not stopped, and leaves out single-stock 2x ETFs once Webull's
    50M THB rule applies to the account.
  - Money movements → How shows the note and how the money invests (e.g. "split · waits in cash for the next buy signal").
- **Timeframe check (27 Oct 2026)**: the six daily 2x ETF strategies stay on daily bars. On 4h and 2h bars (TradingView, the bot's
  own code, next-bar-open fills, 0.11% fee) none was clearly better: "same numbers" lost 7–52 points a year over 10 years, "same
  time span" tied (QLD regime) or lost (Semis, ROM, both IBS-dip), except QLD + Trend + bear-dip on 4h (+4–5 points, deeper
  fall, behind in the last 2 years), kept as a research note. Details: Docs → Daily vs 4h vs 2h bars.
- **Fractional shares (27 Oct 2026)**: Go-live → Test trade has a fractional test (0.5 share by limit or market order, sold
  back). The result per mode and order type decides whether a "fractional shares" option is added; until then the bot buys whole
  shares. Orders send Webull a decimal quantity ("0.5") only for these tests.
- **Dip zones (27 Oct 2026)**: each strategy's depth below its own backtest high, as a percentile of its last-10-year days,
  refreshed after every US close. Green "Buy zone" = 70–80th percentile, solid dark green "Strong buy zone" = 80th or deeper (Home
  banner + one LINE message per dip, re-armed above the 70th; colours as analyst ratings: Buy green, Strong buy dark green). Shown on Home cards, the Strategies list and the Expected return table. Docs → Buy zones.
- **Webull login reminders (27 Oct 2026)**: tokens last 15 days (Webull docs). LINE at 5, 3 and 1 day(s) left and when ended
  (only the nearest step if the bot was off; a renewed token starts again), plus a Home banner from 5 days before the end.
- **Limits for thin ETFs (27 Oct 2026)**: ROM's first Live lot was priced from yesterday's close (no ROM trade yet at the open,
  no bid/ask from Webull) and the ETF opened 1% higher; the retry used the same stale price. Now a quote with no trade yet in
  today's session gets 0.5% more room, and each retry moves the limit at least 0.5% beyond the lot's first limit (cap 2%).
- **Fractional shares in plans** (27 Oct 2026, after the Live fractional limit test passed): whole shares in every lot and the
  leftover fraction (2 decimals) on the last lot of each ETF, so a small strategy no longer keeps up to one share of cash idle.
  Exits sell the exact holding. Minimum fractional buy $5. Setting per mode (Auto = follows that mode's Go-live limit test;
  Paper follows Live). A refused fractional order re-sends the lot as whole shares, switches that ETF (per account) back to
  whole shares and sends one LINE message; it does not block the ETF or cancel the plan.
- **Go-live list after the first Live days** (27 Oct 2026): the ETF test item counts only strategies that have money in that
  mode (all active ones while none has); errors that already have their answer no longer block "No errors" (Webull's 50M THB
  single-stock rule, a failed Test trade of an ETF that passed later); Health no longer marks the handled 50M THB rule as an
  error every day; Test trades widen and chase their limit like lots (thin ETFs such as ROM).
- **Money → Everything** (27 Oct 2026): the button now sends "all" and the server takes the whole strategy at today's prices
  (sells every holding, fractions included, and moves what the sale brings in). Before, the dialog's value was a few seconds
  old, so a small price move made the server refuse it ("worth $150.52; you asked for $150.63").
- **Fractions: 2 decimals and exact fills** (27 Oct 2026, first Live fractional orders): Webull executes the exact fractional
  quantity (1.6581 QLD, 1.3439 USD) but its order status reports it rounded to 2 decimals (1.66, 1.34). The bot booked the
  rounded number, so the Stop & sell of QLD regime sold 1.66 and took 0.0019 QLD (≈ $0.17) of your own QLD, and 2x Semis
  showed 29.66 USD instead of 29.6561. Now buys use 2 decimals, a FILLED fractional order is booked at its exact quantity, and a
  one-time repair corrected the USD books (the QLD difference was already settled by the sale).
- **Idle cash box and Portfolio page** (27 Oct 2026): strategy pages show cash that waits for a buy signal or sits inside
  the rebalance band, with the next buy signal in plain words, the Buy zone pill, and Invest now / Top up now (top-up buys
  only, never sells; small top-ups allowed down to $5 as your explicit choice). The Portfolio page puts the mix vs the
  saved ratio plan (with suggested Moves that open the Money dialog), exposure by market, the mix's combined backtest
  (sub-accounts never rebalanced, computed in the browser from the expected-returns check's weekly series; short metals
  histories left out and named), try-a-mix, correlations and the real time-weighted result on one page. The expected check
  (version 3) now also stores each strategy's full-history weekly values for "All years".
- **Weekly report on LINE** (28 Oct 2026): Saturday 09:00 Bangkok, per mode that is on. Real week (time-weighted) vs the
  strategy's backtest over the same days, fees, and fills vs the day's open (the daily backtests' fill price) as the real
  cost of trading, this week and since the first Live order. Reports kept 26 weeks; shown on the Portfolio page.
- **LINE tidy-up** (28 Oct 2026): daily reports show fractional shares (29.6561 USD, not "30"); a digest lists a repeated
  message once with a count ("Bot started. (×9)"); Webull test's refused leveraged ETFs (the shared test accounts refuse
  them for everyone) are a Health warning, no longer a daily "problem" alert.
- **20-year backtests** (28 Oct 2026): before QLD (Jun 2006), USD/ROM (early 2007) and BIL (May 2007) existed, their daily
  prices are built from the index (2 × QQQ / SMH / IYW minus 0.95% fee and the T-bill cost of the extra 1×; BIL = T-bill
  rate), from Jan 2006, chained back from the first real close. Every daily strategy now starts in 2006; the Falls card
  marks the built part. Signals that read the 2x ETF's own bars (Trend + IBS-dip) see the built bars only inside the
  backtest (per thread), never in live trading. Checked: the fill does not change any later signal (USD Trend + IBS-dip
  has the same falls with and without it).
- **Buy zones over 20 years** (28 Oct 2026, your choice): the percentile now compares today's depth with the last 20 years
  of the strategy's backtest (was 10), so 2008 and 2011–2016 count. Stricter: e.g. ROM 90th → 76th, 2x Semis 78th → 64th,
  QLD regime 70th → 57th (23 Oct). Stored zones are recomputed on the first start with the new window.
- **Hong Kong and HKD** (added 28 Oct 2026, from the research *HK 2x ETFs vs QQQ*): the bot holds Hong Kong dollars in its own
  pot per mode (**bot HKD**, table `pool_fx`), separate from the USD books; HKD you do not allocate is never used. Converting USD to
  HKD stays in the Webull app (paper has a pretend *Convert* button and starts with HK$100,000). The Go-live page tests 7234, 7226
  and 7233 by buying one board lot (100 shares) and selling it back: Webull HK order format (five-digit symbol, market HK,
  ENHANCED_LIMIT on HKEX's tick table, optional BCAN), Hong Kong hours only, paid from bot HKD. Webull Thailand documents US
  trading only, so the result decides whether Hong Kong strategies are built; the section is not counted in readiness.
- **Growth of $10,000** (added 28 Oct 2026): on each strategy's Overview, above Falls to expect, from the same backtest run
  (so the dates always match). Comparison lines: the traded ETF and the signal index held (the first two benchmark series of
  the backtest); log scale by default; the real line is the time-weighted real index started at the backtest's value that day.
  Both charts are drawn at the page's real width with the same margins, so their years line up.
- **Opposite orders settled inside the bot** (added 29 Oct 2026, your request): when one strategy sells a symbol another
  buys while both plans are running, the shares move between the two strategies' books at one price (mid of bid/ask, else
  the last price) with no fee, and only the net goes to Webull. One account means the real position never needed both trades.
  The 20-year backtests show about 12 such days a year (USD, QLD, GLD, BIL). Each side gets an *inside the bot* fill
  (`orders.cross_with` = the other strategy, `broker_order_id` = internal, no submit time), so Webull order counts, fees and
  the Go-live counts are not changed. On by default (Execution page).
- **Hong Kong test removed** (29 Oct 2026, your check in the Webull app: Hong Kong trading is not allowed for this account): the
  Go-live checklist no longer has the *Hong Kong market* section and the bot refuses Hong Kong test trades. The HKD money block
  stays only so bot HKD can be returned; no strategy trades Hong Kong.
