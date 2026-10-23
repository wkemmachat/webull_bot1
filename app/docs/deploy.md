<!--{"title": "Deploy on DigitalOcean", "group": "Server"}-->
# Deploy on DigitalOcean

Server **165.245.188.124**, address **https://webull-bot1.kemmachat.com**. The bot runs in Docker on `127.0.0.1:8012` and the
server's Caddy adds HTTPS in front, next to your other web apps. Nothing else on the server is changed.

## 1 · Push the code from your Mac

```
cd ~/WeBullBot/webull_bot1
git init                       # first time only
git add .
git status                     # .env, data/ and .venv must NOT be listed
git commit -m "TH Strategy Bot"
git branch -M main
git remote add origin https://github.com/wkemmachat/webull_bot1.git    # first time only
git push -u origin main
```

`.env`, `data/` and `.venv/` are in `.gitignore`: your password, keys, LINE token and database never go to GitHub.

## 2 · DNS

Add an **A record** `webull-bot1` → `165.245.188.124` where kemmachat.com's DNS is managed. Check from the Mac:
`dig +short webull-bot1.kemmachat.com` → `165.245.188.124`.

## 3 · On the server

```
ssh root@165.245.188.124
sudo ss -ltnp | grep ':8012 '          # nothing printed = port 8012 is free
cd /opt
sudo git clone https://github.com/wkemmachat/webull_bot1.git
cd /opt/webull_bot1
sudo cp .env.example .env
sudo nano .env
```

In `.env` on the server:

```
COOKIE_SECURE=1
SCHEDULER_ENABLED=1
PUBLIC_URL=https://webull-bot1.kemmachat.com
APP_USERNAME=wkemmachat@gmail.com
APP_PASSWORD=your-long-password
DATA_SOURCE=yahoo
BOT_PORT=8012
```

No quotes, no spaces, avoid `#` and `$` in the password. Then:

```
sudo mkdir -p data
sudo docker compose up -d --build
sudo docker compose logs -f --tail 50      # wait for "Application startup complete", Ctrl+C to leave
curl -s http://127.0.0.1:8012/api/health   # {"ok": true, ...}
```

## 4 · Caddy

```
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%F)
sudo nano /etc/caddy/Caddyfile             # paste deploy/Caddyfile.snippet at the end
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Open https://webull-bot1.kemmachat.com and sign in with APP_USERNAME / APP_PASSWORD. (The create-login page only works on the
bot's own computer, so a stranger cannot claim the login.)

## 5 · Turn the Mac's scheduler off

Set `SCHEDULER_ENABLED=0` in the Mac's `.env` and restart it. Only one copy may trade and send LINE.

## 6 · Webull and LINE on the server

The server starts with a fresh database: enter LINE and Webull again in the web app. Webull API keys can be limited to an IP
address: use **165.245.188.124**. Connect from the server's Webull page and approve in the Webull app.
