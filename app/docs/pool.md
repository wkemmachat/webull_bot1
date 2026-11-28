<!--{"title": "Money: the strategy pool", "group": "Using the app"}-->
# Money: the strategy pool

Most strategies are out of the market most days, so fixed money per strategy leaves a lot of cash idle. The **strategy pool**
is one shared pot per mode (Paper, Webull test and Live each have their own). A strategy gets money when its buy signal
starts a trade and gives it back, with its profit or loss, when the trade ends.

```
Webull account
├─ Strategy pool (allocated to the bot)
│   ├─ in trades     members holding a position, each with its own money
│   └─ free cash     waits for the next buy signal (shown as bot unassigned)
└─ Not for the bot   (the bot never touches it)
```

It is off until you turn it on in **Money → Pool settings**. Off, everything works as in [Money](#/docs/money).

## Members

You choose the members per mode (**Money → Choose members**), any number. Only members trade. Every other strategy keeps
its signals, charts, backtests and LINE alerts but **never buys**: it shows *signals only*.

- **Live:** a strategy can join only after the Webull test trade of its ETF passed (Go-live → Test trade).
- **Take one out:** *Finish the trade, then leave* (it sells on its own signal, the money goes back to the pool) or *Sell at
  the next open*. Its history is kept; *Stay in pool* or *+ Add to pool* brings it back.
- A strategy that was holding money when the pool was turned on, but is not a member, finishes its open trade and then
  hands its money back.

## The rules

| Setting | Default | What it does |
|---|---|---|
| Trade size | 150% ÷ members, kept between 10% and 25% (rounded to 0.5) | Each new trade gets this share of the whole pool (in trades + free cash). You can set your own. |
| Group cap | 25% | Strategies on the same market (the groups of *What your money is in*, such as Nasdaq-100 or Semiconductors) hold at most this together. A trade that would pass it gets only the room left. |
| Smallest trade | 2% | With less free cash than this, a signal waits for money instead of buying a tiny amount. |

1. **First come, first served.** A member whose signal starts a trade gets the trade size, or the group room, or the free
   cash, whichever is smallest. Signals starting at the same check share the free cash in proportion.
2. **Open trades are never cut** to make room for a new one.
3. The trade's profit or loss stays with it until the trade ends, so a winner's next trade starts from the pool's new size,
   not from its own winnings.
4. **When a trade ends**, all its money goes back to the pool at the next check.
5. **New money:** what you allocate to the bot goes to the pool. Signals waiting for money buy at the next check (the next
   open for daily strategies). Manual Add money, Move, Split and Withdraw per strategy are off while the pool is on.
6. **No parking:** members do not park in gold or T-bills while they are out. That cash stays in the pool for the next
   signal. Research: T-bill fees cost about three times the interest at these sizes.
7. **Pause buys** and **Stop & sell** still work per strategy. A paused member gets no new money.

## Expected return of a mix

Different members give different results, so the Money page, Choose members and Pool settings show the **expected return of
the mix**. Each member's own backtest (Webull's fee, the bot's real timing) is run through the pool rules above from
$100,000. It shows a year's return and the worst fall over 1, 3, 5 and 10 years and since the earliest member's history.
It is shown next to *the same members with fixed money each* so you can see what the pool changes. The first time,
the members' backtests take a minute; they are then kept for the day.

Results from the bot's own backtest (27 Nov 2026):

| Mix | Pool, a year / worst fall (10Y) | Fixed money each (10Y) |
|---|---|---|
| The suggested 10, trade size 15%, cap 25% | 57.3% / −20.0% | 60.1% / −29.2% |
| All 20, trade size 10%, cap 25% | 69.2% / −28.9% | 58.7% / −33.0% |

For the suggested 10 (one per group, so the cap never binds) the pool mainly **cuts the worst fall**. With more members it
also uses idle cash. Several strategies use modelled ETF history from before the ETF existed, and all were picked on these
years, so plan for lower.

## Pool backtest on the Dashboard

The Dashboard card **Pool backtest · today's members** runs the pool rules on today's members' backtests and shows:

- **Value from 100** on a log scale (each step ×10 when the range is wide), over 5 years, 10 years or since the start.
- **Under water**: how far below its last high, with dashed lines at the depth reached on 80%, 85% and 90% of days, the
  add-money zone shaded and today's point.
- **After a fall this deep**: from the first day of each fall past the 80th / 85th / 90th percentile (and your alert's
  level), how often the pool was higher a year later, the typical and the 1-in-10 result, and how much further it fell
  first. Each day is ranked against the days before it only (after a 3-year start), and a fall counts again only after the
  pool climbs back above the 70th percentile — the alert's own rule, so the table is what the alert would have told you.

Adding or removing a member (Money → Choose members, or *Take it out* on a warning) changes the backtest: it is worked out
again for the new members (a minute; then kept for the day), and the chart, the table and the alerts follow.

## Alerts

Pool settings → **Alerts** (each with its LINE switch; the same switches as the LINE alerts page):

| Alert | When | Dashboard | LINE |
|---|---|---|---|
| Good time to add extra money | the pool backtest of today's members is deeper than the chosen percentile of its past days (70–95, default **80th**) | green card with the year-later figures and *Add money to the pool* | once per fall; again only after it climbs back above the 70th |
| Monthly add reminder | the chosen day (1–28, default the **1st**; the next trading day if it is a weekend or US holiday) | card until *Done this month* | once, from 08:00 Bangkok |
| Real vs backtest | the real pool (time-weighted) trails the backtest of the same members since the pool started by more than the chosen points (default **5**), after 5 trading days | amber card, *See the gap* | once; again after the gap is back within half |
| A member past its worst fall | a member is deeper below its high than its backtest's worst 10-year fall | amber card with *Open strategy* and *Take it out…* | the strategy's *Deep fall* alert |

While the pool is on, members do not send their own *good time to add money* LINE alert: new money goes to the pool.

Why these rules (research, 28 Nov 2026, 15 Live members): from the first day of each fall past the 80th percentile since
2005 the pool was higher a year later in almost every case (typically about +59%); but waiting for the zone with regular
savings lost to adding them at once in 84% of 5-year periods, and choosing a day inside the month gained nothing (+0.3% since
2005, −1.5% over 10 years). So: add regular money on your day each month; the zone alert is for money you keep aside.

## Turning it on

1. **Paper first.** Money → Choose members → Pool settings → *Pool on*. Strategies that are not members hand their cash back
   at the next check (open trades finish first).
2. Watch it for two to four weeks: Money shows each member's status (*In a trade*, *Signal · waits for money*, *No signal*),
   money by group against the cap, and the moves (*pool: trade starts*, *pool: trade ended*).
3. **Live:** pass the Webull test trade for each member's ETF, then choose members and turn it on.

[Health check](#/docs/health) also checks that the pool adds up: pool = free cash + money in trades.
