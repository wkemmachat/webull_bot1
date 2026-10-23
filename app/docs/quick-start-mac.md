<!--{"title": "Run it on your Mac (VS Code)", "group": "Start here"}-->
# Run it on your Mac (VS Code)

Try everything on your Mac in **Paper** mode first. When it behaves for a week, put the same code on DigitalOcean and turn the
Mac's scheduler off.

## 1 · Get the code

```
cd ~/WeBullBot            # or wherever you keep it
git clone https://github.com/wkemmachat/webull_bot1.git
cd webull_bot1
code .
```

If the files are already in your WeBullBot folder, just open that folder in VS Code.

## 2 · Start the bot

1. In VS Code choose **Terminal → New Terminal** and run `./run.sh`. The first run creates `.venv`, installs the packages and copies
   `.env.example` to `.env`. It needs Python 3.9 or newer: the Mac's own `python3` works
   (if it is missing, run `xcode-select --install`); Python 3.12 from python.org is a little faster.
2. Open `http://127.0.0.1:8000` and create your **username and password** (an email address works as the username;
   the password needs 10+ characters). The bot has **one login, only yours**: there is no sign-up for anyone else.
3. Or press **F5 → "Run TH Strategy Bot"** to start it with the debugger.

```
# .env on your Mac
COOKIE_SECURE=0          # http://localhost has no HTTPS
SCHEDULER_ENABLED=1      # set 0 once the server is live
PUBLIC_URL=http://127.0.0.1:8000
```

> **Only one scheduler.** If the Mac and the server both run the scheduler, every LINE alert comes twice and both copies trade.

## 3 · First minutes

- On the first start the bot downloads about two years of hourly gold and silver futures and six years of daily ETF bars
  (1–2 minutes). The Dashboard fills in after that.
- Each strategy gets **$10,000 paper money** and follows its current signal. Orders only go out while the US market is open
  (20:30–03:00 Bangkok in US summer time, 21:30–04:00 in winter).

## 4 · Connect LINE and Webull test

Go to **LINE alerts**, paste the channel token, add yourself as a recipient and press **Send test message**. Then open
**Webull**, paste the test keys and press **Connect**; switch **Webull test** on in **Settings → Trading modes**.

## Offline demo

No internet? `python scripts/make_demo_data.py` writes random demo prices to `data/csv`; start with `DATA_SOURCE=csv` in `.env`.
These prices are not real.
