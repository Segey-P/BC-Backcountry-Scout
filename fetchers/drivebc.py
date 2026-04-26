import time
from dataclasses import dataclass

import httpx
from shapely.geometry import shape

_OPEN511_URL = "https://api.open511.gov.bc.ca/events"
_SEVERITY_KEEP = {"MAJOR", "MODERATE"}
_KEYWORDS = frozenset({"closed", "closure", "avalanche", "washout", "rockfall", "slide"})
_CRITICAL_ROUTES = frozenset({"sea-to-sky", "hwy 99", "highway 99"})
_CACHE_TTL = 300  # 5 minutes

_cache: dict = {}  # {"data": list, "ts": float}


@dataclass
class RoadEvent:
    headline: str
    description: str
    severity: str
    geometry: dict  # GeoJSON geometry
    last_updated: str


def _is_relevant(event: dict) -> bool:
    severity = event.get("severity", "").upper()
    headline = event.get("headline", "").lower()
    description = event.get("description", "").lower()
    full_text = f"{headline} {description}".lower()

    if severity in _SEVERITY_KEEP:
        return True
    if any(kw in full_text for kw in _KEYWORDS):
        return True
    if any(route in full_text for route in _CRITICAL_ROUTES):
        return True
    return False


def _intersects_corridor(event: dict, corridor) -> bool:
    geo = event.get("geography")
    if not geo:
        return False
    try:
        return corridor.intersects(shape(geo))
    except Exception:
        return False


def _to_road_event(event: dict) -> RoadEvent:
    return RoadEvent(
        headline=event.get("headline", ""),
        description=event.get("description", ""),
        severity=event.get("severity", "UNKNOWN"),
        geometry=event.get("geography", {}),
        last_updated=event.get("updated", ""),
    )


def fetch_drivebc_events(corridor_polygon) -> list[RoadEvent]:
    now = time.monotonic()
    if _cache and (now - _cache.get("ts", 0)) < _CACHE_TTL:
        raw_events = _cache["data"]
    else:
        response = httpx.get(_OPEN511_URL, timeout=8.0)
        response.raise_for_status()
        raw_events = response.json().get("events", [])
        _cache["data"] = raw_events
        _cache["ts"] = now

    return [
        _to_road_event(ev)
        for ev in raw_events
        if _is_relevant(ev) and _intersects_corridor(ev, corridor_polygon)
    ]


def clear_cache() -> None:
    _cache.clear()
