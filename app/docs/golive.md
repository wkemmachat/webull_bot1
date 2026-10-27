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

Without fractions a small strategy keeps up to one share of cash idle: $500 in QLD (about $88 a share) buys 5 shares and
leaves about $59, roughly 12%, uninvested. Webull's API documentation says orders may carry decimal
quantities, but whether Webull Thailand accepts them through the API, and as which order type, is only known by trying.

Under the Test trade table, **Fractional test · limit** buys 0.5 share of the ETF you pick with a limit order (the order type the
bot uses) and sells the 0.5 straight back; **Fractional test · market** does the same with market orders. Paid from bot
unassigned like any test. The box remembers, per mode, whether each order type was **accepted** or **refused** (with Webull's own
answer). A refused fraction does not block the ETF for the strategies, and fractional tests do not count for the Go-live
symbol list.

**Result in Live (27 Oct 2026): limit accepted** (0.5 QLD bought at $89.11 and sold back, fees $0.09). So fractions are on
for Live (**Execution → Fractional shares**). A mode whose limit test passed turns fractions on by itself (Auto); you
can force On or Off per mode there.

### How the bot uses fractions

- Each lot still buys **whole shares**. The **last lot** of an ETF in a plan adds the leftover fraction (e.g. 33.62 ROM instead of
  33), as a limit order like every other lot, with Webull's fee kept inside the strategy's free cash.
- A buy smaller than one share is sent when it is worth at least **$5**; smaller leftovers stay as cash.
- **Sells** sell exactly what the strategy holds when it leaves an ETF (and on Stop & sell, or a full withdrawal), fractions
  included, so nothing is left over.
- **Safety switch**: if Webull refuses a fractional order for an ETF, the bot sends the lot again as whole shares, uses whole
  shares for that ETF from then on (in that account only) and tells you once on LINE. Execution → Fractional shares lists those
  ETFs with a **Reset** button.
- Paper follows Live unless you set it yourself.

## Webull login: renew every 15 days

Webull's OpenAPI login (token) lasts **15 days** by default and is renewed by hand: **Webull page → Reconnect**, then enter the
SMS code in the Webull app (Menu → Messages → OpenAPI Notifications) within 5 minutes. The bot reminds you:

- **LINE** when 5, 3 and 1 day(s) are left, and once more if it has ended (the last two are sent even in quiet hours);
- **Home**: an amber banner from 5 days before the end, red on the last day or once it has ended, with a **Renew now** button;
- the daily Health check (3 days before) and the end date on the Webull page.

Renew while the US market is closed (Bangkok daytime or a weekend) and a few days early. Without a valid login the bot sends no
orders and cannot read the account; queued plans simply wait — nothing is sold by mistake.

## Your checks (you tick them)

Compare the bot's Trades with Webull's order history on 3 days · indicator values vs TradingView · LINE alerts on your phone ·
the Live API key (Market data + Trading, IP whitelist, 2FA) · margin or cash account · the plan to start with 2–3 strategies.

**Count from today** restarts the counting for that mode (for example after a fix). Your ticks are kept.
