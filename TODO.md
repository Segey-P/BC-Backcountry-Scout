# BC Backcountry Scout — TODO

## Active

- [ ] Iterate on Phase 1 — fix real-world issues found in use
- [x] Google Maps Geocoding API — replaced Nominatim; same GOOGLE_MAPS_API_KEY as ETA
- [ ] Natural language input via Gemini — parse free-text into structured intent (skill + destination + destination_type + trip_date); see spec-nlp-intent-router.md
- [ ] Context-aware report assembly — use destination_type (mountain/city/lake/trail) and trip_date to select report sections; future-date trips use forecast weather + normal ETA, no current traffic

## Phase 2 Backlog

- [ ] Proactive alerts when conditions change for an active session's destination
- [ ] Live GPS location support via Telegram location message (enables dynamic geocoding bias)
- [ ] Inline keyboard buttons for `/scout`, `/from` (no-typing UX beyond confirmation flow)
- [ ] Alpine freezing level trends (24h forecast visualization in weather report)
- [ ] Open-access mode (remove JSON allowlist)
- [ ] Environment Canada CAP alert full XML parsing (replace RSS stub)
- [ ] BC Geographic Names Web Service (GNWS) real integration (replace stub)

---

## Key Decisions Locked

| Decision | Choice | Notes |
|---|---|---|
| Phase 2 priority | Proactive alerts | Destination-aware, when active session exists |
| Geocoding primary | Google Maps API (planned) | Replaces Nominatim; better BC backcountry coverage |
| Geocoding fallback | 35-feature fuzzy list | Last resort; GNWS stub retained for later |
| Alpine threshold | 1200m | Open-Meteo terrain elevation, auto-detected |
| Report format | HTML (was MarkdownV2) | Robust escaping for real API data |
| Trip flow | Confirmation step before fetch | Inline buttons: Scout it / Change start |
| Allowlist storage | JSON file | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first |
| Geocoding bias | Live GPS → last point → Squamish default | |
| Language | English only | Phase 2 if demand |
| NLP at runtime | Gemini for intent parsing only | Not in data-fetch path; deterministic pipeline unchanged |
| Context-aware reports | destination_type + trip_date fields from NLP | Mountain→alpine/avalanche; city→driving/ETA; future date→forecast, no live traffic |
| Wildfire corridor check | Both route corridor AND 25km around destination | Already implemented in wildfire.py |
| Local news sources | Squamish Chief RSS live; Facebook + AllTrails out of scope | |
