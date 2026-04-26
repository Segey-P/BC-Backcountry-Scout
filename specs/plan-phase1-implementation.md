# Phase 1 Implementation Plan

**Version:** 0.1  
**Target completion:** Functional MVP (you + 2–3 friends can use it)

---

## 1. Module build order

Build modules sequentially. Each ships testable in isolation before the next starts.

| # | Module | Duration (est.) | Deliverable |
|---|---|---|---|
| 1 | Telegram skeleton | 1–2h | Bot responds to `/start` with disclaimer; nothing else |
| 2 | Session manager | 2–3h | JSON read/write, rolling 24h expiry, unit tests |
| 3 | Geocoder | 3–4h | BC GNWS + Nominatim hybrid, top-3 button reply |
| 4 | Route + buffer | 2–3h | Shapely logic, no API dependency, unit tests |
| 5 | DriveBC fetcher | 2–3h | Single fetcher, format road section of report |
| 6 | Weather fetcher | 2–3h | Open-Meteo, format weather section |
| 7 | Wildfire fetcher | 2–3h | BC Open Data, format fire section |
| 8 | Wildlife/news fetcher | 3–4h | RSS scrape, format wildlife section |
| 9 | Report assembler | 2–3h | Wire everything together, parallel fetches, timeout handling |
| 10 | Hosting setup | 1–2h | Deploy to Oracle Cloud always-free tier |

---

## 2. Testing approach

- **Unit tests:** Session expiry math, buffer geometry, geocoder ranking, severity filter
- **Integration test:** End-to-end with a known destination ("Alice Lake Provincial Park") that hits all fetchers
- **Manual test set:** 10 destinations covering:
  - Squamish town (common reference point)
  - Garibaldi Park (well-known destination)
  - A Forest Service Road (FSR-[number])
  - A typo or fuzzy match
  - An out-of-BC location (should be rejected)
  - An ambiguous name (should offer multiple matches)

---

## 3. What "done" looks like for Phase 1

- [ ] You can send "Alice Lake" from your phone in Squamish and get a complete report under 10 seconds
- [ ] A friend on a different Telegram account can do the same
- [ ] The bot survives 48 hours running unattended without crashing
- [ ] All 10 manual test destinations work as expected
- [ ] Invite-only allowlist is enforced
