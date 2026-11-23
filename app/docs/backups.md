<!--{"title": "Backups & restore", "group": "Server"}-->
# Backups & restore

- Everything (settings, strategies, money, orders, fills, the equity history, logs and the price cache) is in `data/bot.db` (SQLite).
- **Nightly on the server**: a copy every night at 03:30 Bangkok in `data/backups/` (`bot-YYYY-MM-DD.db`), the last **7 days**
  kept. Prices the bot can download again are left out, so the copies are small; the Webull keys and LINE token stay in them
  (encrypted), because these copies never leave the server. Each copy is opened and checked by SQLite after it is made;
  a failed check is a Health warning and a LINE message.
- **Download (Settings → Server & backups, or the Dashboard reminder)**: a fresh copy made at that moment, compressed
  (`webull-bot-YYYY-MM-DD-no-secrets.db.gz`), **without secrets**: no Webull app key or secret, no LINE token, no password
  (the hash is blanked), no sign-ins or sign-in IPs, and no prices the bot can download again. Keep it on your Mac or in
  Google Drive: the nightly copies are all on the same server, so they are lost with it.
- **Reminder**: when nothing was downloaded in the last 7 days (or never), the Dashboard shows *No backup downloaded for N
  days* with a Download button. It goes away when you download.
- **Prices left out**: daily bars, hourly bars of the last ~2 years and the backtests' full histories. Hourly gold and silver
  bars older than 700 days stay in every backup, because Yahoo keeps only ~730 days of hourly bars. The long gold and silver
  history the backtests read is a file in the code, not in the database. The "last downloaded" marks are removed too, so a
  restored copy downloads every price again within a few minutes of starting.

## Restore

1. Stop the bot: `systemctl stop th-strategy-bot`.
2. Put the copy in place. From a nightly copy: `cp data/backups/bot-2026-11-23.db data/bot.db`. From a download (upload it
   to the server first): `gunzip -c webull-bot-2026-11-23-no-secrets.db.gz > data/bot.db`.
3. `chown -R thbot:thbot /opt/webull_bot1` and start: `systemctl start th-strategy-bot`.
4. A downloaded copy has no password: set one with
   `cd /opt/webull_bot1 && sudo -u thbot .venv/bin/python -m app.reset_password`. Then enter the Webull app key and secret
   (Webull page) and the LINE token (LINE alerts page) again, and approve the Webull login in the app.
5. Wait a few minutes: prices download by themselves; the Health check shows when data is fresh.

- Keep `data/secret.key` too if you restore a nightly copy on a new server: it decrypts the Webull and LINE secrets in it.
- Forgot the password: on the server `cd /opt/webull_bot1 && sudo -u thbot .venv/bin/python -m app.reset_password`; on the
  Mac `./.venv/bin/python -m app.reset_password`.
