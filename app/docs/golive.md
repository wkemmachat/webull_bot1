<!--{"title": "Go-live checklist", "group": "Using the app"}-->
# Go-live checklist

**Monitor → Go-live checklist** shows how ready the bot is for real money, measured from its own records in one mode
(normally **Webull test**) since the day you started testing. Aim for **90%** with every **must** item done, then start Live small.

## Daily operations (automatic)

| Item | Passes when |
|---|---|
| US trading sessions | the bot ran during US market hours on 10 trading days with the mode on |
| Order plans finish | at least 5 plans done, none stuck for more than 2 days |
| Lots fill | at least 20 lots sent and no lot failed after all retries |
| Health check clean | 8 days without a problem for this mode (books = account, cash adds up, indicators, bot ran) |
| New signal handled | at least one live signal turned into orders |
| No errors | nothing in Logs → Errors in the last 3 days |
| Webull, LINE, backup | connected with a valid token · alerts delivered · last night's backup made |

## Planned tests (ticked automatically when you do them)

Withdraw from a strategy that holds ETFs · Move money · Stop & sell · Pause all trading during a plan and resume · Restart the
server during a plan (`systemctl restart th-strategy-bot`) · Disconnect and reconnect Webull · Money guard blocks a buy (set the
protected floor above your free cash, see the next buy blocked, set it back) · Return money to Webull.

## Test trade: buy 1 share, sell it back

On the Go-live page, **Test trade** checks every ETF the strategies use (QLD, USD, UGL, AGQ, GLD, BIL, SGOV and the C2-7 2x ETFs) one by one:
the bot buys 1 share (a limit order a little above the ask, like a strategy lot), waits for the fill, sells it straight
back and shows the cost, the fees and how long the fill took. It proves Webull accepts the symbol, fills it and reports it
correctly — before a strategy needs it.

- **Money:** paid from **bot unassigned** only. No strategy's cash or shares change. Keep about $200 there
  (Money → Webull → bot). The money guard and the protected floor check the buy like any other.
- **Cost:** the spread plus Webull's fees, usually under $0.50 a test.
- **When:** US market hours only. Tests queued while the market is closed start at the open. "Test all" runs them one at a time.
- **If the buy does not fill** in 3 tries (2 minutes each) the test stops; "Webull's own answer" shows Webull's order detail.
- **If the sale does not fill** in 5 tries the share stays: LINE alert, then **Sell again**, or sell it in the Webull app and
  press **I sold it** (that sale's cash then stays in Webull, outside the bot).
- **Refused ETFs:** a refusal for Leveraged & Inverse ETFs (OPENAPI_IS_TH_FIRST_ETF_PLACE) means the account must accept
  that risk notice first. The shared Webull test accounts cannot, so on Webull test those ETFs only pass in Live. A
  passed test also clears the "refused" block for that ETF.
- In **Live** the checklist item "Every ETF … bought and sold once" is a must: run Test all on the first market day after
  connecting the Live key, before switching strategies on.

## Fractional shares test: 0.5 share, sold back

The bot buys **whole shares** today. A small strategy therefore keeps up to one share of cash idle: $500 in QLD (about $88 a
share) buys 5 shares and leaves about $59, roughly 12%, uninvested. Webull's API documentation says orders may carry decimal
quantities, but whether Webull Thailand accepts them through the API, and as which order type, is only known by trying.

Under the Test trade table, **Fractional test · limit** buys 0.5 share of the ETF you pick with a limit order (the order type the
bot uses) and sells the 0.5 straight back; **Fractional test · market** does the same with market orders. Paid from bot
unassigned like any test. The box remembers, per mode, whether each order type was **accepted** or **refused** (with Webull's own
answer). A refused fraction does not block the ETF for the strategies, and fractional tests do not count for the Go-live
symbol list.

What happens next depends on the answer: limit accepted → the bot can be allowed to buy fractions like whole shares; only market
accepted → whole shares by limit order and only the leftover fraction at market; both refused → whole shares stay (give each
strategy at least about $1,000). The setting itself is added after the test.

## Your checks (you tick them)

Compare the bot's Trades with Webull's order history on 3 days · indicator values vs TradingView · LINE alerts on your phone ·
the Live API key (Market data + Trading, IP whitelist, 2FA) · margin or cash account · the plan to start with 2–3 strategies.

**Count from today** restarts the counting for that mode (for example after a fix). Your ticks are kept.
