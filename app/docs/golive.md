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

## Your checks (you tick them)

Compare the bot's Trades with Webull's order history on 3 days · indicator values vs TradingView · LINE alerts on your phone ·
the Live API key (Market data + Trading, IP whitelist, 2FA) · margin or cash account · the plan to start with 2–3 strategies.

**Count from today** restarts the counting for that mode (for example after a fix). Your ticks are kept.
