from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Local camera data populated by scripts/fetch_webcams.py via GitHub Actions.
# Oracle Cloud IPs are blocked by all *.gov.bc.ca and *.drivebc.ca endpoints,
# so we cannot fetch live from the bot server.
_DATA_FILE = Path(__file__).parent.parent / "data" / "webcams.json"

_CACHE_TTL = 3600  # reload from disk at most once per hour
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


def _load_cameras() -> list[dict]:
    """Load camera list from local data file, cached in memory for 1 hour."""
    now = time.monotonic()
    cached = _cache.get("cameras")
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    if not _DATA_FILE.exists():
        logger.warning("drivebc_webcam: %s not found — run scripts/fetch_webcams.py", _DATA_FILE)
        return []

    try:
        cameras = json.loads(_DATA_FILE.read_text())
        if not isinstance(cameras, list):
            raise ValueError("expected a JSON array")
        _cache["cameras"] = {"data": cameras, "ts": now}
        logger.info("drivebc_webcam: loaded %d cameras from %s", len(cameras), _DATA_FILE)
        return cameras
    except Exception as exc:
        logger.warning("drivebc_webcam: failed to read %s: %s", _DATA_FILE, exc)
        return []


def fetch_nearest_webcam(
    destination: tuple[float, float],
    max_distance_km: float = 30.0,
) -> Webcam | None:
    """Return the nearest DriveBC webcam to the destination within max_distance_km."""
    dest_lat, dest_lon = destination
    cameras = _load_cameras()
    if not cameras:
        return None

    best: Webcam | None = None
    for cam in cameras:
        try:
            lat = float(cam["lat"])
            lon = float(cam["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        dist = _haversine_km(lat, lon, dest_lat, dest_lon)
        if dist > max_distance_km:
            continue
        if best is None or dist < best.distance_km:
            best = Webcam(
                name=cam.get("name", "BC Highway Webcam"),
                lat=lat,
                lon=lon,
                image_url=cam.get("image_url", ""),
                page_url=cam.get("page_url", ""),
                distance_km=dist,
            )

    return best


def clear_cache() -> None:
    _cache.clear()
