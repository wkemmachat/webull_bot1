# TH Strategy Bot

A web app and trading bot for **Webull Thailand** that runs seven strategies on one account, each with its own money and books:

| Strategy | Signal | Trades |
|---|---|---|
| Gold #1 · Supertrend + ADX | COMEX gold 4H, Supertrend(30, 2.5), ADX(14) > 20 | UGL / SGOV |
| Gold #2 · Supertrend 30/2.5 | COMEX gold 4H | UGL / SGOV |
| Silver #1 · Donchian 30/15 | COMEX silver 4H | AGQ / SGOV |
| Silver #2 · Supertrend 10/3 | COMEX silver 4H | AGQ / SGOV |
| QLD regime | QQQ daily: SMA200, SMA50, 20-day vol gate 30% | QLD / BIL / GLD |
| 2x Semis regime | SMH daily, vol gate 40% | USD / BIL / GLD |
| QLD + Trend + bear-dip | QQQ daily: above SMA200, or RSI(2) < 5 dips below it (exit > SMA5) | QLD / BIL |

- **Paper, Webull test and Live** modes, each with its own books ($10,000 paper money per strategy).
- **Split orders**: N lots × M minutes from a start time (22:00 Bangkok for metals, the market open for regimes), sells before buys,
  limit orders with retries.
- **LINE alerts** (Messaging API): instant / digest / off per event, quiet hours, digest times, per-strategy switch, quota.
- **Money per strategy**: add, withdraw (sells evenly if needed) and move between strategies.
- **Health check**: nightly read-only cross-check of books vs the broker, data, orders, and an independent indicator recompute.
- **TradingView charts** with each strategy's own indicators (Supertrend + ADX pane; QQQ and QLD for the regime).
- Login (username + password, lockout), a full manual inside the app (Docs & manual), and a plugin API for new strategies.

## Run on your Mac

```bash
./run.sh            # creates .venv, installs, copies .env, starts on http://127.0.0.1:8000
```

or open the folder in VS Code and press **F5 → Run TH Strategy Bot**. Needs Python 3.9+ (the Mac's own python3 works; python.org 3.12 is faster).
Create your username and password on the first page.

Offline demo (random prices): **F5 → Run (offline demo prices)**, or

```bash
./.venv/bin/python scripts/make_demo_data.py --dir data-demo/csv
DATA_SOURCE=csv DATA_DIR=data-demo ./.venv/bin/python -m uvicorn app.main:app --port 8001
```

## Tests

```bash
./.venv/bin/python -m pytest
```

## Deploy (DigitalOcean, Docker + Caddy)

See `app/docs/deploy.md` (also in the app under *Docs & manual → Deploy on DigitalOcean*). In short:

```bash
git clone https://github.com/wkemmachat/webull_bot1.git && cd webull_bot1
cp .env.example .env    # COOKIE_SECURE=1, PUBLIC_URL=https://webull-bot1.kemmachat.com, SCHEDULER_ENABLED=1, APP_USERNAME/PASSWORD
docker compose up -d --build
```

Only one copy may run the scheduler: set `SCHEDULER_ENABLED=0` on the Mac once the server trades.

## Layout

```
app/            FastAPI app, engine, strategies/, execution, brokers, LINE, health check, docs/, static/ (web app)
scripts/        make_demo_data.py
tests/          pytest (offline)
deploy/         Caddyfile.snippet
```

Research and signals are for education, not financial advice. Leveraged ETFs can lose a lot quickly.
