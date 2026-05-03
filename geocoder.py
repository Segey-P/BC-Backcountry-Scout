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


def geocode_destination(
    query: str,
    bias_point: tuple[float, float] = SQUAMISH_DEFAULT,
) -> list[GeoResult]:
    google_results = [r for r in _google_maps_lookup(query, bias_point) if _in_bc(r)]
    gnws_results = [r for r in _gnws_lookup(query) if _in_bc(r)]

    # Merge and deduplicate
    combined = _deduplicate(google_results + gnws_results)

    # Rank by haversine distance to bias point
    combined.sort(key=lambda r: _haversine_km((r.lat, r.lon), bias_point))

    return combined[:3]
