# Deploy quick reference — webull-bot1.kemmachat.com (165.245.188.124)

Full guide: `app/docs/deploy.md` (in the app: Docs & manual → Deploy on DigitalOcean).

```bash
# first time
cd /opt && sudo git clone https://github.com/wkemmachat/webull_bot1.git && cd webull_bot1
sudo cp .env.example .env && sudo nano .env    # COOKIE_SECURE=1, SCHEDULER_ENABLED=1, PUBLIC_URL, APP_USERNAME, APP_PASSWORD
sudo mkdir -p data && sudo docker compose up -d --build
# Caddy: add Caddyfile.snippet to /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy

# update
cd /opt/webull_bot1 && sudo git pull && sudo docker compose up -d --build

# logs · restart · stop
sudo docker compose logs -f --tail 100
sudo docker compose restart
sudo docker compose down

# password reset
sudo docker compose exec bot python -m app.reset_password
```
