# BC Backcountry Scout — v1.5 Advanced Features Spec

This document outlines the implementation details for the advanced features brainstormed to enhance the pre-trip report with more safety and context data.

## 1. Solar & Twilight Enhancements
*   **Source:** Open-Meteo Forecast API (`daily` parameters).
*   **Data Points:** `sunrise`, `sunset`, `civil_twilight_end`.
*   **Logic:** 
    *   Calculate "Last Light" based on `civil_twilight_end`.
    *   If the user is scouting in the afternoon, add a proactive warning: *"🔦 Last light at [time]. Bring a headlamp if staying late."*
*   **Display:** Add to the Weather block.

## 2. 24h Max Wind Gusts
*   **Source:** Open-Meteo Forecast API (`hourly` or `daily` parameters).
*   **Data Point:** `wind_gusts_10m_max`.
*   **Logic:** Instead of just showing the "current" gust, show the maximum gust expected in the next 24 hours.
*   **Display:** *"Wind: 15 km/h, max gusts 45 km/h expected today."*

## 3. Air Quality (AQHI)
*   **Source:** Open-Meteo Air Quality API (`https://air-quality-api.open-meteo.com/v1/air-quality`).
*   **Variables:** `pm2_5`, `nitrogen_dioxide`, `ozone`.
*   **Calculation:** Use the Canadian AQHI formula:
    `AQHI = (10/10.4) * 100 * [(e^(0.000537 * O3) - 1) + (e^(0.000871 * NO2) - 1) + (e^(0.000487 * PM2.5) - 1)]`
    *Note: Pollutants must be in specific units (ppb for O3/NO2, µg/m³ for PM2.5).*
*   **Display:** Add an "Air Quality" line to the Safety block if AQHI > 3 (Moderate risk).

## 4. DriveBC Webcam Integration
*   **Source:** DriveBC HighwayCams GeoJSON (`https://catalogue.data.gov.bc.ca/dataset/6b39a910-6c77-476f-ac96-7b4f18849b1c/resource/a9d52d85-8402-4ce7-b2ac-a2779837c48a/download/webcams.json`).
*   **Logic:** 
    *   Cache the GeoJSON locally (it updates infrequently).
    *   Find the camera with the shortest Haversine distance to the destination or any point on the route.
    *   Generate a link: `https://www.drivebc.ca/images/{id}.jpg`.
*   **Display:** Add to the Driving block: `[📷 View nearest webcam: Hwy 99 at Alice Lake]`.

## 5. BC Parks & RSTBC Advisories
*   **Source:** BC Parks REST API (`https://bcparks.api.gov.bc.ca/api/public-advisories`).
*   **Logic:** 
    *   Query the API for advisories.
    *   Filter by keyword matching the destination name (e.g., "Garibaldi", "Stawamus Chief").
    *   Include "Urgency" level to prioritize "High" alerts.
*   **Display:** Add to the Safety block alongside WildSafeBC advisories.

## 6. Peak Temperature Estimate (Lapse Rate)
*   **Logic:**
    *   If destination elevation (from Open-Meteo) is significantly higher (>500m) than the base station elevation OR if the name contains "Peak", "Mount", or "Mountain".
    *   Apply the standard environmental lapse rate: `-6.5°C per 1,000m`.
*   **Display:** *"Summit temp (est): -2°C (based on 2100m elevation)."*

## 7. Compact "Offline" Report
*   **Logic:** Add an inline button "💾 Save Offline".
*   **Action:** Sends a second, very short message containing only the critical text (Roads, Fires, Weather, Last Light) with no HTML formatting, designed to be easy to read/screenshot on very weak signal.
