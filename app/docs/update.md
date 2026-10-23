<!--{"title": "Update after a git push", "group": "Server"}-->
# Update after a git push

On the server (DigitalOcean console):

```
cd /opt/webull_bot1
git pull
.venv/bin/pip install -r requirements.txt
chown -R thbot:thbot /opt/webull_bot1
systemctl restart th-strategy-bot
systemctl status th-strategy-bot --no-pager
```

The database migrates itself on start. Health: `curl -s http://127.0.0.1:8012/api/health` on the server, or
https://webull-bot1.kemmachat.com/api/health. Logs: `journalctl -u th-strategy-bot -f`.
