# BC Backcountry Scout — NLP Intent Router (Gemini)

**Version:** 0.1 (proposal)
**Date:** April 2026
**Status:** Planned — Phase 2

---

## 1. Problem

The bot currently only responds to slash commands (`/scout`, `/from`, `/help`, etc.).
Users have to know the exact syntax. Natural sentences like:

> "I want to go to Whistler from Vancouver"
> "what's the road like to Alice Lake today"
> "any bears near Garibaldi"

…are ignored or hit the unknown-command handler.

---

## 2. Solution

A thin **intent router** layer inserted between Telegram message receipt and the existing command handlers. It uses Gemini to parse free-text messages into a structured intent, then dispatches to the same handler that an explicit slash command would have triggered.

The deterministic data pipeline (geocoder → fetchers → report assembler) is **not changed**. Gemini only touches the user's input string, not any safety-relevant data.

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
                ↓
           [Same pipeline as before]
```

Only plain-text messages (no leading `/`) go through the router. Slash commands bypass it entirely — no regression risk.

### 3.2 Intent JSON schema

Gemini is prompted to return one of:

```json
{"skill": "scout", "destination": "Whistler, BC", "start": "Vancouver, BC"}
{"skill": "set_start", "location": "Squamish, BC"}
{"skill": "help"}
{"skill": "clear"}
{"skill": "unknown", "reason": "query is not about backcountry trip planning"}
```

All fields beyond `skill` are optional and nullable. The router fills missing fields from the session (same priority order as the existing starting-point resolution logic).

### 3.3 Skills map

| Skill | Maps to | Triggered by |
|---|---|---|
| `scout` | `/scout <destination>` handler | "I want to go to X", "conditions at X", "what's it like at X" |
| `set_start` | `/from <location>` handler | "I'm leaving from X", "starting from X", "I'm in X" |
| `help` | `/help` handler | "what can you do", "how do I use this" |
| `clear` | `/clear` handler | "forget my session", "reset" |
| `unknown` | Polite reply listing skills | Anything off-topic |

### 3.4 Fallback chain

1. Gemini returns valid intent → dispatch
2. Gemini returns `unknown` → reply: "I can help with BC backcountry conditions. Try: 'conditions at Alice Lake' or use /scout."
3. Gemini API error / timeout (2s hard limit) → fall through to unknown-command handler, do not block the user
4. Gemini returns malformed JSON → treat as error, same as #3

---

## 4. Gemini API integration

### 4.1 Model

`gemini-2.0-flash` — fastest and cheapest; intent extraction is a simple structured-output task, not reasoning-heavy.

### 4.2 Prompt (system)

```
You are an intent classifier for a Telegram bot that provides BC backcountry trip conditions.
Extract the user's intent from their message and return ONLY valid JSON matching this schema:

{"skill": <"scout"|"set_start"|"help"|"clear"|"unknown">, ...skill-specific fields}

Skills:
- scout: user wants conditions for a destination. Fields: destination (string), start (string or null)
- set_start: user is setting their starting location. Fields: location (string)
- help: user wants to know what the bot can do. No extra fields.
- clear: user wants to reset their session. No extra fields.
- unknown: message is not about backcountry trip planning. Fields: reason (string)

Rules:
- Always return JSON. Never explain or add prose.
- destination and location should include province/region if inferable (e.g. "Whistler, BC").
- If destination is unclear, return unknown.
- Do not invent destinations not mentioned by the user.
```

### 4.3 Auth

`GEMINI_API_KEY` environment variable. Bot startup fails fast with a clear error if not set and NLP is enabled.

### 4.4 Rate / cost

Gemini 2.0 Flash is free-tier eligible at low volume (this bot has 5–20 users). Cache nothing — each message is short and unique. If the project scales, add per-user rate limiting (max 10 NLP calls/min/user).

---

## 5. Configuration

Add to the bot's config/env:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (required if NLP enabled) | API key |
| `NLP_ENABLED` | `false` | Feature flag — off until tested |
| `NLP_TIMEOUT_SECS` | `2.0` | Hard timeout; fallback to unknown-command on expiry |

`NLP_ENABLED=false` means the feature is inert until explicitly turned on. Existing slash-command behaviour is unchanged regardless of this flag.

---

## 6. New file

`intent_router.py` — single module, ~80 lines:

```
parse_intent(text: str, session: dict) -> Intent
```

Returns a dataclass:

```python
@dataclass
class Intent:
    skill: str          # scout | set_start | help | clear | unknown
    destination: str | None = None
    start: str | None = None
    location: str | None = None
    reason: str | None = None
```

`bot.py` calls `parse_intent()` in the plain-text message handler and dispatches based on `intent.skill`.

---

## 7. Testing

- Unit tests with mocked Gemini responses covering all six skills + malformed JSON + timeout
- Manual smoke tests:
  - "I want to go to Whistler from Vancouver" → scout card for Whistler, start Squamish (from session) or Vancouver (from message)
  - "leaving from Squamish" → session updated, bot confirms new start
  - "what can you do" → help message
  - "what's the weather in Toronto" → unknown reply
  - Gemini timeout → graceful fallback, no error shown to user

---

## 8. What this is not

- Not a general "ask the AI anything" mode — `unknown` skill explicitly rejects off-topic messages
- Not a replacement for slash commands — both paths coexist
- Not involved in fetching or formatting data — Gemini never sees road events, fires, or weather data

---

## 9. Open questions

| Question | Notes |
|---|---|
| Gemini vs. Claude for intent parsing? | Gemini is free-tier and user's stated preference. Claude Haiku is a viable alternative at ~same cost if Gemini key is a friction point. |
| Should NLP handle multi-intent messages? | Out of scope for v1 — one skill per message. |
| Logging parsed intents? | Log skill + destination only (no raw user text) for debugging. Consistent with existing privacy policy. |
