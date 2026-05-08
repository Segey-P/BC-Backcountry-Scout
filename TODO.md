# BC Backcountry Scout — Status & Next Steps

## v1.5 Advanced Features Implementation

### Fire Bans (Network Issue)
- [x] Investigate 403 errors from Oracle Cloud on BC gov endpoints — documented in TROUBLESHOOTING.md
  - Root cause: IP reputation filtering by BC gov services
  - Recommended: Contact BC government OGC to allowlist Oracle Cloud IP/ASN ranges
  - Current: Graceful degradation (fire bans return empty, no errors)

## Completed in v1.5

- [x] 24h Max Wind Gusts — fetched and displayed in Weather block
- [x] Air Quality (AQHI) — Open-Meteo, human-readable levels 🟢🟡🟠🔴🟣, Safety block Apr–Oct
- [x] DriveBC Webcam — nearest cam link in Driving block, 24h cache
- [x] BC Parks Advisories — proximity-based (20km), urgency emoji, bcparks.ca links
- [x] Geocoder accuracy — relevance scoring over distance bias
- [x] Report clutter — single "No immediate hazards" line when nothing detected
- [x] Peak Temperature Estimate (Lapse Rate) — +500m elevation estimate in Weather block (alpine only)
- [x] Compact "Offline" Report — 💾 Save Offline button, text-only format for weak signal conditions
