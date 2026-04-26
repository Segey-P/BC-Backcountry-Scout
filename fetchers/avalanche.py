import logging
import math
from dataclasses import dataclass, field

import httpx

_TIMEOUT = 10.0
_AREAS_URL = "https://api.avalanche.ca/forecasts/en/areas"
_PRODUCTS_URL = "https://api.avalanche.ca/forecasts/en/products"

logger = logging.getLogger(__name__)

_DANGER_ICON = {1: "✅", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⛔"}
_DANGER_LABEL = {1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme"}
_DANGER_VALUE = {
    "low": 1, "moderate": 2, "considerable": 3, "high": 4, "extreme": 5,
}


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
    """GeoJSON bbox [minLon, minLat, maxLon, maxLat] → (lat, lon)."""
    return (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2


def _parse_danger_str(raw) -> DangerLevel:
    """Parse danger value from string ('considerable') or dict."""
    val_str = ""
    if isinstance(raw, str):
        val_str = raw.lower()
    elif isinstance(raw, dict):
        rating = raw.get("rating") or raw
        if isinstance(rating, dict):
            val_str = (rating.get("value") or "").lower()
        else:
            val_str = str(rating).lower()
    val = _DANGER_VALUE.get(val_str, 0)
    return DangerLevel(value=val, label=_DANGER_LABEL.get(val, "No Rating"), icon=_DANGER_ICON.get(val, "⬜"))


def _parse_product(product: dict, area_hash: str) -> "AvalancheReport | None":
    report = product.get("report") or {}
    raw_ratings = report.get("dangerRatings") or []
    region_name = report.get("title") or area_hash[:12]

    # Strip HTML from highlights
    highlights_raw = report.get("highlights") or ""
    import re
    highlights = re.sub(r"<[^>]+>", " ", highlights_raw).strip()
    highlights = re.sub(r"\s+", " ", highlights)[:300]

    days: list[DayDanger] = []
    for day_raw in raw_ratings[:3]:
        date_raw = day_raw.get("date") or {}
        date_str = date_raw.get("display") or date_raw.get("value") or ""

        ratings = day_raw.get("ratings") or day_raw.get("dangerRating") or {}
        alp = ratings.get("alp") or ratings.get("alpine") or {}
        tln = ratings.get("tln") or ratings.get("treeline") or {}
        btl = ratings.get("btl") or ratings.get("belowTreeline") or {}

        days.append(DayDanger(
            date=date_str,
            alpine=_parse_danger_str(alp),
            treeline=_parse_danger_str(tln),
            below_treeline=_parse_danger_str(btl),
        ))

    if not days:
        logger.warning("No dangerRatings in report. Report keys: %s", list(report.keys()))
        return None

    return AvalancheReport(
        region_id=area_hash,
        region_name=region_name,
        days=days,
        highlights=highlights,
    )


def fetch_avalanche(lat: float, lon: float) -> "AvalancheReport | None":
    headers = {"User-Agent": "BCBackcountryScout/1.0", "Accept": "application/json"}

    # Step 1: fetch all region boundaries and find nearest by bbox centroid
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
        return None

    def _dist(f):
        bbox = f.get("bbox")
        if not bbox or len(bbox) < 4:
            return float("inf")
        clat, clon = _bbox_center(bbox)
        return _haversine_km(lat, lon, clat, clon)

    nearest = min(features, key=_dist)
    area_hash = nearest["id"]
    logger.info("Nearest area hash: %s (centroid: %s)", area_hash[:12], nearest.get("properties", {}).get("centroid"))

    # Step 2: fetch ALL products and find the one matching our area hash
    try:
        prod_resp = httpx.get(_PRODUCTS_URL, timeout=_TIMEOUT, headers=headers)
        logger.info("Products endpoint: %d", prod_resp.status_code)
        if prod_resp.status_code != 200:
            return None
        products = prod_resp.json()
    except Exception as exc:
        logger.error("Products fetch error: %s", exc)
        return None

    if not isinstance(products, list) or not products:
        return None

    # Find product where area.id matches our nearest region hash
    match = next(
        (p for p in products if (p.get("area") or {}).get("id") == area_hash),
        None,
    )
    if not match:
        logger.warning(
            "No product matched area hash %s. Available area IDs: %s",
            area_hash[:12],
            [p.get("area", {}).get("id", "?")[:12] for p in products[:5]],
        )
        return None

    logger.info("Matched product: %s", match.get("report", {}).get("title"))
    return _parse_product(match, area_hash)
