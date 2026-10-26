<!--{"title": "Paper \u2192 Test \u2192 Live", "group": "Start here"}-->
# Paper → Test → Live

| Mode | Money | Orders go to | Use it for |
|---|---|---|---|
| Paper | pretend, $150,000 account (new installs), $10,000 per strategy | nowhere (filled inside the bot at live prices + 0.05% spread + Webull's 0.107% fee) | watching the logic |
| Webull test | Webull's test account | th-api.uat.webullbroker.com | checking the API connection and order flow |
| Live | your money | your Webull Thailand account | real trading |

- Modes are switched in **Settings → Trading modes**. Several can run at once; each has its own books.
- **Live** asks you to type LIVE. A strategy only trades live after you give it live money (Money → Add money).
- Plans of a mode you switch off keep being tracked until their open orders finish.
- **Fees**: test and live pay Webull's real fee (0.10% + 7% VAT = 0.107% per trade, no minimum). Paper charges the same 0.107%
  (Settings → Fees), so paper results are not better than real ones.
- **Pause all trading** (top right) stops every mode from sending lots until you resume. Signals are still recorded.
