# Server — BC Backcountry Scout

## Hosting

| Field | Value |
|---|---|
| Provider | Oracle Cloud |
| Host | bcscout-vnic |
| User | ubuntu |
| Bot directory | `/home/ubuntu/bc-backcountry-scout` |
| Python venv | `/home/ubuntu/bc-backcountry-scout/venv` |

## systemd Service

| Field | Value |
|---|---|
| Service name | `bcscout` |
| Unit file | `/home/ubuntu/bc-backcountry-scout/deploy/bcscout.service` |

### Common commands

```bash
sudo systemctl restart bcscout       # restart after code/config changes
sudo systemctl status bcscout        # quick health check
sudo journalctl -u bcscout -n 50 --no-pager   # last 50 log lines
sudo journalctl -u bcscout -f        # live log tail
```

## Deploying a new version

```bash
cd /home/ubuntu/bc-backcountry-scout
source venv/bin/activate
git pull origin main
pip install -r requirements.txt      # only needed when requirements change
sudo systemctl restart bcscout
sudo journalctl -u bcscout --since "1 minute ago" --no-pager
```

## Verifying the alert job loaded

After restart, look for this line in logs:

```
INFO bot — Proactive alert job registered (30-min interval)
```

If missing, APScheduler is not installed. Run `pip install -r requirements.txt` inside the venv.

## Notes

- httpx logs full Telegram API URLs at INFO level, which includes the bot token in the path. Consider setting httpx logger to WARNING in production (`logging.getLogger("httpx").setLevel(logging.WARNING)`).
- Session data is stored in `session.json` in the bot directory. Back up before destructive operations.
- Weekly session purge is configured in `session.py` (`_EXPIRY_HOURS = 24`).
