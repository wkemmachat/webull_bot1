<!--{"title": "Paper \u2192 Test \u2192 Live", "group": "Start here"}-->
# Paper → Test → Live

| Mode | Money | Orders go to | Use it for |
|---|---|---|---|
| Paper | pretend, $100,000 account, $10,000 per strategy | nowhere (filled inside the bot at live prices + 0.05% spread) | watching the logic |
| Webull test | Webull's test account | th-api.uat.webullbroker.com | checking the API connection and order flow |
| Live | your money | your Webull Thailand account | real trading |

- Modes are switched in **Settings → Trading modes**. Several can run at once; each has its own books.
- **Live** asks you to type LIVE. A strategy only trades live after you give it live money (Money → Add money).
- Plans of a mode you switch off keep being tracked until their open orders finish.
- **Pause all trading** (top right) stops every mode from sending lots until you resume. Signals are still recorded.
