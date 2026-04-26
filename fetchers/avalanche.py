import logging
import math
from dataclasses import dataclass, field

import httpx

_TIMEOUT = 8.0
_AREAS_URL = "https://api.avalanche.ca/forecasts/en/areas"
_FORECAST_URL = "https://api.avalanche.ca/forecasts/en/forecasts/{}"

logger = logging.getLogger(__name__)

_DANGER_ICON = {1: "✅", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⛔"}
_DANGER_LABEL = {1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme"}


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


def _bbox_center(bbox: list) -> tuple[float, float]:
    """GeoJSON bbox is [minLon, minLat, maxLon, maxLat] → (lat, lon)."""
    return (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2


def _extract_int(raw) -> int:
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, dict):
        for key in ("value", "rating", "dangerRating"):
            val = raw.get(key)
            if val is not None:
                return _extract_int(val)
    return 0


def _parse_danger(raw) -> DangerLevel:
    val = max(0, min(5, _extract_int(raw)))
    return DangerLevel(value=val, label=_DANGER_LABEL.get(val, "No Rating"), icon=_DANGER_ICON.get(val, "⬜"))


def _parse_forecast(hash_id: str, region_name: str, data: dict) -> "AvalancheReport | None":
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

    if not days:
        logger.warning("No dangerRatings in forecast. Keys: %s", list(data.keys()))
        return None

    highlights = data.get("highlights") or ""
    if isinstance(highlights, list):
        highlights = " ".join(str(h) for h in highlights)

    return AvalancheReport(
        region_id=hash_id,
        region_name=region_name,
        days=days,
        highlights=str(highlights)[:400].strip(),
    )


def fetch_avalanche(lat: float, lon: float) -> "AvalancheReport | None":
    headers = {"User-Agent": "BCBackcountryScout/1.0", "Accept": "application/json"}

    # Step 1: fetch all regions as GeoJSON
    try:
        areas_resp = httpx.get(_AREAS_URL, timeout=_TIMEOUT, headers=headers)
        if areas_resp.status_code != 200:
            logger.warning("Areas endpoint returned %d", areas_resp.status_code)
            return None
        features = areas_resp.json().get("features") or []
    except Exception as exc:
        logger.error("Areas fetch error: %s", exc)
        return None

    if not features:
        logger.warning("No features in areas response")
        return None

    # Step 2: find nearest region by bbox centroid
    def _dist(f):
        bbox = f.get("bbox")
        if not bbox or len(bbox) < 4:
            return float("inf")
        clat, clon = _bbox_center(bbox)
        return _haversine_km(lat, lon, clat, clon)

    nearest = min(features, key=_dist)
    hash_id = nearest["id"]
    props = nearest.get("properties") or {}
    region_name = (
        props.get("name") or props.get("regionName") or props.get("slug") or hash_id[:12]
    )
    logger.info("Nearest region: %s (id: %s...)", region_name, hash_id[:16])

    # Step 3: fetch forecast using hash ID
    url = _FORECAST_URL.format(hash_id)
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, headers=headers)
        logger.info("Forecast %s → %d — %s", url[:80], resp.status_code, resp.text[:300])
        if resp.status_code != 200:
            return None
        return _parse_forecast(hash_id, region_name, resp.json())
    except Exception as exc:
        logger.error("Forecast fetch error: %s", exc)
        return None
