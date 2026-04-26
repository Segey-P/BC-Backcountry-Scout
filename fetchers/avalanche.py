import logging
import math
from dataclasses import dataclass, field

import httpx

_TIMEOUT = 8.0
_BASE_URL = "https://api.avalanche.ca/forecasts/en/forecasts"

logger = logging.getLogger(__name__)

_DANGER_ICON = {
    1: "✅", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⛔",
}
_DANGER_LABEL = {
    1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme",
}

# (region_id, display_name, center_lat, center_lon)
_REGIONS = [
    ("sea-to-sky",         "Sea to Sky",          50.15, -123.10),
    ("south-coast",        "South Coast",          49.35, -121.80),
    ("south-coast-inland", "South Coast Inland",   49.50, -120.80),
    ("north-columbia",     "North Columbia",       51.50, -118.50),
    ("south-columbia",     "South Columbia",       49.50, -117.80),
    ("kootenay-boundary",  "Kootenay Boundary",    49.10, -117.30),
    ("purcells",           "Purcells",             50.50, -116.50),
    ("cariboo",            "Cariboo",              52.70, -121.00),
    ("north-rockies",      "North Rockies",        56.50, -122.50),
    ("south-rockies",      "South Rockies",        50.50, -115.50),
    ("north-coast",        "North Coast",          54.50, -128.50),
]


@dataclass
class DangerLevel:
    value: int
    label: str
    icon: str


@dataclass
class DayDanger:
    date: str
    alpine: DangerLevel
    treeline: DangerLevel
    below_treeline: DangerLevel


@dataclass
class AvalancheReport:
    region_id: str
    region_name: str
    days: list[DayDanger] = field(default_factory=list)
    highlights: str = ""


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _nearest_region(lat: float, lon: float) -> tuple[str, str]:
    best = min(_REGIONS, key=lambda r: _haversine_km(lat, lon, r[2], r[3]))
    return best[0], best[1]


def _extract_int(raw) -> int:
    """Recursively extract integer danger value from various API response shapes."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, dict):
        for key in ("value", "rating", "dangerRating"):
            val = raw.get(key)
            if val is not None:
                return _extract_int(val)
    return 0


def _parse_danger(raw) -> DangerLevel:
    val = max(0, min(5, _extract_int(raw)))
    return DangerLevel(
        value=val,
        label=_DANGER_LABEL.get(val, "No Rating"),
        icon=_DANGER_ICON.get(val, "⬜"),
    )


_PROBE_URLS = [
    "https://api.avalanche.ca/forecasts/en/areas",
    "https://api.avalanche.ca/forecasts/en/forecasts",
    "https://api.avalanche.ca/forecasts",
]


def _probe_api() -> None:
    """Log responses from candidate endpoints to discover the correct API shape."""
    headers = {"User-Agent": "BCBackcountryScout/1.0", "Accept": "application/json"}
    for url in _PROBE_URLS:
        try:
            resp = httpx.get(url, timeout=_TIMEOUT, headers=headers)
            logger.info("PROBE %s → %d — %s", url, resp.status_code, resp.text[:500])
        except Exception as exc:
            logger.info("PROBE %s → error: %s", url, exc)


def fetch_avalanche(lat: float, lon: float) -> "AvalancheReport | None":
    region_id, region_name = _nearest_region(lat, lon)
    _probe_api()
    return None

    raw_ratings = data.get("dangerRatings") or []
    days: list[DayDanger] = []

    for day_raw in raw_ratings[:3]:
        dr = day_raw.get("dangerRating") or day_raw

        date_raw = day_raw.get("date") or {}
        if isinstance(date_raw, dict):
            date_str = date_raw.get("display") or date_raw.get("value") or ""
        else:
            date_str = str(date_raw)

        alp = dr.get("alp") or dr.get("alpine") or 0
        tln = dr.get("tln") or dr.get("treeline") or 0
        btl = dr.get("btl") or dr.get("belowTreeline") or dr.get("below_treeline") or 0

        days.append(DayDanger(
            date=date_str,
            alpine=_parse_danger(alp),
            treeline=_parse_danger(tln),
            below_treeline=_parse_danger(btl),
        ))

    highlights = data.get("highlights") or ""
    if isinstance(highlights, list):
        highlights = " ".join(str(h) for h in highlights)

    return AvalancheReport(
        region_id=region_id,
        region_name=region_name,
        days=days,
        highlights=str(highlights)[:400].strip(),
    )
