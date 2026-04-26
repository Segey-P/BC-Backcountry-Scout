from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 3.0


@dataclass
class WeatherReport:
    current_temp: float | None
    current_wind: float | None
    current_precip: float | None
    forecast_24h: list[dict]
    freezing_level: float | None
    alerts: list[str]
    timestamp: str


def fetch_weather(lat: float, lon: float) -> WeatherReport:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,windspeed_10m,precipitation,freezinglevel_height",
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

    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    winds = hourly.get("windspeed_10m") or []
    precips = hourly.get("precipitation") or []
    freezing = hourly.get("freezinglevel_height") or []

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
    )


def _fetch_ec_alerts(lat: float, lon: float) -> list[str]:
    """Fetch Environment Canada CAP alerts for the area. Returns empty list if unavailable."""
    try:
        # BC-wide warnings RSS feed; full CAP XML parsing is Phase 2
        response = httpx.get(
            "https://weather.gc.ca/rss/warning/bc_e.xml",
            timeout=_TIMEOUT,
            headers={"User-Agent": "BCBackcountryScout/1.0"},
        )
        if response.status_code != 200:
            return []
        # Extract <title> lines from RSS items (crude but avoids an XML dep for MVP)
        alerts = []
        for line in response.text.splitlines():
            line = line.strip()
            if line.startswith("<title>") and "WARNING" in line.upper():
                title = line.replace("<title>", "").replace("</title>", "").strip()
                if title:
                    alerts.append(title)
        return alerts[:5]  # cap at 5 to keep report short
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
