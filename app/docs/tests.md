<!--{"title": "Tests", "group": "Developers"}-->
# Tests

```
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest -q
```

The tests run offline on demo prices: indicators against TradingView definitions and an independent implementation, 4H bar
building, all twelve strategies (incl. the QLD + Trend + bear-dip rule against the research code, the Trend + IBS-dip size band and dip rule, and the USD version's full-size dip days), split plans (lots, rounds, sells before buys, retries), money add/withdraw/move, LINE delivery
rules, sign-in and lockout, next-open orders (queued plans, exact sells, estimated buys, the LINE preview), daily P&L (money moves left out, today vs last session, CSV), falls (depth, length, recovery, time underwater), the weekly 2x ETF search (name filter, beta / age / trading checks, suggest / add / dismiss), expected returns (research − haircut, the weak/good range, the mix of strategies, real vs
expected, the yearly check and the filled-in docs), and the web API.
