"""What every strategy type provides. Add a new type by putting a module in app/strategies/ with a class
decorated with @register: it then appears in Strategies → Add strategy, and its PARAMS build the form.

A strategy never places orders itself. `evaluate()` returns the TARGET: the share of the strategy's
money each symbol should hold, e.g. {"UGL": 0.99} or {"QLD": 0.25, "BIL": 0.74}. The execution engine
compares that with what the strategy holds and sends split orders to get there.
"""
from __future__ import annotations

import copy

TYPES: dict = {}


def register(cls):
    TYPES[cls.type] = cls
    return cls


class StrategyBase:
    type = "base"
    label = "Base"
    family = "signal"              # signal (4H bars) | regime (daily)
    timeframe = "4H"
    description = ""
    PARAMS: list = []              # [{key, label, kind(int|float|text|symbol|select|bool), default, help, group, options}]
    EXEC_DEFAULTS: dict = {}       # execution overrides that suit this type (e.g. regimes start at the market open)

    def __init__(self, row: dict):
        self.row = row
        self.id = row["id"]
        self.name = row["name"]
        self.color = row.get("color") or "#5B8DEF"
        self.params = self.merge_params(row.get("params") or {})

    @classmethod
    def default_params(cls) -> dict:
        return {p["key"]: copy.deepcopy(p["default"]) for p in cls.PARAMS}

    @classmethod
    def merge_params(cls, given: dict) -> dict:
        out = cls.default_params()
        for p in cls.PARAMS:
            if p["key"] in given and given[p["key"]] is not None:
                v = given[p["key"]]
                try:
                    if p["kind"] == "int":
                        v = int(float(v))
                    elif p["kind"] == "float":
                        v = float(v)
                    elif p["kind"] == "bool":
                        v = v in (True, 1, "1", "true", "on", "yes")
                    elif p["kind"] == "symbol":
                        v = str(v).strip().upper()
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    raise ValueError(f"{p['label']}: not a valid value ({v})")
                if "min" in p and isinstance(v, (int, float)) and v < p["min"]:
                    raise ValueError(f"{p['label']}: at least {p['min']}")
                if "max" in p and isinstance(v, (int, float)) and v > p["max"]:
                    raise ValueError(f"{p['label']}: at most {p['max']}")
                out[p["key"]] = v
        return out

    # ---- data the strategy needs: [(symbol, '1h' | '1d')]
    def data_needs(self) -> list:
        return []

    def trade_symbols(self) -> list:
        """ETFs the strategy can hold (for quotes, positions and the benchmark)."""
        return []

    def benchmark_symbol(self) -> str | None:
        return None

    def buffer(self) -> float:
        return float(self.params.get("cash_buffer_pct", 1.0)) / 100.0

    def cash_target(self) -> dict:
        return {}

    def evaluate(self, now) -> dict:
        raise NotImplementedError

    def chart(self, now, rng: str = "1M") -> dict:
        return {"charts": []}

    def describe(self) -> dict:
        return {"rules": [], "flow": "", "tv": ""}

    def next_check(self, now):
        return None

    def is_buy_signal(self, sig: dict) -> bool:
        """A signal (row of the signals table) that starts or increases a position. Money added with
        "wait for the next buy signal" stays in cash until one of these happens after it was added."""
        return sig.get("kind") == "BUY"

    def rebalance_band(self) -> float:
        return float(self.params.get("rebalance_band_pct", 10)) / 100.0
