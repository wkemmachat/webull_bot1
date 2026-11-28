<!--{"title": "2x ETF watch", "group": "Using the app"}-->
# 2x ETF watch

Every **Saturday 09:40 Bangkok** (after the US Friday close) the bot ranks US-listed **long 2x ETFs** by money traded a day
(90-day average, from Yahoo) and tells you what is new. It only reports: nothing is traded and no strategy changes.

- **Which funds count:** index, sector, theme, commodity, bond, currency and country funds. Single-stock 2x funds (Webull
  Thailand does not let you trade them) and crypto funds are left out, as are inverse, 3x, buffer, income and VIX funds.
- **Starting list:** the 76 non-single-stock 2x funds from the 26 Nov 2026 research; Yahoo's search adds funds it finds.
- **New** means: a fund **entered the top 50** this week, or a 2x fund was **listed in the last 4 months**. Funds that
  **left** the top 50 are listed too. The first check builds the starting list and reports nothing as new.
- **Where you see it:** the Dashboard card *New 2x ETFs* (one line in a quiet week), this page (*Monitor → 2x ETF watch*:
  the top 50 with each fund's move, money traded a day, years of history and status, and a weekly log), and one LINE message
  when something is new (event *New 2x ETFs this week*).
- **Status** of each fund: *In the pool*, *In the bot* (a strategy trades it), *Researched before* (in the 26 Nov research),
  *To research* (you marked it) or *Not researched*.
- **Research it** only marks the fund for you; ask Claude to research it like the others. **Dismiss** hides a new fund.
  **Check now** runs the check at once (a minute or two).

Limits: Yahoo's search finds new listings less completely than a full screener, so a brand-new fund with very little trading
can show up a week or two late. Near rank 50 funds trade only about $0.3–0.4M a day, so movement at the bottom is normal.
