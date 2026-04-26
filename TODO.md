# Phase 1 Build Queue

## Refinement Complete ✓

All decisions finalized. Specs locked. Ready for implementation.

---

## Build Checklist (Next Actions)

- [x] **Module 1: Telegram skeleton** — `bot.py` + `requirements.txt`. BotHandler class, /start with disclaimer, all other commands stubbed, async long-poll.
- [x] Module 2: Session manager — `session.py` + `tests/test_session.py`. All 11 tests pass.
- [x] Module 3: Geocoder — `geocoder.py` + `tests/test_geocoder.py`. 15 tests pass.
- [ ] Module 4: Route + buffer
- [ ] Module 5: DriveBC fetcher
- [ ] Module 6: Weather fetcher
- [ ] Module 7: Wildfire fetcher
- [ ] Module 8: Wildlife/news fetcher (includes Parks Canada, Hunting BC)
- [ ] Module 9: Report assembler
- [ ] Module 10: Oracle Cloud hosting setup

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

## Ready to Build

Next step: Copy the Module 1 prompt from `specs/context-build-prompts.md` and paste into Claude Code on the web (claude.ai/code).
