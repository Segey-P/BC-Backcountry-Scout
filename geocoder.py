import logging
import math
import os
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx

logger = logging.getLogger(__name__)

SQUAMISH_DEFAULT = (49.7016, -123.1558)

_BC_LAT_MIN, _BC_LAT_MAX = 48.3, 60.0
_BC_LON_MIN, _BC_LON_MAX = -139.1, -114.0

_GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_GNWS_SEARCH_URL = "https://apps.gov.bc.ca/pub/bcgnws/names/search"


@dataclass
class GeoResult:
    name: str
    lat: float
    lon: float
    source: str  # "google" | "gnws"


def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _deduplicate(results: list[GeoResult], threshold_km: float = 0.5) -> list[GeoResult]:
    unique: list[GeoResult] = []
    for r in results:
        if not any(_haversine_km((r.lat, r.lon), (u.lat, u.lon)) < threshold_km for u in unique):
            unique.append(r)
    return unique


def _gnws_lookup(query: str) -> list[GeoResult]:
    """Query the BC Geographic Names Web Service (GNWS)."""
    params = {
        "name": query,
        "outputFormat": "geojson",
        "outputSRS": "4326",
        "itemsPerPage": 10,
    }
    try:
        response = httpx.get(_GNWS_SEARCH_URL, params=params, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("geocoder: GNWS request failed: %s", e)
        return []

    results = []
    for item in data.get("features", []):
        props = item.get("properties", {})
        geom = item.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        name = props.get("name", query.title())
        results.append(GeoResult(name, lat, lon, "gnws"))

    return results


def _google_maps_lookup(query: str, bias_point: tuple[float, float]) -> list[GeoResult]:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.warning("geocoder: GOOGLE_MAPS_API_KEY not set, skipping Google lookup")
        return []

    params = {
        "address": f"{query} British Columbia Canada",
        "key": api_key,
        "components": "country:CA",
        "language": "en",
        "bounds": f"{_BC_LAT_MIN},{_BC_LON_MIN}|{_BC_LAT_MAX},{_BC_LON_MAX}",
    }
    try:
        response = httpx.get(_GOOGLE_GEOCODE_URL, params=params, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("geocoder: Google Maps request failed: %s", e)
        return []

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        logger.warning("geocoder: Google Maps returned status=%s for query=%r", status, query)
        return []
    logger.debug("geocoder: Google Maps status=%s results=%d for query=%r",
                 status, len(data.get("results", [])), query)

    results = []
    for item in data.get("results", []):
        loc = item.get("geometry", {}).get("location", {})
        try:
            lat = float(loc["lat"])
            lon = float(loc["lng"])
        except (KeyError, ValueError):
            continue
        if not (_BC_LAT_MIN <= lat <= _BC_LAT_MAX and _BC_LON_MIN <= lon <= _BC_LON_MAX):
            continue
        # Use the first component of formatted_address as the display name
        full = item.get("formatted_address", "")
        name = full.split(",")[0].strip() if full else query.title()
        results.append(GeoResult(name, lat, lon, "google"))

    return results[:5]


def _in_bc(r: GeoResult) -> bool:
    return _BC_LAT_MIN <= r.lat <= _BC_LAT_MAX and _BC_LON_MIN <= r.lon <= _BC_LON_MAX


def _relevance_score(query: str, result: GeoResult) -> int:
    """Score result by query match quality. Higher is better."""
    query_lower = query.lower()
    result_lower = result.name.lower()
    query_words = query_lower.split()
    result_words = result_lower.split()

    # Exact name match is best (e.g., query "Whistler" = result "Whistler")
    if result_lower == query_lower:
        return 1000

    # Prefix match is very good (e.g., query "Whistler" matches result "Whistler Valley")
    if result_lower.startswith(query_lower + " ") or result_lower.startswith(query_lower):
        return 900

    # All query words appear in result name (e.g., "city of richmond" matches "City of Richmond")
    matching_words = sum(1 for qw in query_words if qw in result_words)
    if matching_words == len(query_words) and matching_words > 0:
        # Prefer results where query words appear in same order
        if all(result_lower.find(qw) >= 0 for qw in query_words):
            return 800 + matching_words * 10

    # Partial match: some query words in result (e.g., "richmond" matches "Richmond Island")
    if matching_words > 0:
        return 100 + matching_words * 10

    # No meaningful match
    return 0


def geocode_destination(
    query: str,
    bias_point: tuple[float, float] = SQUAMISH_DEFAULT,
) -> list[GeoResult]:
    google_results = [r for r in _google_maps_lookup(query, bias_point) if _in_bc(r)]
    gnws_results = [r for r in _gnws_lookup(query) if _in_bc(r)]

    # Merge and deduplicate
    combined = _deduplicate(google_results + gnws_results)

    # Rank by query relevance, with distance as tiebreaker for equal scores
    combined.sort(
        key=lambda r: (
            -_relevance_score(query, r),  # Sort by relevance score (descending)
            _haversine_km((r.lat, r.lon), bias_point),  # Tiebreaker: distance (ascending)
        )
    )

    return combined[:3]
