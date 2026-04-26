# Hosting Decision Matrix — Phase 1

A Telegram bot requires always-on compute. This document compares options, ranked by recommendation for BCBackcountryscout.

---

## Recommendations Summary

| Option | Cost | Setup Effort | Reliability | Recommendation |
|---|---|---|---|---|
| **Oracle Cloud always-free ARM VM** | $0 | Medium | Excellent | ✅ **First choice** |
| Raspberry Pi at home | $0 marginal | Low | Good (depends on home internet) | Fallback if Oracle problematic |
| Fly.io free tier | $0 (shrinking) | Low | Good | Second choice if Oracle unavailable |
| Railway free tier | $0 | Low | Good | Acceptable, requires monitoring |
| Render free tier | $0 | Low | Poor (spins down) | ❌ Not suitable for a bot |

---

## Detailed Comparison

### 1. Oracle Cloud Always-Free ARM VM ✅ Recommended

**Cost:** $0 (truly always-free, not trial)  
**Setup:** ~30–60 min to provision VM + SSH access

**Pros:**
- Genuinely always-free tier (not a trial)
- 4 OCPU ARM VM + generous storage
- Full root access; can run anything
- Reliable for a small side project
- No risk of sudden billing

**Cons:**
- More infrastructure management than cloud function platforms
- Requires basic Linux/SSH knowledge
- Account closure risk if unused for 7 months (rare but possible)

**Setup steps (rough):**
1. Create Oracle Cloud free account
2. Provision an Always-Free Compute VM (Ubuntu 22.04 LTS ARM)
3. Open port 22 (SSH) + port for Telegram webhook (if using webhook mode)
4. Upload code via git clone or scp
5. Create systemd service to auto-start bot on reboot
6. Test: SSH in, check bot is running, send a test message

**Estimated cost:** $0/month, forever (assuming no abuse)

---

### 2. Fly.io Free Tier

**Cost:** $0 if within 3 shared-cpu-1x instances (free allowance)  
**Setup:** ~20 min (Docker + flyctl CLI)

**Pros:**
- Easy deployment (Docker-based, very fast)
- Global edge locations (fast response)
- Generous free tier for small projects

**Cons:**
- Free tier is shrinking year over year
- Storage for `session.json` is limited; need to use persistent volume (costs $$ once quota exceeded)
- Terraform/CLI learning curve for beginners

**Verdict:** Good if Oracle becomes unavailable, but not the first choice for a persistent bot.

---

### 3. Raspberry Pi at Home

**Cost:** ~$0 marginal (if you already own one)  
**Setup:** ~30 min (OS + dependencies)

**Pros:**
- Full control; no cloud vendor lock-in
- No service interruption risk
- Can always see logs locally

**Cons:**
- Home internet outages take the bot down
- Requires Pi running 24/7 (modest electricity cost)
- Static IP or dynamic DNS setup needed for webhook mode
- Limited troubleshooting from outside the home

**Use case:** Fallback if Oracle account has issues, or secondary redundancy.

---

### 4. Railway Free Tier

**Cost:** $5/month free allowance; can fit this project  
**Setup:** ~15 min

**Pros:**
- Simple deployment (git push)
- Persistent storage included
- No Docker needed

**Cons:**
- Not as generous as Oracle or Fly
- Requires monitoring to stay in free tier
- Vendor lock-in

**Verdict:** Acceptable, but Oracle is better.

---

### 5. Render Free Tier (Not Recommended)

**Cost:** $0 but limited  
**Issue:** Free instances spin down after 15 min of inactivity. A Telegram bot needs to be always-on; spinning down breaks long-poll or webhook mode.

**Verdict:** ❌ **Do not use for this project.**

---

## Recommended: Oracle Cloud

### Why Oracle

1. **Truly always-free.** No trial expiration, no shrinking quotas.
2. **Adequate resources.** 4 OCPU, 24 GB RAM is massive overkill for a small bot, but included in free tier.
3. **Full OS control.** Can run cron jobs, systemd services, custom logging.
4. **No vendor creep.** Standard Ubuntu; if you ever leave, code is portable.

### Setup Checklist

- [ ] Create Oracle Cloud account (free tier sign-up)
- [ ] Provision Always-Free Compute VM (Ubuntu 22.04 LTS, ARM shape)
- [ ] Configure SSH keypair and security group (allow port 22, any HTTP/HTTPS if webhook)
- [ ] Clone BCBackcountryscout repo to VM
- [ ] Install Python 3.11+ and dependencies (`pip install -r requirements.txt`)
- [ ] Create `session.json` at project root
- [ ] Create systemd service file (`/etc/systemd/system/bcbackcountryscout.service`)
- [ ] Start service and enable auto-start: `sudo systemctl enable bcbackcountryscout`
- [ ] Test from phone: send `/start` command to bot
- [ ] Set up log rotation (logrotate or systemd journal)
- [ ] Document the VM's IP/DNS for future reference

### Systemd Service Example

```ini
[Unit]
Description=BC Backcountry Scout Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/BCBackcountryscout
ExecStart=/home/ubuntu/BCBackcountryscout/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Fallback Plan

If Oracle becomes problematic:
1. **Short-term:** Raspberry Pi at home (if you have one) or Fly.io free tier
2. **Long-term:** Evaluate Railway or other emerging platforms

---

## Actual Deployment (Phase 1)

Hosting is Module 10 (last step). Modules 1–9 will be built and tested locally. Once all modules pass tests, you'll deploy to Oracle Cloud and verify end-to-end.
