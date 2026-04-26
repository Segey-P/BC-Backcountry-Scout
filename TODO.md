# BC Backcountry Scout — TODO

## Active

- [ ] Iterate on Phase 1 — fix real-world issues found in use
- [ ] Trailforks integration — trail conditions + ride/hike reports (bear sightings, trail damage, current conditions)
- [ ] Natural language input via Gemini — parse free-text like "I want to go to Whistler from Vancouver" into structured bot skills

## Phase 2 Backlog

- [ ] Proactive alerts when conditions change for an active session's destination
- [ ] Live GPS location support via Telegram location message (enables dynamic geocoding bias)
- [ ] Inline keyboard buttons for `/scout`, `/from` (no-typing UX beyond confirmation flow)
- [ ] Alpine freezing level trends (24h forecast visualization in weather report)
- [ ] Open-access mode (remove JSON allowlist)
- [ ] Environment Canada CAP alert full XML parsing (replace RSS stub)
- [ ] BC Geographic Names Web Service (GNWS) real integration (replace stub)
- [ ] Facebook outdoor groups monitoring (hard — anti-scraping; low priority vs. Trailforks)

---

## Key Decisions Locked

| Decision | Choice | Notes |
|---|---|---|
| Phase 2 priority | Proactive alerts | Destination-aware, when active session exists |
| Geocoding | Nominatim live + 35-feature fuzzy fallback | GNWS stub retained for later |
| Alpine threshold | 1200m | Open-Meteo terrain elevation, auto-detected |
| Report format | HTML (was MarkdownV2) | Robust escaping for real API data |
| Trip flow | Confirmation step before fetch | Inline buttons: Scout it / Change start |
| Allowlist storage | JSON file | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first |
| Geocoding bias | Live GPS → last point → Squamish default | |
| Language | English only | Phase 2 if demand |
| NLP at runtime | Gemini for intent parsing only | Not in data-fetch path; deterministic pipeline unchanged |
| Local news sources | Squamish Chief RSS live; Facebook skipped | Trailforks API preferred over Facebook |
