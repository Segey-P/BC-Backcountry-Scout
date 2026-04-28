# BC Backcountry Scout — NLP Intent Router (Gemini)

**Version:** 0.3
**Date:** April 2026
**Status:** Implemented — live on main

---

## 1. Problem (original) / Status

Originally the bot only responded to slash commands. Natural sentences were ignored.
Additionally, every query returned the full report regardless of what the user asked about.

Both problems are now solved. NLP is live behind `NLP_ENABLED=true`. The system prompt
has been tuned through one production bug (scout triggers too narrow → "unknown" returned
for valid queries like "Weather at Watersprite?") and a geocoder quality-gate fix was
shipped alongside it.

---

## 2. Solution

A thin **intent router** layer inserted between Telegram message receipt and the existing
command handlers. Gemini parses free-text into a structured intent — including
destination type and trip date — then dispatches to the existing pipeline.

The report assembler uses destination type and trip date to select and prioritise sections.

The deterministic data pipeline (geocoder → fetchers → report assembler) is **not changed**.
Gemini only touches the user's input string, not any safety-relevant data.

---

## 3. Architecture

### 3.1 Where it sits

```
[Telegram message]
       ↓
[Message handler — bot.py]
       ↓
  Is it a /command?
  ├─ Yes → existing command router (unchanged)
  └─ No  → [Intent Router]
                ↓
           [Gemini API]
                ↓
           Structured intent JSON
                ↓
           Dispatch to existing handler
           (with destination_type + trip_date injected)
                ↓
           [Report Assembler — section selection based on context]
```

Only plain-text messages (no leading `/`) go through the router. Slash commands bypass it entirely — no regression risk.

### 3.2 Intent JSON schema

Gemini is prompted to return one of:

```json
{
  "skill": "scout",
  "destination": "Elfin Lakes, BC",
  "start": "Squamish, BC",
  "destination_type": "mountain",
  "trip_date": "tomorrow",
  "focus": null
}
{
  "skill": "scout",
  "destination": "Brandywine Meadows, BC",
  "start": null,
  "destination_type": "alpine",
  "trip_date": "today",
  "focus": "avalanche"
}
{
  "skill": "scout",
  "destination": "Whistler, BC",
  "start": "Squamish, BC",
  "destination_type": "city",
  "trip_date": "today",
  "focus": "driving"
}
{"skill": "set_start", "location": "Squamish, BC"}
{"skill": "help"}
{"skill": "clear"}
{"skill": "unknown", "reason": "query is not about backcountry trip planning"}
```

**Field definitions:**

| Field | Values | Notes |
|---|---|---|
| `skill` | `scout` \| `set_start` \| `help` \| `clear` \| `unknown` | Always present |
| `destination` | string or null | Include province/region if inferable |
| `start` | string or null | Null → resolved from session |
| `destination_type` | `mountain` \| `alpine` \| `lake` \| `trail` \| `park` \| `city` \| `unknown` | Gemini infers from name; geocoder may refine |
| `trip_date` | `today` \| `tomorrow` \| ISO date string \| null | Null → today |
| `focus` | `driving` \| `avalanche` \| `weather` \| `wildfire` \| `wildlife` \| null | Null = full report. Set only when user clearly asks for a single data type. |

### 3.3 Skills map

| Skill | Maps to | Triggered by |
|---|---|---|
| `scout` | `/scout <destination>` handler | "I want to go to X", "conditions at X", "what's it like at X" |
| `set_start` | `/from <location>` handler | "I'm leaving from X", "starting from X" |
| `help` | `/help` handler | "what can you do", "how do I use this" |
| `clear` | `/clear` handler | "forget my session", "reset" |
| `unknown` | Polite reply listing skills | Anything off-topic |

### 3.4 Fallback chain

1. Gemini returns valid intent → dispatch
2. Gemini returns `unknown` → reply: "I can help with BC backcountry conditions. Try: 'conditions at Alice Lake' or use /scout."
3. Gemini API error / timeout (2s hard limit) → fall through to unknown-command handler, do not block the user
4. Gemini returns malformed JSON → treat as error, same as #3

---

## 4. Context-aware report assembly

The report assembler receives `destination_type` and `trip_date` alongside the fetched data
and selects/prioritises sections accordingly.

### 4.1 Section selection matrix

| Destination type | Trip date | Sections shown | Sections skipped/deprioritised |
|---|---|---|---|
| `mountain` / `alpine` | today | All sections — alpine weather, avalanche, road conditions, wildfire, wildlife, ETA | — |
| `mountain` / `alpine` | future | Tomorrow's alpine forecast, avalanche forecast for that date, normal ETA estimate | Current conditions, current traffic |
| `lake` / `trail` / `park` | today | Weather, road conditions, wildlife, wildfire, ETA | Avalanche (unless elevation > 1200m) |
| `lake` / `trail` / `park` | future | Forecast weather for trip date, wildfire, wildlife, normal ETA | Current conditions, current traffic |
| `city` | today | Road conditions, current ETA, wildfire | Alpine weather, avalanche |
| `city` | future | Normal ETA estimate, weather forecast | Current traffic, current conditions |

### 4.2 "Normal ETA" for future dates

When `trip_date` is not today, current traffic is irrelevant. The ETA fetcher returns a
baseline travel time (no traffic — from the OSRM or Google Routes API) labelled as
"typical driving time" rather than "current ETA". The report notes:
> *ETA: ~1h 45m typical (no live traffic — departure date is [date])*

### 4.3 Avalanche for future dates

The avalanche fetcher already pulls a multi-day forecast from avalanche.ca.
For a future trip date, the assembler selects the forecast for that specific day
rather than today's danger rating.

### 4.4 Weather for future dates

Open-Meteo provides up to 16-day hourly forecast. For a future trip date, the assembler
selects the forecast window for that day (06:00–18:00 local) rather than the next 24h.
Label changes from "Next 24h" to "Forecast for [date]".

---

## 5. Gemini API integration

### 5.1 Model

`gemini-2.0-flash` — fastest and cheapest; intent extraction is a simple structured-output
task, not reasoning-heavy.

### 5.2 Prompt (system)

```
You are an intent classifier for a Telegram bot that provides BC backcountry trip conditions.
Extract the user's intent from their message and return ONLY valid JSON matching this schema:

{
  "skill": <"scout"|"set_start"|"help"|"clear"|"unknown">,
  ...skill-specific fields
}

Skills:
- scout: user wants conditions for a destination.
  Fields: destination (string), start (string or null), destination_type (string), trip_date (string or null)
- set_start: user is setting their starting location. Fields: location (string)
- help: user wants to know what the bot can do. No extra fields.
- clear: user wants to reset their session. No extra fields.
- unknown: message is not about backcountry trip planning. Fields: reason (string)

destination_type values: mountain, alpine, lake, trail, park, city, unknown
trip_date: "today", "tomorrow", or ISO date (YYYY-MM-DD). Null if not mentioned (assume today).

Rules:
- Always return JSON. Never explain or add prose.
- destination and location should include province/region if inferable (e.g. "Whistler, BC").
- If destination is unclear, return unknown.
- Do not invent destinations not mentioned by the user.
- Infer destination_type from the place name where possible (e.g. "Elfin Lakes" → mountain/alpine).
```

### 5.3 Auth

`GEMINI_API_KEY` environment variable. Bot startup fails fast with a clear error if NLP is
enabled and the key is not set.

### 5.4 Rate / cost

Gemini 2.0 Flash is free-tier eligible at low volume (5–20 users).
If the project scales, add per-user rate limiting (max 10 NLP calls/min/user).

---

## 6. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (required if NLP enabled) | Gemini API key |
| `NLP_ENABLED` | `false` | Feature flag — off until tested |
| `NLP_TIMEOUT_SECS` | `2.0` | Hard timeout; graceful fallback on expiry |

---

## 7. New / changed files

| File | Change |
|---|---|
| `intent_router.py` | New — `parse_intent(text, session) -> Intent` (~80 lines) |
| `bot.py` | Add plain-text message handler; call `parse_intent()`; inject `destination_type` + `trip_date` into scout flow |
| `report_assembler.py` | Accept `destination_type` + `trip_date`; section selection matrix (§4.1) |
| `fetchers/eta.py` | Add `no_traffic=True` mode for future-date trips |
| `fetchers/weather.py` | Accept optional `target_date` to select forecast window |
| `fetchers/avalanche.py` | Accept optional `target_date` to select danger rating for that day |

### Intent dataclass

```python
@dataclass
class Intent:
    skill: str                    # scout | set_start | help | clear | unknown
    destination: str | None = None
    start: str | None = None
    destination_type: str | None = None   # mountain | alpine | lake | trail | park | city | unknown
    trip_date: str | None = None          # "today" | "tomorrow" | "YYYY-MM-DD" | None
    focus: str | None = None              # driving | avalanche | weather | wildfire | wildlife | None (full)
    location: str | None = None
    reason: str | None = None
```

---

## 7b. Focused queries (focus field)

When `focus` is set, the bot runs only the relevant fetchers and renders a focused response.
If `focus` is null (or the user typed a general query), the full scout report is returned as usual.

| focus | Fetchers run | Assembler | Confirmation shows "From"? |
|---|---|---|---|
| null | all | `assemble_report` | yes |
| `driving` | DriveBC + ETA | `assemble_driving_report` | yes |
| `avalanche` | avalanche + weather (alpine context) | `assemble_avalanche_report(weather=...)` | no |
| `weather` | weather 3-day | `assemble_3day_report` | no |
| `wildfire` | wildfire | `assemble_wildfire_report` | no |
| `wildlife` | wildlife news | `assemble_wildlife_report` | no |

"Change start" button is hidden on the confirmation card for non-driving focuses.
Post-report keyboard shows only "Scout new" for focused reports (no 3-day/avalanche drill-downs).

---

## 8. Testing

- Unit tests with mocked Gemini responses covering all skills + malformed JSON + timeout
- Smoke tests:
  - "I want to go to Whistler from Vancouver" → scout, city, today
  - "going to Elfin Lakes tomorrow" → scout, mountain/alpine, tomorrow → alpine forecast for tomorrow, no current traffic
  - "conditions at Alice Lake this Saturday" → scout, lake/park, specific date
  - "leaving from Squamish" → set_start
  - "what can you do" → help
  - "what's the weather in Toronto" → unknown
  - Gemini timeout → graceful fallback, no error shown

---

## 9. What this is not

- Not a general "ask the AI anything" mode — `unknown` explicitly rejects off-topic messages
- Not a replacement for slash commands — both paths coexist
- Not involved in fetching or formatting data — Gemini never sees road events, fires, or weather data

---

## 10. Open questions

| Question | Notes |
|---|---|
| Gemini vs. Claude Haiku for intent parsing? | Gemini is free-tier and stated preference. Haiku is viable alternative if Gemini key is friction. |
| Should NLP handle multi-intent messages? | Out of scope for v1 — one skill per message. |
| Logging parsed intents? | Log skill + destination_type + trip_date only (no raw user text). Consistent with privacy policy. |
| destination_type refinement from geocoder? | Geocoder result (elevation, place type) could override Gemini's inferred type. E.g. if Gemini says "city" but elevation > 1200m → switch to alpine. Low priority for v1. |
