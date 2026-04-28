from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 3.0
_ALPINE_ELEVATION_M = 1200
_CACHE_TTL = 900  # 15 minutes

_cache_state = {
    "weather": {"last_result": None, "last_time": 0, "last_coords": None},
    "weather_3day": {"last_result": None, "last_time": 0, "last_coords": None},
}

_WMO_CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm + hail",
}


@dataclass
class WeatherReport:
    current_temp: float | None
    current_wind: float | None
    current_precip: float | None
    forecast_24h: list[dict]
    freezing_level: float | None
    alerts: list[str]
    timestamp: str
    elevation: float | None = None
    snow_depth: float | None = None
    snowfall_24h: float | None = None
    wind_gusts: float | None = None
    is_alpine: bool = False


def _fetch_weather_uncached(lat: float, lon: float) -> WeatherReport:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "temperature_2m,windspeed_10m,precipitation,freezinglevel_height,"
            "snowfall,snow_depth,windgusts_10m"
        ),
        "current_weather": "true",
        "forecast_days": 2,
        "timezone": "auto",
    }

    try:
        response = httpx.get(_OPEN_METEO_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        return _empty_report("timeout")
    except httpx.HTTPError:
        return _empty_report("http_error")

    cw = data.get("current_weather") or {}
    hourly = data.get("hourly") or {}
    elevation = data.get("elevation")

    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    winds = hourly.get("windspeed_10m") or []
    precips = hourly.get("precipitation") or []
    freezing = hourly.get("freezinglevel_height") or []
    snowfalls = hourly.get("snowfall") or []
    snow_depths = hourly.get("snow_depth") or []
    gusts = hourly.get("windgusts_10m") or []

    forecast_24h = [
        {"time": t, "temp": te, "wind": wi, "precip": pr, "freezing_level": fr}
        for t, te, wi, pr, fr in zip(
            times[:24], temps[:24], winds[:24], precips[:24], freezing[:24]
        )
    ]

    alerts = _fetch_ec_alerts(lat, lon)

    return WeatherReport(
        current_temp=cw.get("temperature"),
        current_wind=cw.get("windspeed"),
        current_precip=precips[0] if precips else None,
        forecast_24h=forecast_24h,
        freezing_level=freezing[0] if freezing else None,
        alerts=alerts,
        timestamp=cw.get("time") or datetime.now(timezone.utc).isoformat(),
        elevation=elevation,
        snow_depth=snow_depths[0] if snow_depths else None,
        snowfall_24h=sum(snowfalls[:24]) if snowfalls else None,
        wind_gusts=gusts[0] if gusts else None,
        is_alpine=(elevation or 0) > _ALPINE_ELEVATION_M,
    )


def fetch_weather(lat: float, lon: float) -> WeatherReport:
    now = time.monotonic()
    coords = (lat, lon)
    cache = _cache_state["weather"]
    if (
        cache["last_result"] is not None
        and cache["last_coords"] == coords
        and (now - cache["last_time"]) < _CACHE_TTL
    ):
        return cache["last_result"]

    result = _fetch_weather_uncached(lat, lon)
    cache["last_result"] = result
    cache["last_coords"] = coords
    cache["last_time"] = now
    return result


@dataclass
class DayForecast:
    date: str
    temp_max: float
    temp_min: float
    precip_mm: float
    snow_cm: float
    condition: str


def _fetch_weather_3day_uncached(lat: float, lon: float) -> list[DayForecast]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,weathercode",
        "forecast_days": 3,
        "timezone": "auto",
    }
    try:
        response = httpx.get(_OPEN_METEO_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.TimeoutException, httpx.HTTPError):
        return []

    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precips = daily.get("precipitation_sum") or []
    snows = daily.get("snowfall_sum") or []
    codes = daily.get("weathercode") or []

    result = []
    for dt, hi, lo, pr, sn, code in zip(dates, highs, lows, precips, snows, codes):
        try:
            d = datetime.strptime(dt, "%Y-%m-%d")
            date_str = d.strftime("%a %b %-d")
        except ValueError:
            date_str = dt
        condition = _WMO_CODES.get(int(code) if code is not None else 0, "Variable")
        result.append(DayForecast(
            date=date_str,
            temp_max=hi or 0,
            temp_min=lo or 0,
            precip_mm=pr or 0,
            snow_cm=sn or 0,
            condition=condition,
        ))
    return result


def fetch_weather_3day(lat: float, lon: float) -> list[DayForecast]:
    now = time.monotonic()
    coords = (lat, lon)
    cache = _cache_state["weather_3day"]
    if (
        cache["last_result"] is not None
        and cache["last_coords"] == coords
        and (now - cache["last_time"]) < _CACHE_TTL
    ):
        return cache["last_result"]

    result = _fetch_weather_3day_uncached(lat, lon)
    cache["last_result"] = result
    cache["last_coords"] = coords
    cache["last_time"] = now
    return result


_EC_ALERT_KEYWORDS = frozenset({"WARNING", "WATCH", "ADVISORY", "STATEMENT", "ENDED"})
_EC_FEED_URL = "https://weather.gc.ca/rss/warning/bc_e.xml"


def _parse_ec_xml(xml_bytes: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    alerts: list[str] = []
    tag = root.tag

    if "feed" in tag or tag == "{http://www.w3.org/2005/Atom}feed":
        # Atom feed
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f"{{{atom_ns}}}entry"):
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            _maybe_add_alert(title, alerts)
    else:
        # RSS 2.0: root is <rss>, items are inside <channel>
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            _maybe_add_alert(title, alerts)

    return alerts[:5]


def _maybe_add_alert(title: str, alerts: list[str]) -> None:
    upper = title.upper()
    if title and any(kw in upper for kw in _EC_ALERT_KEYWORDS):
        # Skip the generic feed-level title entries (e.g. "BC Warnings", "No alerts")
        if len(title) > 15 and "NO ALERTS" not in upper:
            alerts.append(title)


def _fetch_ec_alerts(lat: float, lon: float) -> list[str]:
    try:
        response = httpx.get(
            _EC_FEED_URL,
            timeout=_TIMEOUT,
            headers={"User-Agent": "BCBackcountryScout/1.0"},
        )
        if response.status_code != 200:
            return []
        return _parse_ec_xml(response.content)
    except Exception:
        return []


def _empty_report(reason: str) -> WeatherReport:
    return WeatherReport(
        current_temp=None,
        current_wind=None,
        current_precip=None,
        forecast_24h=[],
        freezing_level=None,
        alerts=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def clear_cache() -> None:
    _cache_state["weather"]["last_result"] = None
    _cache_state["weather"]["last_coords"] = None
    _cache_state["weather"]["last_time"] = 0
    _cache_state["weather_3day"]["last_result"] = None
    _cache_state["weather_3day"]["last_coords"] = None
    _cache_state["weather_3day"]["last_time"] = 0
