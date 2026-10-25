<!--{"title": "LINE alerts", "group": "Using the app"}-->
# LINE alerts

LINE Notify closed on 31 March 2025, so the bot uses the **Messaging API**:

1. https://developers.line.biz → create a Provider → create a **Messaging API** channel.
2. Basic settings → copy **Your user ID** (starts with U).
3. Messaging API tab → **Channel access token (long-lived)** → Issue → copy.
4. Scan the channel's QR code and **add it as a friend** in LINE.
5. In the bot: **LINE alerts** → paste the token → **+ Add recipient** with your user ID → **Save** → **Send test message**.

A LINE group can also receive alerts: add the channel to the group and use the group ID (starts with C). Each recipient can get
everything or only the daily reports. The daily report per strategy shows its value, its total return, **today's profit or loss**
(money added or withdrawn that day left out), what it holds and the day's trades.

## When messages go

| Delivery | Meaning |
|---|---|
| Instant | sent within 30 seconds; several at once are joined into one message |
| Digest | collected and sent at your digest times (default 08:00 and 21:00 Bangkok) |
| Off | not sent (still in Logs) |

**Quiet hours** (default 00:30–07:00) hold instant alerts until they end, except **critical** ones: a lot that failed, Webull not
connected, a new sign-in, a health-check problem. Critical alerts cannot be switched off.

The page shows the monthly quota from LINE's API. Above 90% of the quota, non-critical instant alerts move to the digest.
Every strategy also has its own LINE switch.

## New 2x ETF found

Event *New 2x ETF found* (instant by default). After the weekend ranking, if the weekly search finds a 2x ETF that passes the
checks for one of the largest stocks C2-7 Momentum 2x would hold as shares, you get its name, beta, daily trading and age. Nothing
changes until you press **Add** on the strategy page. See [C2-7 Momentum](#/docs/strategy-c27).

## Expected returns: yearly check

Event *Expected returns: yearly check* (instant by default). Once a year the bot re-runs every strategy's backtest and sends
the research return, the plan (after the haircut) and the bot backtest now for each strategy. It names any strategy whose
backtest fell below its plan. While the research review is due, a reminder comes once a month. See
[Expected returns](#/docs/expected-returns).
