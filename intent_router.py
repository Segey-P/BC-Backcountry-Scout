import json
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an intent classifier for a Telegram bot that provides BC backcountry trip conditions.
Extract the user's intent and return ONLY valid JSON — no prose, no markdown, no code fences.

Schema: {"skill": <"scout"|"set_start"|"help"|"clear"|"unknown">, ...skill-specific fields}

Skills:
- scout: user wants conditions for a destination.
  Fields: destination (string), start (string or null), destination_type (string), trip_date (string or null)
- set_start: user is setting their starting location. Fields: location (string)
- help: user wants to know what the bot can do. No extra fields.
- clear: user wants to reset their session. No extra fields.
- unknown: not about backcountry trip planning. Fields: reason (string)

destination_type values: mountain, alpine, lake, trail, park, city, unknown
trip_date: "today", "tomorrow", or ISO date YYYY-MM-DD. Null if not mentioned (assume today).

Rules:
- Always return JSON only.
- Include BC/region in destination/location if inferable (e.g. "Whistler, BC").
- If destination is unclear, return unknown.
- Do not invent destinations not mentioned by the user."""

@dataclass
class Intent:
    skill: str                        # scout | set_start | help | clear | unknown
    destination: str | None = None
    start: str | None = None
    destination_type: str | None = None   # mountain | alpine | lake | trail | park | city | unknown
    trip_date: str | None = None          # today | tomorrow | YYYY-MM-DD | None
    location: str | None = None
    reason: str | None = None


def parse_intent(text: str) -> Intent:
    """Call Gemini to extract a structured intent from free-form user text.

    Returns Intent(skill='unknown') on any failure so the caller always gets
    a valid object without handling exceptions.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("intent_router: GEMINI_API_KEY not set")
        return Intent(skill="unknown", reason="NLP not configured")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
            ),
        )
        raw = response.text.strip()
        # Strip markdown code fences Gemini sometimes adds despite instructions
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("intent_router: bad JSON from Gemini: %s", e)
        return Intent(skill="unknown", reason="parse error")
    except Exception as e:
        logger.warning("intent_router: Gemini call failed: %s", e)
        return Intent(skill="unknown", reason="service error")

    skill = data.get("skill", "unknown")
    if skill not in ("scout", "set_start", "help", "clear", "unknown"):
        skill = "unknown"

    return Intent(
        skill=skill,
        destination=data.get("destination"),
        start=data.get("start"),
        destination_type=data.get("destination_type"),
        trip_date=data.get("trip_date"),
        location=data.get("location"),
        reason=data.get("reason"),
    )


def nlp_enabled() -> bool:
    return os.environ.get("NLP_ENABLED", "false").lower() == "true"
