<!--{"title": "Update after a git push", "group": "Server"}-->
# Update after a git push

```
cd /opt/webull_bot1 && sudo git pull && sudo docker compose up -d --build
```

The database migrates itself on start. Health: `curl https://webull-bot1.kemmachat.com/api/health` (or on the server `curl -s http://127.0.0.1:8012/api/health`).
