# Deploy quick reference — webull-bot1.kemmachat.com (165.245.188.124), no Docker

Full guide: `app/docs/deploy.md` (in the app: Docs & manual → Deploy on DigitalOcean).

```bash
# first time (as root)
apt update && apt install -y git python3-venv python3-pip
useradd --system --create-home --home-dir /home/thbot --shell /usr/sbin/nologin thbot
cd /opt && git clone https://github.com/wkemmachat/webull_bot1.git && cd webull_bot1
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # COOKIE_SECURE=1, SCHEDULER_ENABLED=1, PUBLIC_URL, APP_USERNAME, APP_PASSWORD
mkdir -p data && chown -R thbot:thbot /opt/webull_bot1 && chmod 600 .env
cp deploy/th-strategy-bot.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now th-strategy-bot
# Caddy: add Caddyfile.snippet to /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy

# update
cd /opt/webull_bot1 && git pull && .venv/bin/pip install -r requirements.txt && chown -R thbot:thbot . && systemctl restart th-strategy-bot

# logs · restart · stop · status
journalctl -u th-strategy-bot -f
systemctl restart th-strategy-bot
systemctl stop th-strategy-bot
systemctl status th-strategy-bot --no-pager

# password reset
cd /opt/webull_bot1 && sudo -u thbot .venv/bin/python -m app.reset_password
```
