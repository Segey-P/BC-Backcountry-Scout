# BC Backcountry Scout — Requirements & Functionality

**Version:** 0.2 (Phase 1 deployed; Phase 1.5 polish shipped)
**Date:** April 2026
**Status:** Deployed to Oracle Cloud; iterating on real-world use

> This document covers what BC Backcountry Scout does, who it's for, scope, architecture, data sources, and functional requirements. Updated to reflect Phase 1.5 changes: confirmation flow, alpine weather, HTML reports, unknown-command handler.

---

## 1. Product Overview

### 1.1 What it is

A Telegram-based agent that gives outdoor users in British Columbia a single concise pre-trip report covering road conditions, weather, wildfires, and wildlife activity for a chosen backcountry destination, with optional proactive monitoring.

### 1.2 Who it's for

- Primary user: Squamish-based trail runners, hunters, snowmobilers, backpackers heading into BC backcountry
- Secondary user: Friends of the primary user (small private group, invite-only)
- Usage context: Pre-trip planning the night before; occasional in-field check on weak LTE

### 1.3 Why Telegram (not a website or SMS)

- Works over weak data; bot replies are text-light
- Single channel for both pull (on-demand reports) and push (proactive alerts)
- Free; no per-message cost
- No app install friction for friends already on Telegram
- Bot API is mature and free

### 1.4 What this is *not*

- Not a routing/navigation app (does not replace Google Maps / Gaia)
- Not a hunting regulations lookup tool (Phase 2 at earliest)
- Not a search-and-rescue or emergency tool (explicit disclaimer required)
- Not a weather forecast service in its own right (it surfaces existing forecasts)

---

## 2. Scope

### 2.1 Phase 1 (MVP — what gets built first)

| Module | Purpose |
|---|---|
| Telegram bot interface | Listen for commands, reply with reports, handle inline buttons |
| Session manager | 24h rolling memory of starting point per user |
| Geocoder | Resolve destination names to lat/long, top 3 matches as buttons |
| Route + buffer | Build 5km corridor between start and destination |
| DriveBC monitor | Pull active road events on the corridor |
| Weather module | Current + 24h forecast at destination |
| Wildfire module | Active fires within corridor or within 25km of destination |
| Wildlife/closure module | Recent advisories from WildSafeBC + Squamish news sources |
| Report assembler | Combine all of the above into a single Telegram message |

### 2.2 Phase 2 (after MVP works for you and 2-3 friends)

- **Proactive alerts** — Subscribe to a destination; get pinged when conditions change (road closures, fires, wildlife, weather) in the destination area (not Squamish-specific)
- **Avalanche bulletin integration** — Avalanche Canada API for terrain-specific snowmobile planning
- **Trail "busy-ness" estimate** — Heuristic based on permit/parking, Strava heatmap, or trip reports
- **Air quality** (BC AirHub)
- **Multi-day trip mode** — Hunting trip with fixed basecamp
- **Open access** — Switch from invite-only allowlist to public bot access
- **Advanced analytics** — Trip history, seasonal patterns, user preferences

### 2.3 Phase 3 (only if there's demand)

- Hunting season / regulations lookup
- Snowmobile zone status (open/closed)
- Web dashboard view

### 2.4 Out of scope (do not build)

- User accounts beyond Telegram user_id
- Payment / subscription
- iOS/Android native app
- Generic "ask the AI anything" mode

---

## 3. Architecture

### 3.1 System diagram (logical)

```
[Telegram User]
     ↕  (Telegram Bot API webhook or long-poll)
[Bot Handler]  ─────────────────────────────┐
     ↓                                      │
[Session Manager] ←──── reads/writes ────→ [session.json]
     ↓
[Intent Router]
     ↓
[Geocoder] ──────────→ Nominatim API
                ─────→ BC Geographic Names Web Service
     ↓
[Route + Buffer] ────→ shapely (local lib, no API)
     ↓
[Data Fetchers — run in parallel]
     ├─ DriveBC (Open511)     → api.open511.gov.bc.ca
     ├─ Weather               → Environment Canada / Open-Meteo
     ├─ Wildfire              → BC Wildfire Service open data
     └─ Wildlife/news         → WildSafeBC RSS, Squamish Chief RSS
     ↓
[Report Assembler]
     ↓
[Telegram Bot API] → user
```

### 3.2 Components

| Component | Tech | Notes |
|---|---|---|
| Bot framework | `python-telegram-bot` (v21+) | Async, well-maintained, free |
| Geocoder client | `geopy` for Nominatim; `requests` for BC GNWS | Both free |
| Spatial ops | `shapely` | Local, no API |
| HTTP | `httpx` (async) | For parallel API fetches |
| Storage | Local JSON file (Phase 1); SQLite (Phase 2 when alerts arrive) | No external DB needed yet |
| Hosting | Oracle Cloud always-free tier | Must be always-on |
| Language | Python 3.11+ | |

### 3.3 Why no LLM in the runtime path (Phase 1)

The MVP does not require an LLM at request time. Every step (geocode, fetch, filter, format) is deterministic. Adding an LLM here adds latency, cost, and a hallucination surface for safety-relevant data (road closures, fires).

LLM use is reserved for:
- **Build time:** Claude Code generating the implementation
- **Phase 2:** Optional natural-language summarization of long news articles into one-line warnings (with the original link always included)

---

## 4. Data Sources

### 4.1 DriveBC — Road events

- **Endpoint:** `https://api.open511.gov.bc.ca/events`
- **Auth:** None
- **Format:** JSON (Open511 standard)
- **Rate limit:** Be polite; cache for 5 min minimum
- **Filter logic:** Severity = MAJOR or MODERATE, OR description contains any of: `closed`, `closure`, `avalanche`, `washout`, `rockfall`, `slide`, regardless of severity
  - Reason: Sea-to-Sky closures are routinely classified MODERATE or MINOR but still mean a 1-2 hour delay or full reroute

### 4.2 Geocoding

- **Hybrid approach:** BC GNWS stub → Nominatim live → fuzzy fallback against 35 hardcoded BC features
- **Status:**
  - **BC GNWS:** stubbed (returns hardcoded results for "alice lake" and "mamquam"). Phase 2 to wire up live.
  - **Nominatim:** **live** (`https://nominatim.openstreetmap.org/search`). User-Agent: `BCBackcountryScout/1.0`. Results filtered to BC bounding box (lat 48.3–60.0, lon -139.1 to -114.0). Max 1 req/sec.
  - **Fuzzy fallback:** 35 hardcoded BC features (cities, parks, peaks, FSRs) ranked by bidirectional token-match score
- **Reason for hybrid:** OSM coverage of named backcountry features in BC is patchy; live Nominatim covers cities and major parks well, fuzzy list covers Squamish-corridor specifics

### 4.3 Weather

- **Primary:** Open-Meteo (`https://api.open-meteo.com/v1/forecast`)
  - Free, no API key, generous rate limit
  - Provides temp, wind, precip, freezing level, **snow depth**, **snowfall**, **wind gusts**, **terrain elevation**
- **Alpine detection:** When Open-Meteo reports terrain elevation > 1200 m, the report switches to an alpine block (snow depth, recent snowfall, gusts, freezing-level-vs-terrain warning)
- **Alerts:** Environment Canada BC-wide warnings RSS feed (`https://weather.gc.ca/rss/warning/bc_e.xml`); full CAP XML parsing is Phase 2

### 4.4 Wildfire

- **BC Wildfire Service Open Data:** `https://catalogue.data.gov.bc.ca/dataset/`
  - "BC Wildfire Active Incidents" layer (GeoJSON)
  - Free, no key
- **Filter:** Fires intersecting the route corridor OR within 25km of destination
- **Also surface:** Active fire bans in the relevant fire centre

### 4.5 Wildlife / closures / local advisories

- **WildSafeBC:** RSS/scrape of recent reported sightings filtered to Squamish + corridor area
- **Squamish Chief:** RSS for recent local news (filter for keywords: `bear`, `cougar`, `closure`, `closed`, `trail`)
- **Squamish Facebook (outdoor groups):** Monitor for community advisories (Phase 1.5 if scraping is feasible, else Phase 2)
- **Squamish Fire Department:** Alerts for fire-related closures and restrictions
- **Parks Canada (Garibaldi National Park):** RSS/scrape for trail closures and permit restrictions
- **Hunting BC alerts:** Season dates, closure zones, and wildlife alerts (relevant for hunting trips)
- **Confidence note in output:** These are unofficial / community sources — surface them but tag them as such

### 4.6 Source reliability tagging

Every line in the assembled report carries an implicit reliability tier. The bot doesn't display the tier explicitly but uses it to decide phrasing:

| Tier | Sources | Phrasing |
|---|---|---|
| Official | DriveBC, BC Wildfire, Env Canada | "Closure on Hwy 99..." |
| Semi-official | WildSafeBC | "Bear sighting reported..." |
| Community | News scrape, social | "Local reports mention..." |

---

## 5. Functional Specification

### 5.1 User commands

| Command | Behaviour |
|---|---|
| `/start` | Welcome message + brief explanation + safety disclaimer |
| `/scout <destination>` | Show trip confirmation, then fetch full report on confirm |
| `/from <location>` | Manually set or override the starting point |
| `/whereami` | Show current session state (start point, last destination) |
| `/clear` | Clear the session |
| `/help` | List commands |
| Unknown command (e.g. `/scount`) | Suggest closest match using fuzzy match against known commands |

Sharing a Telegram **Live Location** at any time updates the live GPS slot in the session (Phase 2 — not yet implemented).

### 5.2 The destination-first interaction flow

1. User sends `/scout <destination>`
2. Bot replies "Searching…" (immediate feedback)
3. Bot calls Geocoder → top match (BC-filtered, distance-biased) replaces "Searching…"
4. Bot edits the message into a **trip confirmation card** with two inline buttons:
   - **✅ Scout it** — confirm and fetch
   - **📍 Change start** — switch the starting point in-line
5. Confirmation shows: Start, Destination (full resolved name), Date (today by default)
6. If user taps **Change start**: bot prompts for text input → re-geocodes → edits the same message back into a refreshed confirmation card
7. If user taps **Scout it**: bot edits message to "Fetching conditions…", runs all fetchers in parallel, then edits the same message with the final report
8. Bot updates the session timestamp (rolling 24h)

The entire flow operates on a single Telegram message that progressively edits in place — no clutter, no extra messages.

### 5.3 Geocoding logic

1. Append `British Columbia Canada` to query
2. Try BC Geographic Names Web Service (currently a stub — Phase 2 to wire up live)
3. If <3 results, query **live Nominatim** (`https://nominatim.openstreetmap.org/search`) with `User-Agent: BCBackcountryScout/1.0`
4. Filter Nominatim results to BC bounding box (lat 48.3–60.0, lon -139.1 to -114.0)
5. Deduplicate within 0.5 km, sort by distance to bias point (§5.4)
6. If best match has character-level similarity ≥ 0.85 to the query → return top 3
7. **Fuzzy fallback** (if API results are weak): rank a hardcoded list of 35 BC features (cities, parks, peaks, FSRs) by **bidirectional token-match score** (max of query→name and name→query word coverage at ≥0.80 SequenceMatcher ratio). Threshold: ≥0.50.
   - Bidirectional scoring fixes queries like `iceberg lake whistler` matching `Whistler, BC` (1 of 2 name words match → score 0.50)
8. If still nothing → reply "Couldn't find that in BC. Try adding a region (e.g. 'Alice Lake Squamish') or check spelling."

### 5.4 Starting-point resolution priority

In order:

1. **Manual override** — Most recent `/from` command in the current session
2. **Live GPS** — Telegram Live Location shared in the last 30 min (if available, prefer this)
3. **Session memory** — `starting_point` from `session.json` if rolling 24h has not lapsed
4. **Prompt user** — Bot asks for a starting point and pauses

### 5.5 Session memory

- **Storage:** `session.json` keyed by Telegram `user_id`
- **Rolling 24h expiry:** Every successful interaction (any command that resolves to a report) refreshes the `last_active` timestamp
- **Expiry check:** On each request, if `now - last_active > 24h`, the session is considered expired and starting point is cleared
- **Privacy-first retention:** Sessions purged weekly (not monthly) to minimize stored data
- **Schema:**

```json
{
  "<user_id>": {
    "starting_point": {
      "name": "Squamish, BC",
      "lat": 49.7016,
      "lon": -123.1558,
      "source": "manual"
    },
    "live_gps": {
      "lat": 49.7016,
      "lon": -123.1558,
      "received_at": "2026-04-25T14:30:00Z"
    },
    "last_active": "2026-04-25T14:30:00Z",
    "last_destination": {
      "name": "Alice Lake Provincial Park",
      "lat": 49.77,
      "lon": -123.12
    }
  }
}
```

### 5.6 Route + buffer logic

- Build a `LineString` between starting point and destination using `shapely`
- Apply a 5km buffer (in projected coordinates — use BC Albers EPSG:3005 to avoid lat/lon distortion errors)
- Result is a polygon used for spatial intersection with road events and fires
- For destination-only checks (weather, nearby fires), use a 25km circular buffer around the destination point

### 5.7 Parallel fetch behaviour

- All data fetchers run concurrently with a hard 8-second timeout per fetcher
- If a fetcher times out or errors, its section in the report shows "Data unavailable" rather than blocking the whole report
- Total report should arrive in under 10 seconds in the normal case

### 5.8 Report format

Assembled message uses Telegram **HTML** mode (switched from MarkdownV2 in Phase 1.5 because real API data — road event headlines, negative temperatures, fire names — contained unescaped special characters and Telegram silently rejected the messages). All dynamic content is `html.escape()`'d. Target length: under 1500 chars so it fits one Telegram message and renders fast on weak signal.

```
🌲 <b>Alice Lake Provincial Park</b>
From: Squamish, BC

🚨 <b>Safety</b>
✅ No major road events on Hwy 99
⚠️ Bear sighting reported 2 days ago — Mamquam Spawning Channel
✅ No active wildfires within 25km
✅ No wildlife advisories

🌤️ <b>Weather (next 24h)</b>
Now: 12°C, 8 km/h
Next 12h: 0.0mm precip, freezing level 1800m

🚗 <b>Driving conditions</b>
Highways open, normal flow

<i>Report generated: 14:32 PDT. Conditions change fast — verify before you go.</i>
```

**Alpine variant** — when destination terrain elevation > 1200 m (auto-detected from Open-Meteo), the weather block is replaced with:

```
🏔️ <b>Alpine Weather (1900m)</b>
Now: -3°C, 40 km/h, gusts 75
Next 12h: 0.5mm precip, freezing level 1700m
Snow depth: 60cm
Recent snowfall: 5.0cm
⚠️ Freezing level near or below terrain
```

If a fetcher times out:

```
🌤️ <b>Weather</b>
Data unavailable (timeout)
```

### 5.9 Error states

| Situation | Behaviour |
|---|---|
| Geocoder returns nothing | Reply "Couldn't find that in BC. Try adding a region (e.g. 'Alice Lake Squamish') or check spelling." |
| User types unknown command (e.g. `/scount`) | Suggest closest match using `difflib.get_close_matches` against known commands: "Did you mean **/scout**? Try: `/scout <destination>`" |
| Pending confirmation expires (session purged before Scout it tapped) | Reply "Session expired. Please run /scout again." |
| Individual fetcher times out | That section shows "Data unavailable" or is omitted; report still delivered |
| Out-of-BC destination | Nominatim BC-bounding-box filter returns no matches → standard "couldn't find" reply |
| Telegram API outage | Best-effort retry handled by `python-telegram-bot`; logged via `journalctl` |

---

## 6. Non-Functional Requirements

| Property | Target |
|---|---|
| Response latency (full report) | < 10s p95 |
| Geocoding response | < 2s |
| Concurrent users | 5–20 (small private group) |
| Uptime | Best-effort 95% (this is a side project, not a paid service) |
| Logs | Rotate weekly; do not log Telegram message content beyond the destination string |
| Privacy | No data sold, shared, or analyzed beyond what's needed for the report |

---

## 7. Safety & Disclaimers

### 7.1 Mandatory disclaimer (shown on `/start` and once per session)

> This bot provides best-effort information from public sources. It is **not** a substitute for checking official sources, telling someone your trip plan, carrying communication and navigation, or knowing the area. Conditions change fast in the BC backcountry. Always verify before you go.

### 7.2 What the bot will *never* do

- Tell the user a route is "safe"
- Provide search-and-rescue information
- Recommend whether to go or not go on a trip
- Provide medical or emergency advice

### 7.3 What the bot will *always* do

- Surface the source for every significant claim
- Tag community/unofficial reports as such
- Show "Data unavailable" rather than infer or hallucinate
- Include the timestamp on every report

---

## 8. Data & Privacy

- **Stored per user:** Telegram `user_id`, last starting point, last live GPS (with timestamp), last destination, session timestamp
- **Not stored:** Telegram username, message history, contact info
- **Retention:** Session data auto-expires per the rolling 24h rule; expired records purged weekly to minimize stored data
- **Sharing:** None
- **Deletion:** `/clear` removes the user's session record entirely
- **Access control:** Phase 1 — invite-only via JSON allowlist. Phase 2+ — can switch to open access if desired

---

## 9. Glossary

- **FSR** — Forest Service Road
- **Open511** — Standard for transportation event data; what DriveBC uses
- **BC GNWS** — BC Geographic Names Web Service (provincial place-name authority)
- **Buffer (spatial)** — A polygon that wraps a line/point at a fixed distance; here, the "search corridor" along the route
- **Rolling expiry** — A timer that resets on every interaction, vs. a hard expiry that runs from a fixed start time
