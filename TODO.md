# BC Backcountry Scout — TODO

- [ ] BC Geographic Names Web Service (GNWS) real integration (replace 39-feature fuzzy fallback list)
- [ ] Deploy updated requirements.txt to server (`pip install -r requirements.txt` — adds APScheduler for /watch job)
- [ ] focus=driving: post-report "Full scout" button to upgrade to full report from same destination

---

## Key Decisions Locked

| Decision | Choice | Notes |
|---|---|---|
| Phase 2 priority | Proactive alerts | Implemented: /watch + /unwatch; 30-min background job via PTB JobQueue |
| Geocoding primary | Google Maps API | Replaces Nominatim; better BC backcountry coverage |
| Geocoding fallback | 43-feature fuzzy list | Last resort; GNWS stub to be replaced in next session |
| Geocoder quality gate | 0.55 similarity threshold | Filters wrong Google results before fuzzy merge |
| Focused queries | focus field on Intent | NLP sets focus; only relevant fetchers run; focused assembler used |
| 3-day weather | elevation + freezing level + Windy link | Available via button or "weather at X" NLP query |
| Alpine threshold | 1200m | Open-Meteo terrain elevation, auto-detected |
| Report format | HTML (was MarkdownV2) | Robust escaping for real API data |
| Trip flow | Confirmation step before fetch | Inline buttons: Scout it / Change start |
| Allowlist storage | JSON file | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first |
| Geocoding bias | Live GPS → last point → Squamish default | GPS location message now supported |
| Language | English only | Phase 2 if demand |
| NLP at runtime | Gemini for intent parsing only | Not in data-fetch path; deterministic pipeline unchanged |
| Context-aware reports | destination_type + trip_date fields from NLP | Mountain→alpine/avalanche; city→driving/ETA; future date→forecast, no live traffic |
| Wildfire corridor check | Both route corridor AND 25km around destination | Already implemented in wildfire.py |
| Local news sources | Squamish Chief RSS live; Facebook + AllTrails out of scope | |
| EC alerts parsing | Proper ElementTree XML (Atom + RSS 2.0) | Replaced fragile line-by-line scan |
| Freezing level trend | ↑↓→ in report (24h window, ±150m threshold) | Added to weather section |
| Proactive alerts job | APScheduler via python-telegram-bot[job-queue] | /watch stores dest in session; job runs every 30 min |
