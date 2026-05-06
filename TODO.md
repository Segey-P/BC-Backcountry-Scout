# BC Backcountry Scout — TODO

## v1.5 Advanced Features Implementation

### Solar & Twilight Enhancements
- [ ] Fetch `sunrise`, `sunset`, `civil_twilight_end` from Open-Meteo.
- [ ] Add "Last Light" warning to weather block.

### 24h Max Wind Gusts
- [ ] Fetch `wind_gusts_10m_max` from Open-Meteo.
- [ ] Update weather block to display max gusts.

### Air Quality (AQHI)
- [ ] Fetch `pm2_5`, `nitrogen_dioxide`, `ozone` from Open-Meteo Air Quality API.
- [ ] Implement Canadian AQHI calculation logic.
- [ ] Add AQHI status to Safety block if risk is moderate or higher.

### DriveBC Webcam Integration
- [ ] Cache DriveBC webcam GeoJSON data.
- [ ] Implement logic to find nearest webcam to destination/route.
- [ ] Add link to nearest webcam image in Driving block.

### BC Parks & RSTBC Advisories
- [ ] Query BC Parks REST API for advisories.
- [ ] Filter advisories by destination name and urgency.
- [ ] Add relevant advisories to Safety block.

### Peak Temperature Estimate (Lapse Rate)
- [ ] Implement logic to estimate peak temperature based on destination elevation and lapse rate.
- [ ] Display estimated summit temperature in Weather block when applicable.

### Compact "Offline" Report
- [ ] Add "💾 Save Offline" button to the report message.
- [ ] Implement function to generate a text-only, minimal report for weak signal conditions.
