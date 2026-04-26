from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache

import httpx

_TIMEOUT = 5.0
_BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"
_CACHE_TTL = 300  # 5 minutes


@dataclass
class ETAResult:
    duration_text: str
    duration_traffic_text: str
    distance_text: str


_cache_state = {"last_result": None, "last_time": 0, "last_points": None}


def _fetch_eta_uncached(start_point: tuple, dest_point: tuple) -> "ETAResult | None":
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None

    try:
        resp = httpx.get(
            _BASE_URL,
            params={
                "origin": f"{start_point[0]},{start_point[1]}",
                "destination": f"{dest_point[0]},{dest_point[1]}",
                "departure_time": "now",
                "traffic_model": "best_guess",
                "key": api_key,
            },
            timeout=_TIMEOUT,
            headers={"User-Agent": "BCBackcountryScout/1.0"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != "OK":
            return None

        leg = data["routes"][0]["legs"][0]
        duration = leg["duration"]["text"]
        distance = leg["distance"]["text"]
        duration_traffic = leg.get("duration_in_traffic", {}).get("text", duration)

        return ETAResult(
            duration_text=duration,
            duration_traffic_text=duration_traffic,
            distance_text=distance,
        )
    except (httpx.TimeoutException, httpx.HTTPError, KeyError, IndexError):
        return None


def fetch_eta(start_point: tuple, dest_point: tuple) -> "ETAResult | None":
    now = time.monotonic()
    if (
        _cache_state["last_result"] is not None
        and _cache_state["last_points"] == (start_point, dest_point)
        and (now - _cache_state["last_time"]) < _CACHE_TTL
    ):
        return _cache_state["last_result"]

    result = _fetch_eta_uncached(start_point, dest_point)
    _cache_state["last_result"] = result
    _cache_state["last_points"] = (start_point, dest_point)
    _cache_state["last_time"] = now
    return result


def clear_cache() -> None:
    _cache_state["last_result"] = None
    _cache_state["last_points"] = None
    _cache_state["last_time"] = 0
