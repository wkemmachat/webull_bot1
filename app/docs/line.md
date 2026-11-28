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

**Weekend pause** (on by default, *When to send*): no digest from Saturday 12:00 to Monday 08:00 (Bangkok). The Saturday
08:00 digest still comes (it carries Friday's US close); anything collected after it waits for Monday 08:00, in one
message. Instant and critical alerts are not paused.

**Restarts**: a deploy (a new version) and a normal restart or server reboot are written to Logs only (*Bot started* with
*Bot updated 75a13aa → 4f2c9e1* or *shut down normally*). LINE gets *Bot restarted unexpectedly* (instant, waits for quiet
hours) only when the bot did not shut down normally: a crash, out of memory or a power loss, with the last time it was seen
running and how long it was off.

## Monthly message budget (300)

Every push to every recipient is one LINE message, and LINE's free plan allows **300 a month**. On 27 Nov 2026 the bot reached
the limit and LINE refused the rest of the month's alerts, critical ones too. Now the bot keeps to a **monthly budget**
(LINE alerts → *Connection*, default 300; LINE's own plan limit is used if it is lower):

| State | What happens |
|---|---|
| On pace | everything as set |
| Today's share used | the month's room left (less the reserve) is spread over the days left; past today's share, routine instant alerts wait for the next digest |
| Running low | the month's digests would not fit: **one digest a day** (the first time), routine instant alerts go into it |
| Critical only | the last **30 messages** are kept for critical alerts (failed lot, Webull disconnected, new sign-in, health problem); the rest is not sent but stays on the site (Logs, Dashboard) |
| Limit reached | nothing is sent until the 1st |

The count is the bot's own (each message × recipients) or LINE's (refreshed hourly), whichever is higher, and starts again on
the 1st (Bangkok). Unused room carries over to the next days. The page shows *this month* with the reserve marked, today's use
and share; the Dashboard and Health check warn when running low. *Recently sent* marks what the budget held back
(*not sent · budget*).

Every strategy also has its own LINE switch. With **Automatic** on (LINE alerts page → *Strategies sending alerts*, on by
default) the switches set themselves: a strategy's LINE is **on while it is not Stopped** (Active, Pause buys or Stop & sell)
**and holds money** (at least $1 of cash or any shares) in Live, or in the modes that are on when Live is off; it turns
**off** once the strategy is Stopped or empty. Giving money to a strategy is enough to start its alerts, and a strategy you
empty or stop still sends its last messages (the move, the final sale, *stopped*) before it goes quiet. Each change is
written to Logs (*LINE alerts turned on automatically*). Critical alerts (a failed lot, Webull disconnected, a health-check
problem) always come. Turn Automatic off to set every switch by hand.

## Pool alerts

With the strategy pool on: *Pool: good time to add extra money*, *Pool: monthly add reminder* and *Pool: real behind its
backtest* (all Instant; Pool settings → Alerts switches them the same as this page). They go out for one mode only (Live when
it is on). See [Strategy pool → Alerts](#/docs/pool).

## Orders for the next US open

Event *Orders for the next US open* (instant by default). At 17:30 New York on each trading day you get one message per trading
mode, listing every plan waiting for the next open: for example "USD Trend + IBS-dip: buy ≈118 USD ≈$9,950 — Dip day: IBS
0.06 < 0.15", with the start time in Bangkok. It arrives after the US close; quiet hours (00:30–07:00) hold it until 07:00
Bangkok. Nothing is sent when no orders are waiting.

## New 2x ETF found

Event *New 2x ETF found* (instant by default). After the weekend ranking, if the weekly search finds a 2x ETF that passes the
checks for one of the largest stocks C2-7 Momentum 2x would hold as shares, you get its name, beta, daily trading and age. Nothing
changes until you press **Add** on the strategy page. See [C2-7 Momentum](#/docs/strategy-c27).

## Expected returns: yearly check

Event *Expected returns: yearly check* (instant by default). Once a year the bot re-runs every strategy's backtest and sends
the research return, the plan (after the haircut) and the bot backtest now for each strategy. It names any strategy whose
backtest fell below its plan. While the research review is due, a reminder comes once a month. See
[Expected returns](#/docs/expected-returns).
