<!--{"title": "Troubleshooting", "group": "Help"}-->
# Troubleshooting

| You see | Do this |
|---|---|
| "Webull is not connected yet" | Webull page → Connect → approve in the Webull app within 5 minutes |
| A plan stays "Queued" | It waits for its start time and the US session. **Start now** sends at once if the market is open |
| Lots keep retrying | The price moves away within the interval. Raise the limit offset a little or use fewer lots |
| LINE "401" | The channel token was re-issued: paste the new one |
| LINE "400" | The recipient ID is wrong: it starts with U (user) or C (group) |
| Every alert comes twice | Two copies run the scheduler. Set `SCHEDULER_ENABLED=0` on the Mac |
| "Price data problem" | Yahoo is down for a while; the bot retries every tick and does not trade on old signals |
| Positions "missing" | Something was sold in the Webull app by hand. The bot only sells what is really there |
| Locked out / forgot the password | Wait 15 minutes, or run `python -m app.reset_password` (server: `docker compose exec bot python -m app.reset_password`) |
| "Login not created yet" on the server | Put APP_USERNAME and APP_PASSWORD in `.env` and restart, or run the reset command above |
