<!--{"title": "Profit & loss: since start and by month", "group": "Using the app"}-->
# Profit & loss: since start and by month

Sidebar → **Profit & loss** (Trade group). One page for the mode in the top bar (Paper, Webull test or Live) that answers two
questions: *how much have I made or lost since I started?* and *how did each month go?* Every number comes from the bot's
own records (the value of every strategy, recorded every 30 minutes); Webull's monthly statement stays the official record.

## The numbers, in plain words

| Number | What it means |
| --- | --- |
| **Profit / loss** | Value change minus money moved in or out. Putting $5,000 in is never a gain; taking money out is never a loss. |
| **Put in** | Money in minus money out, all strategies together. |
| **Worth now** | Value of all strategies now, at live prices. Worth − put in = the profit or loss. |
| **% of the money in play** | Profit ÷ money in play (since start: ÷ put in). The same % as the Dashboard's *Since start*. |
| **Time-weighted %** | Each day's profit ÷ (value before + money added that day), chained. It ignores *when* you added money, so it is the fair way to compare months or to compare with a fund. Under a year of records it is not a yearly rate, and the page says so. |
| **Held instead** | The same money bought and held in the same ETFs (the Dashboard's "vs buy & hold" line), worked out the same way. *Bot $X ahead / behind* is the difference. |
| **Fees** | Webull fees on the orders of the period. They are already inside the profit or loss; shown so you can see them. |

The **Since start** number is exactly the Dashboard's *Since start*. A month's profit is the sum of its US trading days
(New York date), so the months add up to the since-start number.

## What is on the page

1. **Summary** — the big profit or loss, both % figures, *put in → worth now* with a bar (green: what is left of the money in
   play; red: the loss, or a lighter green beyond it: the gain), the buy-and-hold comparison, days up/down, best and worst day
   and fees. The buttons at the top (*Since start*, the last three months) switch the whole page to one month.
2. **Worth vs money put in** — the black line is what everything was worth at each US close (the last point is now); the grey
   step line is the money put in. The shaded gap between them is your profit (green) or loss (red). Dots mark days money went
   in (green) or out (red). The dashed purple line is the same money bought and held. Hover a day for its numbers.
3. **Monthly returns** — a year × month grid (on a phone: a tile per month), % (time-weighted) or $. Tap a month to narrow
   the page to it; tap it again for since start. `*` = month to date.
4. **Month statements** — like a bank statement: *Start + put in / taken out + profit / loss = End*. A month starts at the
   previous month's last close and ends at its own last close (the current month: now).
5. **Where it came from** — each strategy's part of the period, worst to best. The bars add up to the total. A greyed bar is a
   strategy with no money in it now (it still counts: its profit or loss happened).
6. **By strategy and month** — a strategy per row, the last six months as columns, coloured by size. The rows add up to the
   month totals (a *Timing of the records* row appears only if a strategy's records and the total's are a few minutes apart).
   Tap a name for that strategy's Daily P&L.

**Download CSV** gives every month (start, put in, profit, %, held instead, end, fees, days up/down and one column per
strategy) plus a *since_start* row — ready for a spreadsheet or your accountant.

## A strategy's months

Each strategy page → **Daily P&L** tab → **By month**: the same statement for that strategy alone (start, put in / taken out,
profit, % chained from its days, end, days up/down), above its day-by-day table.

## Why it can differ from Webull

- The bot counts a day at its last record of that US day (every 30 minutes), Webull at the official close.
- Fees and dividends Webull books a day later land in the next day here.
- Money outside the bot's strategies (Webull cash the bot does not manage) is not in these numbers.
