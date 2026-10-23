<!--{"title": "Deploy on DigitalOcean", "group": "Server"}-->
# Deploy on DigitalOcean

Server **165.245.188.124**, address **https://webull-bot1.kemmachat.com**. The bot runs as a normal Linux service (systemd) on
`127.0.0.1:8012` with its own Python environment, under its own user `thbot`. The server's Caddy adds HTTPS in front, next to your
other web apps. Nothing else on the server is changed. (A Docker setup is also included: `docker-compose.yml`.)

## 1 · Push the code from your Mac

```
cd ~/WeBullBot/webull_bot1
git add . && git commit -m "describe the change" && git push
```

`.env`, `data/` and `.venv/` are in `.gitignore`: your password, keys, LINE token and database never go to GitHub.

## 2 · DNS

An **A record** `webull-bot1` → `165.245.188.124`. Check: `dig +short webull-bot1.kemmachat.com`.

## 3 · On the server (DigitalOcean web console, as root)

```
python3 --version                       # 3.9 or newer
apt update && apt install -y git python3-venv python3-pip
ss -ltnp | grep ':8012 '                # nothing printed = port 8012 is free
useradd --system --create-home --home-dir /home/thbot --shell /usr/sbin/nologin thbot
cd /opt && git clone https://github.com/wkemmachat/webull_bot1.git
cd /opt/webull_bot1
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
```

`.env` on the server:

```
COOKIE_SECURE=1
SCHEDULER_ENABLED=1
PUBLIC_URL=https://webull-bot1.kemmachat.com
APP_USERNAME=wkemmachat@gmail.com
APP_PASSWORD=your-long-password
DATA_SOURCE=yahoo
```

```
mkdir -p data && chown -R thbot:thbot /opt/webull_bot1 && chmod 600 .env
cp deploy/th-strategy-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now th-strategy-bot
systemctl status th-strategy-bot --no-pager
curl -s http://127.0.0.1:8012/api/health
```

## 4 · Caddy

Add `deploy/Caddyfile.snippet` to the end of `/etc/caddy/Caddyfile` (keep a backup), then
`caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy`.

## 5 · Turn the Mac's scheduler off

`SCHEDULER_ENABLED=0` in the Mac's `.env`. Only one copy may trade and send LINE.

## 6 · Webull and LINE on the server

Fresh database: enter LINE and Webull again in the web app.

**Webull API keys** (from Webull Thailand's developer docs, Oct 2026):

1. webull.co.th → your photo → **Developer Tool** → **API Management → My Application**: apply for API access. Webull reviews it
   (1–2 working days; you get an email).
2. **API Management → API Keys Management**: application name `TH Strategy Bot`, permissions **Market data** and **Trading**
   (both), IP whitelist **165.245.188.124**, 2FA on. Generate the key (SMS code + trading password). Copy the **App Key** and
   **App Secret**; *Reset Key* gives a new secret if you lose it.
3. In the bot: **Webull → Live API keys** → paste → Save → **Connect**. Webull sends an SMS code; enter it in the Webull app
   (it pops up, or Menu → Messages → OpenAPI Notifications → Check Now) **within 5 minutes**. The token is saved on the server;
   the Webull page shows until when it is valid.

**Webull test** needs no application: on the Webull page press **Use #1** (one of Webull's three public shared test accounts on
th-api.uat.webullbroker.com), Connect, then Test connection. Everyone shares those accounts, so their orders and positions
change without you.
