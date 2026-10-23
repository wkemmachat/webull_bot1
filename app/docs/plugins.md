<!--{"title": "Add a strategy plugin", "group": "Developers"}-->
# Add a strategy plugin

Most new strategies need no code: **Strategies → + Add strategy** with one of the existing types and different parameters.
For new rules, add a Python module in `app/strategies/`:

```
from .base import StrategyBase, register

@register
class MyStrategy(StrategyBase):
    type = "my_rule"
    label = "My rule"
    family = "regime"            # or "signal"
    timeframe = "1D"
    PARAMS = [
        {"key": "signal", "label": "Signal", "kind": "symbol", "default": "SPY", "group": "Symbols"},
        {"key": "trade", "label": "Trade with", "kind": "symbol", "default": "SSO", "group": "Symbols"},
        {"key": "days", "label": "Average (days)", "kind": "int", "default": 200, "min": 10, "group": "Rules"},
    ]

    def data_needs(self):
        return [(self.params["signal"], "1d")]

    def trade_symbols(self):
        return [self.params["trade"], "BIL"]

    def evaluate(self, now):
        # return the TARGET: share of the strategy's money per symbol
        return {"ok": True, "state": "on", "label": "ON · SSO", "target": {"SSO": 0.99},
                "bar_time": ..., "signal_time": ..., "checks": [], "history": []}
```

Restart the bot: the type appears in the wizard and its PARAMS build the form. `evaluate()` never places orders: the execution
engine turns the target into split plans. `chart()` returns the chart spec (see `signal.py` and `regime.py`).
