# BC Backcountry Scout — TODO

## v1.5 Advanced Features Implementation

### Peak Temperature Estimate (Lapse Rate)
- [ ] Implement logic to estimate peak temperature based on destination elevation and lapse rate.
- [ ] Display estimated summit temperature in Weather block when applicable.

### Compact "Offline" Report
- [ ] Add "💾 Save Offline" button to the report message.
- [ ] Implement function to generate a text-only, minimal report for weak signal conditions.

### Fire Bans (Network Issue)
- [ ] Investigate why DataBC WFS and BCWS ArcGIS return 403 from Oracle Cloud — may need proxy or IP allowlisting.

## Completed in v1.5

- [x] 24h Max Wind Gusts — fetched and displayed in Weather block
- [x] Air Quality (AQHI) — Open-Meteo, human-readable levels 🟢🟡🟠🔴🟣, Safety block Apr–Oct
- [x] DriveBC Webcam — nearest cam link in Driving block, 24h cache
- [x] BC Parks Advisories — proximity-based (50km), urgency emoji, bcparks.ca links
- [x] Geocoder accuracy — relevance scoring over distance bias
- [x] Report clutter — single "No immediate hazards" line when nothing detected
