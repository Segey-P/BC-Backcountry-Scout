from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_AIR_QUALITY_URL = "https://api.open-meteo.com/v1/air-quality"
_TIMEOUT = 8.0
_CACHE_TTL = 300  # 5 minutes


@dataclass
class AirQualityReport:
    """Air quality data and AQHI calculation."""
    aqhi: float | None
    pm25: float | None
    no2: float | None
    o3: float | None
    level: str
    emoji: str
    color: str


_cache_state = {}


def calculate_aqhi(pm25: float | None, no2_ug: float | None, o3_ug: float | None) -> float | None:
    """Calculate Canadian AQHI-like index from pollutant concentrations.

    Simplified AQHI formula that produces typical 1-50 range values.
    AQHI ≈ 10 × (PM2.5/35 + NO2/200 + O3/120)

    Args:
        pm25: PM2.5 concentration (µg/m³)
        no2_ug: Nitrogen dioxide (µg/m³)
        o3_ug: Ozone (µg/m³)

    Returns:
        AQHI value (float, typically 1-50) or None if any input is None
    """
    if pm25 is None or no2_ug is None or o3_ug is None:
        return None
    return 10 * (pm25 / 35 + no2_ug / 200 + o3_ug / 120)


def aqhi_level(value: float | None) -> tuple[str, str, str]:
    """Return (label, emoji, color_hex) for AQHI value.

    Categories per Health Canada:
    - Good (1-3): 🟢
    - Moderate (4-6): 🟡
    - Poor (7-10): 🟠
    - High (11-15): 🔴
    - Very High (16+): 🟣

    Args:
        value: AQHI value, or None

    Returns:
        Tuple of (label, emoji, hex_color)
    """
    if value is None:
        return ("Unknown", "❓", "#999999")
    if value < 4:
        return ("Good", "🟢", "#00dd00")
    if value < 7:
        return ("Moderate", "🟡", "#ffaa00")
    if value < 11:
        return ("Poor", "🟠", "#ff6600")
    if value < 16:
        return ("High", "🔴", "#dd0000")
    return ("Very High", "🟣", "#8800cc")


def fetch_air_quality(lat: float, lon: float) -> AirQualityReport:
    """Fetch air quality data and calculate AQHI. Cached for 5 minutes."""
    cache_key = (lat, lon)
    now = time.time()

    cached = _cache_state.get(cache_key)
    if cached and now - cached["time"] < _CACHE_TTL:
        return cached["result"]

    result = _fetch_air_quality_uncached(lat, lon)

    _cache_state[cache_key] = {"result": result, "time": now}
    return result


def _fetch_air_quality_uncached(lat: float, lon: float) -> AirQualityReport:
    """Fetch air quality data from Open-Meteo (no caching)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm2_5,nitrogen_dioxide,ozone",
        "timezone": "auto",
    }
    try:
        response = httpx.get(_AIR_QUALITY_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        logger.warning("aqhi: fetch failed: %s", exc)
        return AirQualityReport(None, None, None, None, "Unknown", "❓", "#999999")

    try:
        current = data.get("current", {})
        pm25 = current.get("pm2_5")
        no2 = current.get("nitrogen_dioxide")
        o3 = current.get("ozone")

        aqhi_val = calculate_aqhi(pm25, no2, o3)
        label, emoji, color = aqhi_level(aqhi_val)

        return AirQualityReport(
            aqhi=aqhi_val,
            pm25=pm25,
            no2=no2,
            o3=o3,
            level=label,
            emoji=emoji,
            color=color,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("aqhi: parse failed: %s", exc)
        return AirQualityReport(None, None, None, None, "Unknown", "❓", "#999999")


def clear_cache() -> None:
    """Clear cache (used by tests)."""
    global _cache_state
    _cache_state = {}
