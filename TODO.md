# Phase 1 Build Queue

## Refinement Complete ✓

All decisions finalized. Specs locked. Ready for implementation.

---

## Build Checklist (Next Actions)

- [x] **Module 1: Telegram skeleton** — `bot.py` + `requirements.txt`. BotHandler class, /start with disclaimer, all other commands stubbed, async long-poll.
- [x] Module 2: Session manager — `session.py` + `tests/test_session.py`. All 11 tests pass.
- [x] Module 3: Geocoder — `geocoder.py` + `tests/test_geocoder.py`. 15 tests pass.
- [x] Module 4: Route + buffer — `route_buffer.py` + `tests/test_route_buffer.py`. 9 tests pass.
- [x] Module 5: DriveBC fetcher — `fetchers/drivebc.py` + `tests/test_drivebc.py`. 13 tests pass.
- [x] Module 6: Weather fetcher — `fetchers/weather.py` + `tests/test_weather.py`. 7 tests pass.
- [x] Module 7: Wildfire fetcher — `fetchers/wildfire.py` + `tests/test_wildfire.py`. 9 tests pass.
- [x] Module 8: Wildlife/news fetcher — `fetchers/wildlife_news.py` + `tests/test_wildlife_news.py`. 17 tests pass.
- [x] Module 9: Report assembler — `report_assembler.py` + `tests/test_report_assembler.py`. 6 tests pass.
- [x] Module 10: Oracle Cloud hosting setup — `deploy/bcscout.service` + `deploy/setup.sh` + `.env.example`

---

## Phase 1 Complete ✓

All 10 modules shipped. Bot is ready to deploy.

**Next: Deploy to Oracle Cloud**

- [ ] Provision Oracle Cloud Always-Free ARM VM (Ubuntu 22.04 LTS)
- [ ] SSH in and run: `bash deploy/setup.sh`
- [ ] Edit `.env` with real `TELEGRAM_BOT_TOKEN`
- [ ] Start service: `sudo systemctl start bcscout`
- [ ] Smoke-test: send `/start` from Telegram
- [ ] Phase 2 planning — proactive alerts for trip destination area

---

## Key Decisions Locked

| Decision | Choice | Notes |
|---|---|---|
| Phase 2 priority | Proactive alerts (A) | For trip destination area; Phase 2 feature |
| Proactive alerts scope | Destination-aware | Only if session is active |
| Allowlist storage | JSON file (B) | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first approach |
| Geocoding bias | Live GPS → last point (C/B fallback) | Prefer real-time location |
| News sources | WildSafeBC, Squamish Chief, Parks Canada, Hunting BC, Fire Dept | Expanded from original spec |
| Report format | As-is | Concise, emoji-friendly, <1500 chars |
| Language | English only | Phase 2 if demand |
| Timeline | Soft | No hard deadline |

---

## Phase 2 Backlog (post-deploy)

- Proactive alerts when conditions change for an active session's destination
- Open-access mode (remove JSON allowlist)
- Live GPS location support via Telegram location message
- Environment Canada CAP alert full XML parsing (replace RSS stub)
