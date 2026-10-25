# C2-7 Momentum research data (copied read-only from "Research on single Stock Nasdaq", 25 Oct 2026)

- `rank_weekly.csv.gz` — weekly Nasdaq-100 market-cap ranking (top 50), Fridays 28 Oct 2016 – 23 Oct 2026:
  week, rank, symbol, mcap_busd. Market cap = Friday close × SEC shares outstanding (research file
  Nasdaq100_Top50_Weekly_2016-2026.csv). Dual-class names use the first class (GOOGL).
- `prices.csv.gz` — daily open/close, adjusted for splits and dividends (total return), Jan 2016 – 23 Oct 2026, for the
  54 companies that were ever in the top 20 (Alpaca SIP, research file nasdaq100_top50_universe_daily_2016-2026.csv).
- `members.txt` — the 100 Nasdaq-100 members on 23 Oct 2026, used for the bot's own weekly ranking from then on.

After 23 Oct 2026 the bot ranks the members itself every weekend (Yahoo market caps) and extends prices from Yahoo.
