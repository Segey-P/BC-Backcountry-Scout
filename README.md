# BC Backcountry Scout

**Status:** Refinement phase  
**Owner:** Sergey Pochikovskiy

## Overview

BCBackcountryscout is a Telegram-based agent for BC outdoor enthusiasts. Send a destination name, get a pre-trip report covering road conditions (DriveBC), weather, active wildfires, and wildlife advisories. Designed for Squamish-based trail runners, hunters, snowmobilers, and backpackers heading into BC backcountry.

**Phase 1:** MVP for you + 2–3 friends. Invite-only.

---

## Architecture

- **Bot:** Python + `python-telegram-bot`
- **Data sources:** DriveBC (Open511), Open-Meteo, BC Wildfire Service, WildSafeBC, Squamish Chief
- **Storage:** Local JSON (session state); SQLite in Phase 2
- **Hosting:** Oracle Cloud always-free ARM VM
- **Cost:** $0/month

---

## Project Structure

```
specs/
├── spec-scout-requirements.md     — Requirements, architecture, data sources, functional spec
├── spec-scout-open-questions.md   — 9 refinement questions (answer before build)
├── plan-phase1-implementation.md  — Build sequence (10 modules)
├── context-build-prompts.md       — Copy/paste prompts for Claude Code (one per module)
└── ref-hosting-options.md         — Hosting decision matrix + Oracle Cloud setup

_archived_original-spec.md         — Original spec document (superseded by specs/ folder)
TODO.md                            — Current next actions
CLAUDE.md                          — AI agent instructions
```

---

## Before Build Starts

1. Read `specs/spec-scout-open-questions.md`
2. Answer all 9 refinement questions
3. Update specs based on your answers
4. Once locked, use `context-build-prompts.md` module-by-module with Claude Code

---

## Build Checklist (Phase 1)

Module completion order (each has tests):

- [ ] **1. Telegram skeleton** — `/start` command + disclaimer
- [ ] **2. Session manager** — Rolling 24h session memory
- [ ] **3. Geocoder** — Destination name → lat/lon (BC GNWS + Nominatim)
- [ ] **4. Route + buffer** — Spatial polygon around trip corridor
- [ ] **5. DriveBC fetcher** — Road events API
- [ ] **6. Weather fetcher** — Open-Meteo + Env Canada alerts
- [ ] **7. Wildfire fetcher** — BC Wildfire Service
- [ ] **8. Wildlife/news fetcher** — WildSafeBC + Squamish Chief RSS
- [ ] **9. Report assembler** — Combine all data, parallel fetches, <10s response
- [ ] **10. Hosting setup** — Deploy to Oracle Cloud, systemd service

---

## Phase 2 (After MVP Stable)

Chose one:
- Proactive alerts (subscribe to location, get pushed on changes)
- Avalanche integration (Avalanche Canada for snowmobile routes)
- Trail busy-ness estimate

---

## How to Use This Project

### For Development
```bash
cd /path/to/project
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest  # Run all tests
```

### For Deployment
See `specs/ref-hosting-options.md` for Oracle Cloud setup instructions.

---

## Safety & Privacy

- **Disclaimer:** Mandatory on `/start` and once per 24h session. Conditions change fast; verify before you go.
- **Data stored:** Telegram user_id, last starting point, session expiry, last destination
- **Data NOT stored:** Telegram username, message history, contact info
- **Invite-only:** Bot rejects unauthorized user_ids
- **Retention:** Sessions auto-expire after 24h inactivity; older records purged monthly

---

## Questions?

See `specs/spec-scout-open-questions.md` for refinement decisions.

