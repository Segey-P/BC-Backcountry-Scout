from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_BCPARKS_BASE = "https://bcparks.api.gov.bc.ca/api"
_ADVISORIES_URL = f"{_BCPARKS_BASE}/public-advisories"
_PARKS_URL = f"{_BCPARKS_BASE}/parks"
_TIMEOUT = 8.0
_CACHE_TTL = 900  # 15 minutes

_cache: dict = {}

_URGENCY_LABELS = {
    1: "Info",
    2: "Advisory",
    3: "Warning",
    4: "Danger",
}


@dataclass
class ParkAdvisory:
    park_name: str
    title: str
    urgency_level: int
    urgency_label: str
    description: str
    url: str
    distance_km: float


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _fetch_advisories_raw() -> list[dict]:
    """Fetch all public advisories from BC Parks API. Cached 15 min."""
    now = time.monotonic()
    cached = _cache.get("advisories")
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        params = {
            "isActive": "true",
            "pageSize": 200,
        }
        response = httpx.get(_ADVISORIES_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        advisories = data if isinstance(data, list) else data.get("data") or data.get("items") or []
        _cache["advisories"] = {"data": advisories, "ts": now}
        return advisories
    except Exception as exc:
        logger.warning("bcparks: advisories fetch failed: %s", exc)
        return []


def _advisory_distance(advisory: dict, dest_lat: float, dest_lon: float) -> float:
    """Calculate distance from advisory park location to destination."""
    # Advisories are linked to parks; try to get park coordinates
    protectedArea = advisory.get("protectedArea") or {}
    lat = protectedArea.get("latitude") or protectedArea.get("lat")
    lon = protectedArea.get("longitude") or protectedArea.get("lon") or protectedArea.get("lng")

    if lat is None or lon is None:
        # Also try nested sites or regions
        sites = advisory.get("sites") or []
        if sites:
            lat = sites[0].get("latitude")
            lon = sites[0].get("longitude")

    if lat is None or lon is None:
        return float("inf")

    try:
        return _haversine_km(float(lat), float(lon), dest_lat, dest_lon)
    except (TypeError, ValueError):
        return float("inf")


def _build_advisory_url(advisory: dict) -> str:
    """Build BC Parks advisory URL."""
    park = advisory.get("protectedArea") or {}
    slug = park.get("slug") or ""
    if slug:
        return f"https://bcparks.ca/explore/parkpgs/{slug}/#advisories"
    return "https://bcparks.ca/advisories"


def fetch_park_advisories(
    destination: tuple[float, float],
    radius_km: float = 20.0,
) -> list[ParkAdvisory]:
    """Return active BC Parks advisories within radius_km of destination."""
    dest_lat, dest_lon = destination
    raw = _fetch_advisories_raw()
    if not raw:
        return []

    results = []
    for item in raw:
        urgency = item.get("urgency") or {}
        urgency_level = urgency.get("urgencyLevel") or urgency.get("id") or 2

        dist = _advisory_distance(item, dest_lat, dest_lon)
        if dist > radius_km:
            continue

        park = item.get("protectedArea") or {}
        park_name = park.get("protectedAreaName") or park.get("name") or "BC Park"
        title = item.get("title") or item.get("advisoryDate") or "Advisory"
        description = item.get("description") or ""
        # Trim long descriptions
        if len(description) > 120:
            description = description[:117] + "…"

        results.append(ParkAdvisory(
            park_name=park_name,
            title=title,
            urgency_level=urgency_level,
            urgency_label=_URGENCY_LABELS.get(urgency_level, "Advisory"),
            description=description,
            url=_build_advisory_url(item),
            distance_km=dist,
        ))

    results.sort(key=lambda a: (a.distance_km, -a.urgency_level))
    return results[:5]  # Cap at 5 to keep report concise


def clear_cache() -> None:
    _cache.clear()
