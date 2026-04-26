import math
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx

SQUAMISH_DEFAULT = (49.7016, -123.1558)
_SIMILARITY_THRESHOLD = 0.85
_FUZZY_TOKEN_THRESHOLD = 0.50
_FUZZY_TOKEN_WORD_MIN = 0.80

# Bounding box for British Columbia
_BC_LAT_MIN, _BC_LAT_MAX = 48.3, 60.0
_BC_LON_MIN, _BC_LON_MAX = -139.1, -114.0

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "BCBackcountryScout/1.0 (github.com/Segey-P/bc-backcountry-scout)"}


@dataclass
class GeoResult:
    name: str
    lat: float
    lon: float
    source: str  # "gnws" | "nominatim" | "fuzzy"


_KNOWN_FEATURES: list[GeoResult] = [
    GeoResult("Alice Lake Provincial Park", 49.7696, -123.1163, "fuzzy"),
    GeoResult("Mamquam Forest Service Road", 49.7500, -123.0800, "fuzzy"),
    GeoResult("Garibaldi Provincial Park", 49.9500, -123.0000, "fuzzy"),
    GeoResult("Squamish, BC", 49.7016, -123.1558, "fuzzy"),
    GeoResult("Brandywine Falls Provincial Park", 50.0530, -123.1280, "fuzzy"),
    GeoResult("Whistler, BC", 50.1163, -122.9574, "fuzzy"),
    GeoResult("Cheakamus Lake", 49.9900, -123.0500, "fuzzy"),
    GeoResult("Elfin Lakes", 49.9400, -123.0700, "fuzzy"),
    GeoResult("Black Tusk", 49.9700, -123.0400, "fuzzy"),
    GeoResult("Ring Creek Rip", 49.7900, -123.0500, "fuzzy"),
    GeoResult("Tantalus Lookout", 49.9000, -123.2000, "fuzzy"),
    GeoResult("Levette Lake", 49.8800, -123.1700, "fuzzy"),
    GeoResult("Stawamus Chief Provincial Park", 49.6750, -123.1469, "fuzzy"),
    GeoResult("Furry Creek", 49.5700, -123.2200, "fuzzy"),
    GeoResult("Porteau Cove Provincial Park", 49.5500, -123.2300, "fuzzy"),
    GeoResult("Birkenhead Lake Provincial Park", 50.5000, -122.7000, "fuzzy"),
    GeoResult("Pemberton, BC", 50.3177, -122.8005, "fuzzy"),
    GeoResult("Brackendale, BC", 49.7800, -123.1600, "fuzzy"),
    GeoResult("Diamond Head", 49.9500, -123.0600, "fuzzy"),
    GeoResult("Tricouni Peak", 49.9200, -123.2500, "fuzzy"),
    GeoResult("Vancouver, BC", 49.2827, -123.1207, "fuzzy"),
    GeoResult("Victoria, BC", 48.4284, -123.3656, "fuzzy"),
    GeoResult("Kelowna, BC", 49.8880, -119.4960, "fuzzy"),
    GeoResult("Kamloops, BC", 50.6745, -120.3273, "fuzzy"),
    GeoResult("Prince George, BC", 53.9171, -122.7497, "fuzzy"),
    GeoResult("Revelstoke, BC", 50.9981, -118.1957, "fuzzy"),
    GeoResult("Golden, BC", 51.2988, -116.9631, "fuzzy"),
    GeoResult("Tofino, BC", 49.1530, -125.9066, "fuzzy"),
    GeoResult("Sun Peaks, BC", 50.8873, -119.8883, "fuzzy"),
    GeoResult("Manning Provincial Park", 49.0833, -120.7500, "fuzzy"),
    GeoResult("Joffre Lakes Provincial Park", 50.3667, -122.4833, "fuzzy"),
    GeoResult("Stein Valley Nlaka'pamux Heritage Park", 50.1333, -121.9167, "fuzzy"),
    GeoResult("Skagit Valley Provincial Park", 49.0500, -121.1500, "fuzzy"),
    GeoResult("Coquihalla Summit", 49.7167, -121.0833, "fuzzy"),
    GeoResult("Hope, BC", 49.3838, -121.4422, "fuzzy"),
]


def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _similarity(query: str, name: str) -> float:
    """Character-level similarity — used to validate API results against the query."""
    q, n = query.lower().strip(), name.lower().strip()
    if q in n or n in q:
        return 1.0
    return SequenceMatcher(None, q, n).ratio()


def _token_match_score(query: str, name: str) -> float:
    """Bidirectional token match: max of (query→name fraction) and (name→query fraction).

    Using both directions means a query like 'iceberg lake whistler' can match
    'Whistler, BC' because 1 of 2 name words matches a query word (score=0.50).
    """
    q_words = query.lower().split()
    n_words = name.lower().split()
    if not q_words or not n_words:
        return 0.0

    q_matched = sum(
        1 for qw in q_words
        if any(SequenceMatcher(None, qw, nw).ratio() >= _FUZZY_TOKEN_WORD_MIN for nw in n_words)
    )
    n_matched = sum(
        1 for nw in n_words
        if any(SequenceMatcher(None, nw, qw).ratio() >= _FUZZY_TOKEN_WORD_MIN for qw in q_words)
    )
    return max(q_matched / len(q_words), n_matched / len(n_words))


def _deduplicate(results: list[GeoResult], threshold_km: float = 0.5) -> list[GeoResult]:
    unique: list[GeoResult] = []
    for r in results:
        if not any(_haversine_km((r.lat, r.lon), (u.lat, u.lon)) < threshold_km for u in unique):
            unique.append(r)
    return unique


def _gnws_lookup(query: str) -> list[GeoResult]:
    """Stub — replace with real BC GNWS HTTP call in a later module."""
    q = query.lower()
    if "alice lake" in q:
        return [GeoResult("Alice Lake Provincial Park", 49.7696, -123.1163, "gnws")]
    if "mamquam" in q:
        return [
            GeoResult("Mamquam River", 49.7900, -123.0600, "gnws"),
            GeoResult("Mamquam Forest Service Road", 49.7500, -123.0800, "gnws"),
        ]
    return []


def _nominatim_lookup(query: str) -> list[GeoResult]:
    """Live Nominatim/OSM lookup scoped to British Columbia."""
    params = {
        "q": f"{query} British Columbia Canada",
        "format": "json",
        "limit": 5,
        "addressdetails": 0,
    }
    try:
        response = httpx.get(
            _NOMINATIM_URL,
            params=params,
            headers=_NOMINATIM_HEADERS,
            timeout=5.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    results = []
    for item in data:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, ValueError):
            continue
        if not (_BC_LAT_MIN <= lat <= _BC_LAT_MAX and _BC_LON_MIN <= lon <= _BC_LON_MAX):
            continue
        display = item.get("display_name", "")
        name = display.split(",")[0].strip() if display else query.title()
        results.append(GeoResult(name, lat, lon, "nominatim"))
    return results


def geocode_destination(
    query: str,
    bias_point: tuple[float, float] = SQUAMISH_DEFAULT,
) -> list[GeoResult]:
    results = _gnws_lookup(query)
    if len(results) < 3:
        results += _nominatim_lookup(query)

    results = _deduplicate(results)
    results.sort(key=lambda r: _haversine_km((r.lat, r.lon), bias_point))

    if results and _similarity(query, results[0].name) >= _SIMILARITY_THRESHOLD:
        return results[:3]

    # Fuzzy fallback: rank known BC features by bidirectional token match score
    scored = sorted(_KNOWN_FEATURES, key=lambda r: -_token_match_score(query, r.name))
    return [r for r in scored[:3] if _token_match_score(query, r.name) >= _FUZZY_TOKEN_THRESHOLD]
