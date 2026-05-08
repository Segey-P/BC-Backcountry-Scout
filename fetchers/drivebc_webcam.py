from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# DataBC GeoJSON endpoint for all BC Highway webcams
_WEBCAM_URL = (
    "https://openmaps.gov.bc.ca/geo/pub/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeName=pub:WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP"
    "&outputFormat=json&srsName=EPSG:4326"
)
# Fallback: DriveBC open data CSV/JSON (known public endpoint)
_WEBCAM_FALLBACK_URL = "https://api.open511.gov.bc.ca/webcams"

_TIMEOUT = 10.0
_CACHE_TTL = 86400  # 24 hours (camera locations don't change often)

_cache: dict = {}


@dataclass
class Webcam:
    name: str
    lat: float
    lon: float
    image_url: str
    page_url: str
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


def _parse_webcam_wfs(features: list, dest_lat: float, dest_lon: float) -> list[Webcam]:
    """Parse DataBC WFS GeoJSON features into Webcam objects."""
    cameras = []
    for feature in features:
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])

        cam_id = props.get("CAM_ID") or props.get("CAM_NAME") or ""
        name = props.get("CAM_NAME") or props.get("HIGHWAY_DESCRIPTION") or "BC Highway Webcam"
        highway = props.get("HIGHWAY_DESCRIPTION") or ""
        if highway and highway not in name:
            name = f"{name} ({highway})"

        # DriveBC image URLs follow a known pattern
        image_url = props.get("IMAGE_URL") or (
            f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id}/latest/image.jpg"
            if cam_id else ""
        )
        page_url = props.get("CAM_URL") or f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id}.html"

        dist = _haversine_km(lat, lon, dest_lat, dest_lon)
        cameras.append(Webcam(
            name=name,
            lat=lat,
            lon=lon,
            image_url=image_url,
            page_url=page_url,
            distance_km=dist,
        ))
    return cameras


def _fetch_webcams_raw() -> list[dict]:
    """Fetch raw webcam features from DataBC WFS (cached 24h)."""
    now = time.monotonic()
    cached = _cache.get("webcams")
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        response = httpx.get(_WEBCAM_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features") or []
        if features:
            _cache["webcams"] = {"data": features, "ts": now}
            return features
    except Exception as exc:
        logger.warning("drivebc_webcam: WFS fetch failed: %s", exc)

    # Fallback: Open511 webcams endpoint
    try:
        response = httpx.get(_WEBCAM_FALLBACK_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        # Open511 webcams have a different structure
        cameras = data.get("webcams") or []
        features = []
        for cam in cameras:
            location = cam.get("location") or {}
            coords = location.get("coordinates")
            if not coords:
                continue
            features.append({
                "geometry": {"type": "Point", "coordinates": coords},
                "properties": {
                    "CAM_NAME": cam.get("name", ""),
                    "IMAGE_URL": cam.get("url", ""),
                    "CAM_URL": cam.get("url", ""),
                    "CAM_ID": cam.get("id", ""),
                }
            })
        if features:
            _cache["webcams"] = {"data": features, "ts": now}
        return features
    except Exception as exc:
        logger.warning("drivebc_webcam: fallback fetch failed: %s", exc)
        return []


def fetch_nearest_webcam(
    destination: tuple[float, float],
    max_distance_km: float = 30.0,
) -> Webcam | None:
    """Return the nearest DriveBC webcam to the destination within max_distance_km."""
    dest_lat, dest_lon = destination
    features = _fetch_webcams_raw()
    if not features:
        return None

    cameras = _parse_webcam_wfs(features, dest_lat, dest_lon)
    if not cameras:
        return None

    cameras.sort(key=lambda c: c.distance_km)
    nearest = cameras[0]

    if nearest.distance_km > max_distance_km:
        return None

    return nearest


def clear_cache() -> None:
    _cache.clear()
