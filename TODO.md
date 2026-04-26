# BC Backcountry Scout — Build Status

## Phase 1 Complete ✓

All 10 modules shipped and tested.

---

## Phase 1.5 — Debug & Feature Polish ✓

- [x] Real Nominatim geocoding (replaced stub — all BC locations now resolve)
- [x] Bidirectional fuzzy token scoring (fixes "iceberg lake whistler" → Whistler)
- [x] Expanded `_KNOWN_FEATURES` list (35 BC locations vs 20)
- [x] Alpine weather section (auto-detected when destination > 1200m: snow depth, snowfall, gusts, freezing level warning)
- [x] Unknown-command handler with typo suggestions (/scount → did you mean /scout?)
- [x] 93 tests pass

---

## Deploy to Oracle Cloud (Next)

- [ ] Provision Oracle Cloud Always-Free ARM VM (Ubuntu 22.04 LTS)
- [ ] SSH in and run: `bash deploy/setup.sh`
- [ ] Edit `.env` with real `TELEGRAM_BOT_TOKEN`
- [ ] Start service: `sudo systemctl start bcscout`
- [ ] Smoke-test: send `/start` from Telegram, then `/scout Whistler`

---

## Phase 2 Backlog

- [ ] Telegram inline keyboard buttons for common commands (no typing required)
- [ ] Proactive alerts when conditions change for an active session's destination
- [ ] Open-access mode (remove JSON allowlist)
- [ ] Live GPS location support via Telegram location message
- [ ] Environment Canada CAP alert full XML parsing (replace RSS stub)
- [ ] Avalanche forecast (Avalanche Canada public API)
- [ ] BC Geographic Names Web Service (GNWS) real integration (replace stub)

---

## Key Decisions Locked

| Decision | Choice | Notes |
|---|---|---|
| Phase 2 priority | Inline buttons + proactive alerts | Buttons: no-typing UX; alerts: destination-aware |
| Geocoding | Nominatim live + fuzzy fallback | GNWS stub retained for later |
| Alpine threshold | 1200m | Open-Meteo terrain elevation, auto-detected |
| Allowlist storage | JSON file | Switchable to open access in Phase 2 |
| Session purging | Weekly | Privacy-first |
| Geocoding bias | Live GPS → last point → Squamish default | |
| Report format | Concise, emoji-friendly, <1500 chars | Alpine section auto-added for high destinations |
| Language | English only | Phase 2 if demand |
