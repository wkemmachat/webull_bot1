<!--{"title": "Backups & restore", "group": "Server"}-->
# Backups & restore

- Everything (settings, strategies, money, orders, prices, logs) is in `data/bot.db` (SQLite).
- A copy is made every night at 03:30 Bangkok in `data/backups/` and kept 30 days. **Settings → Download backup now** makes one
  and downloads it.
- Keep `data/secret.key` too: it encrypts the stored Webull and LINE secrets.
- Restore: stop the bot, copy the backup over `data/bot.db`, start again.
- Forgot the password: `docker compose exec bot python -m app.reset_password` (or `python -m app.reset_password` without Docker).
