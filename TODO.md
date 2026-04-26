# BC Backcountry Scout — TODO

## Active

- [ ] Smoke-test deployed bot end-to-end:
  - `/scout alice watersprite lake` → confirmation card appears with two buttons
  - Tap **Scout it** → message edits to "Fetching conditions…" then full report
  - Tap **Change start** → type new start → confirmation refreshes in place
  - `/scout vancouver` and `/scout whistler` resolve correctly
  - High-elevation destination (e.g. Elfin Lakes) shows 🏔️ Alpine Weather section
  - `/scount whistler` triggers typo suggestion
- [ ] Iterate on Phase 1 — fix any real-world issues found in use

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
| Geocoding | Nominatim live + 35-feature fuzzy fallback | GNWS stub retained for later |
| Alpine threshold | 1200m | Open-Meteo terrain elevation, auto-detected |
| Report format | HTML (was MarkdownV2) | Robust escaping for real API data |
| Trip flow | Confirmation step before fetch | Inline buttons: Scout it / Change start |
| Allowlist storage | JSON file | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first |
| Geocoding bias | Live GPS → last point → Squamish default | |
| Language | English only | Phase 2 if demand |
