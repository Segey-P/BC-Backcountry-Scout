# Build Prompts by Module — Copy/Paste for Claude Code

Each prompt is pre-filled with the module number, spec sections, and expected deliverable. Paste one prompt at a time into Claude Code to build one module.

---

## Module 1: Telegram Skeleton

```
Read specs/spec-scout-requirements.md sections 5.1 and 6. 
Implement bot.py with:

- BotHandler class that initializes the python-telegram-bot Telegram.Bot
- `/start` command handler that sends the safety disclaimer (from spec §7.1)
- All other commands defined but stubbed (return "Coming soon")
- Async long-poll or webhook setup (your choice; long-poll is simpler for MVP)
- Graceful shutdown

No data fetching yet. Just listen and reply to /start.

Test: Can you /start the bot and see the disclaimer?
```

---

## Module 2: Session Manager

```
Read specs/spec-scout-requirements.md section 5.5.

Implement session.py with:
- load_session(user_id: int) -> dict | None
- save_session(user_id: int, data: dict) -> None
- is_expired(session: dict) -> bool (uses 24h rolling expiry against last_active)
- clear_session(user_id: int) -> None
- refresh_session(user_id: int) -> None (updates last_active timestamp)

Storage is session.json at the project root. Use file locking (fcntl on macOS/Linux, msvcrt on Windows) to handle concurrent writes.

Schema from spec §5.5.

Write pytest tests covering:
- New user (no session exists)
- Fresh session (created < 1 hour ago)
- Expired session (> 24h old)
- Refresh (verifies last_active updates)
- Clear (user deleted from file)

Deliverable: session.py + tests/test_session.py. All tests pass.
```

---

## Module 3: Geocoder

```
Read specs/spec-scout-requirements.md sections 4.2 and 5.3.

Implement geocoder.py with:
- geocode_destination(query: str, bias_point: tuple = SQUAMISH_DEFAULT) -> list[GeoResult]
  Returns top 3 matches as GeoResult(name, lat, lon, source)
- Hybrid logic: BC GNWS first, Nominatim fallback
- Distance sorting (prefer results closer to bias_point)
- Fuzzy matching fallback if <3 results (built-in list of ~20 common Squamish area features: Alice Lake, Mamquam FSR, Garibaldi Park, etc.)
- Exact string similarity check: if best match is >85% similar to query, return top 3; else trigger fuzzy fallback

Don't include the full Nominatim/GNWS API integration yet — stub them to return hardcoded results for "Alice Lake" and "Mamquam" so you can test the ranking logic.

Write pytest tests covering:
- Exact match (query = "Alice Lake")
- Typo (query = "alce lake") — fuzzy fallback expected
- Out-of-BC location (query = "Seattle") — should return empty or fallback
- Distance sorting (two results equidistant, one closer — closer one ranks first)

Deliverable: geocoder.py + tests/test_geocoder.py. All tests pass.
```

---

## Module 4: Route + Buffer

```
Read specs/spec-scout-requirements.md section 5.6.

Implement route_buffer.py with:
- build_route_corridor(start: tuple[lat, lon], destination: tuple[lat, lon]) -> shapely.Polygon
  Creates a 5km buffer around a LineString between start and destination, using BC Albers projection (EPSG:3005)
- destination_buffer(destination: tuple[lat, lon], radius_km=25) -> shapely.Polygon
  Creates a circular buffer around destination

Use shapely + pyproj for projections. No API calls.

Write pytest tests covering:
- Basic corridor (start to destination, 5km buffer applied correctly)
- Projection consistency (same result whether you project before or after buffer)
- Edge case: start == destination (should be a circular buffer only, not a line)

Deliverable: route_buffer.py + tests/test_route_buffer.py. All tests pass.
```

---

## Module 5: DriveBC Fetcher

```
Read specs/spec-scout-requirements.md section 4.1.

Implement fetchers/drivebc.py with:
- fetch_drivebc_events(corridor_polygon: shapely.Polygon) -> list[RoadEvent]
  Each RoadEvent has: headline, description, severity, geometry, last_updated
- Filter logic: Severity in [MAJOR, MODERATE] OR description contains any of [closed, closure, avalanche, washout, rockfall, slide]
- Spatial filtering: event geometry intersects corridor_polygon
- Caching: cache the Open511 response for 5 min (use a simple dict with timestamp; no external cache)

For now, make a real HTTP call to api.open511.gov.bc.ca/events and filter in memory. Don't parse every event type — focus on events that have a geometry and are relevant to BC.

Write pytest tests covering:
- Filter logic (MAJOR event included, MINOR + "closed" in description included, MINOR + no keywords excluded)
- Spatial filter (event intersecting polygon vs. outside polygon)
- Cache expiry (fetch again after 5 min, not before)

Deliverable: fetchers/drivebc.py + tests/test_drivebc.py. All tests pass.
```

---

## Module 6: Weather Fetcher

```
Read specs/spec-scout-requirements.md section 4.3.

Implement fetchers/weather.py with:
- fetch_weather(lat: float, lon: float) -> WeatherReport
  WeatherReport contains: current_temp, current_wind, current_precip, forecast_24h, freezing_level, timestamp
- Data source: Open-Meteo (https://api.open-meteo.com/v1/forecast)
- Also fetch Env Canada CAP alerts for the area (if any) and include in report
- Timeout: 3 seconds per fetch (part of the 8-second per-fetcher budget from §5.7)

Write pytest tests covering:
- Real fetch to Open-Meteo for Squamish (49.7016, -123.1558) — verify structure
- Timeout handling (mock httpx to timeout)
- Missing data (some fields may be null) — report should handle gracefully

Deliverable: fetchers/weather.py + tests/test_weather.py. Tests may mock Open-Meteo to avoid rate limits.
```

---

## Module 7: Wildfire Fetcher

```
Read specs/spec-scout-requirements.md section 4.4.

Implement fetchers/wildfire.py with:
- fetch_wildfire(corridor_polygon: shapely.Polygon, destination: tuple[lat, lon]) -> list[FireIncident]
  Each FireIncident has: name, stage_of_control, size_hectares, geometry, distance_to_destination_km
- Filter logic: Fires intersecting corridor_polygon OR within 25km of destination point
- Data source: BC Wildfire Service open data (https://catalogue.data.gov.bc.ca/dataset/)
  Download the "BC Wildfire Active Incidents" GeoJSON (or query the WMS endpoint)
- Also check for active fire bans in the relevant fire centre

Timeout: 3 seconds.

Write pytest tests covering:
- Spatial filter (fire intersecting vs. outside)
- Distance filter (fire within 25km vs. beyond)
- Empty result (no fires) → return empty list gracefully

Deliverable: fetchers/wildfire.py + tests/test_wildfire.py.
```

---

## Module 8: Wildlife & News Fetcher

```
Read specs/spec-scout-requirements.md section 4.5.

Implement fetchers/wildlife_news.py with:
- fetch_wildlife_news(corridor_polygon: shapely.Polygon, destination_name: str) -> list[Advisory]
  Each Advisory has: source (WildSafeBC | Squamish Chief | Parks Canada | Hunting BC | etc.), category (bear | cougar | closure | avalanche | hunting | etc.), summary, link, date
- Data sources (MVP):
  - WildSafeBC RSS (parse + filter for Squamish/corridor area mentions)
  - Squamish Chief RSS (filter for keywords: bear, cougar, closure, closed, trail)
  - Parks Canada (Garibaldi) — trail closures, permit info (RSS or scrape)
  - Hunting BC alerts — season dates, closure zones, wildlife alerts
  - Squamish Fire Department — fire-related closures and restrictions
  - (Phase 1.5) Squamish Facebook outdoor groups (if feasible to monitor)
- Tag each advisory with its reliability tier (official for Parks/Hunting BC, semi-official for WildSafeBC, community for news/Facebook)

Timeout: 3 seconds.

For MVP, stub most sources and return hardcoded sample advisories for key sources (WildSafeBC, Squamish Chief, Parks Canada). Real RSS/scraping can be added incrementally after the skeleton works.

Write pytest tests covering:
- Filter logic (keyword matching, category assignment)
- Deduplication (same article from two sources → only one in output)
- Empty result → return []
- Source tagging (reliability tier correct for each source)

Deliverable: fetchers/wildlife_news.py + tests/test_wildlife_news.py.
```

---

## Module 9: Report Assembler

```
Read specs/spec-scout-requirements.md section 5.8.

Implement report_assembler.py with:
- assemble_report(
    destination_name: str,
    start_name: str,
    road_events: list[RoadEvent],
    weather: WeatherReport,
    fires: list[FireIncident],
    advisories: list[Advisory]
  ) -> str

- Output format: Telegram MarkdownV2 (from §5.8)
- Target length: < 1500 chars
- Structure:
  🌲 Destination name
  From: start point
  
  🚨 Safety section (roads, advisories, fires)
  🌤️ Weather section
  🚗 Driving section
  
  Timestamp + disclaimer

- Parallel fetch integration:
  - run_all_fetchers(destination_geom, start, destination) -> dict
  - Uses asyncio to fetch all 5 sources in parallel
  - 8-second timeout per fetcher
  - If a fetcher fails/times out, show "Data unavailable" instead of crashing

Write an end-to-end test with known data (Alice Lake):
- Mock all fetchers to return sample data
- Verify report is generated, under 1500 chars, valid MarkdownV2 format

Deliverable: report_assembler.py + tests/test_report_assembler.py.
```

---

## Module 10: Hosting Setup

```
Read specs/ref-hosting-options.md.

You will deploy to Oracle Cloud always-free tier.

Deliverable:
1. Oracle Cloud VM provisioning (or document the steps if already done)
2. Deploy script or instructions to start the bot on the Oracle VM
3. Logging setup (rotate weekly, log to /var/log/bcbackcountryscout/)
4. Systemd service file (or equiv.) so bot auto-restarts on reboot
5. Test: From your phone, /start the bot and /scout Alice Lake; verify you get a report

Recommended Python runtime: Python 3.11+ with venv, using systemd to manage the bot process.
```

---

## Notes

- Each prompt assumes the previous modules are complete.
- All modules should have unit tests. Run `pytest` before marking a module done.
- Once all 9 modules are done, Module 10 (hosting) is the final step to get the bot live.
- If a module is blocked (e.g., waiting for API docs), note it in `TODO.md` and move to the next independent module.
