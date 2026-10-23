<!--{"title": "Project layout", "group": "Developers"}-->
# Project layout

```
app/
  main.py          web API, login, static app
  engine.py        the loop: data → evaluate → plans → send → LINE → daily jobs
  strategies/      base.py (plugin API), signal.py (Supertrend, Donchian), regime.py
  execution.py     plans, lots, retries, equity snapshots
  brokers.py       Paper broker, Webull OpenAPI (test + live)
  ledger.py        each strategy's cash and shares per mode
  moneyops.py      add / withdraw / move
  notify.py        LINE queue, instant / digest / off, quiet hours, quota
  health.py        nightly cross-check, independent indicator recompute
  marketdata.py    Yahoo (or offline CSV) prices, quotes
  metals.py        GC/SI 4H bars, contract rolls (bars.py, rolls.py)
  indicators.py    Pine-exact RMA, ATR, Supertrend, DMI/ADX, Donchian
  markethours.py   US sessions and holidays (update yearly)
  views.py         data for each page
  docs/            this manual
  static/          the web app (no build step; TradingView Lightweight Charts in vendor/)
scripts/make_demo_data.py   offline demo prices
tests/                      pytest
deploy/                     Caddy snippet
```
