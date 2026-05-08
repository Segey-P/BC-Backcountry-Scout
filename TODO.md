# BC Backcountry Scout — TODO

## v1.5 Advanced Features Implementation

### Fire Bans (Network Issue)
- [ ] Investigate why DataBC WFS and BCWS ArcGIS return 403 from Oracle Cloud — may need proxy or IP allowlisting.

## Completed in v1.5

- [x] 24h Max Wind Gusts — fetched and displayed in Weather block
- [x] Air Quality (AQHI) — Open-Meteo, human-readable levels 🟢🟡🟠🔴🟣, Safety block Apr–Oct
- [x] DriveBC Webcam — nearest cam link in Driving block, 24h cache
- [x] BC Parks Advisories — proximity-based (20km), urgency emoji, bcparks.ca links
- [x] Geocoder accuracy — relevance scoring over distance bias
- [x] Report clutter — single "No immediate hazards" line when nothing detected
- [x] Peak Temperature Estimate (Lapse Rate) — +500m elevation estimate in Weather block (alpine only)
- [x] Compact "Offline" Report — 💾 Save Offline button, text-only format for weak signal conditions
