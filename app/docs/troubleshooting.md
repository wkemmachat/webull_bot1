<!--{"title": "Troubleshooting", "group": "Help"}-->
# Troubleshooting

| You see | Do this |
|---|---|
| "Webull is not connected yet" | Webull page → Connect → enter the SMS code in the Webull app within 5 minutes (Menu → Messages → OpenAPI Notifications) |
| Webull "401" / "IP not allowed" | The App Key's IP whitelist must contain the server IP (165.245.188.124); the Mac's IP will be refused |
| A plan stays "Queued" | It waits for its start time and the US session. **Start now** sends at once if the market is open |
| "Webull refuses QLD" (OPENAPI_IS_TH_FIRST_ETF_PLACE) | The account has not switched on Leveraged & Inverse ETFs. In the Webull app, try to buy 1 QLD by hand: Webull shows the Leveraged & Inverse ETF risk notice — read and agree (or ask Webull support to switch it on). The shared test accounts cannot do this: test with a strategy that holds GLD/BIL/SGOV, or ask Webull for your own test account |
| "Webull refuses USD" (OPENAPI_TICKER_IS_DENY) | Webull TH does not offer that ETF. Pick another one for the strategy (Strategies → edit), or pause it |
| After you fix a refusal | Orders → **I fixed it — try again now**. Otherwise the bot tries again by itself after 6 hours |
| Lots keep retrying | The price moves away within the interval. Raise the limit offset a little or use fewer lots |
| LINE "401" | The channel token was re-issued: paste the new one |
| LINE "400" | The recipient ID is wrong: it starts with U (user) or C (group) |
| Every alert comes twice | Two copies run the scheduler. Set `SCHEDULER_ENABLED=0` on the Mac |
| "Price data problem" | Yahoo is down for a while; the bot retries every tick and does not trade on old signals |
| Positions "missing" | Something was sold in the Webull app by hand. The bot only sells what is really there |
| Locked out / forgot the password | Wait 15 minutes, or run `python -m app.reset_password` (server: `cd /opt/webull_bot1 && sudo -u thbot .venv/bin/python -m app.reset_password`) |
| "Login not created yet" on the server | Put APP_USERNAME and APP_PASSWORD in `.env` and restart, or run the reset command above |
