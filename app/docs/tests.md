<!--{"title": "Tests", "group": "Developers"}-->
# Tests

```
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest -q
```

The tests run offline on demo prices: indicators against TradingView definitions and an independent implementation, 4H bar
building, the seven strategies (incl. the QLD + Trend + bear-dip rule against the research code), split plans (lots, rounds, sells before buys, retries), money add/withdraw/move, LINE delivery
rules, sign-in and lockout, and the web API.
