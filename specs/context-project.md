# Project Context — BC Backcountry Scout

## Overview
- **Purpose:** Telegram bot that pulls road conditions, weather, wildfires, and wildlife advisories for a BC backcountry destination in one message.
- **Stack:** Python + python-telegram-bot
- **Deploy:** Self-hosted (Oracle Cloud, systemd service)
- **Telegram bot:** @bc_scout_bot

## Deploy Command
```bash
ssh bcscout "cd ~/bc-backcountry-scout && git pull && sudo systemctl restart bcscout"
```

## Key Files
| File | Purpose |
|---|---|
| `TODO.md` | Current next steps (read by Project Hub dashboard) |
| `specs/` | Authoritative spec documents |
| `deploy/server.md` | Server details, deploy commands |
