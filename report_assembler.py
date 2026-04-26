import asyncio
import html
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fetchers.drivebc import RoadEvent, fetch_drivebc_events
from fetchers.eta import ETAResult, fetch_eta
from fetchers.weather import WeatherReport, fetch_weather
from fetchers.wildfire import FireIncident, fetch_wildfire
from fetchers.wildlife_news import Advisory, fetch_wildlife_news

_PACIFIC = ZoneInfo("America/Vancouver")

def _e(value) -> str:
    """Escape dynamic content for HTML — converts to str first so numbers are safe."""
    return html.escape(str(value))


def assemble_report(
    destination_name: str,
    start_name: str,
    road_events: list[RoadEvent],
    weather: Optional[WeatherReport],
    fires: list[FireIncident],
    advisories: list[Advisory],
    eta: Optional[ETAResult] = None,
) -> str:
    """Assemble a single Telegram HTML message from fetched data."""

    lines = []

    lines.append(f"🌲 <b>{_e(destination_name)}</b>")
    lines.append(f"From: {_e(start_name)}")
    lines.append("")

    lines.append("🛡️ <b>Safety</b>")

    if road_events:
        for event in road_events:
            lines.append(f"⚠️ {_e(event.headline)}")
    else:
        lines.append("✅ No major road events")

    if fires:
        for fire in fires:
            lines.append(
                f"🔥 {_e(fire.name)} ({fire.size_hectares:.0f}ha, {fire.distance_to_destination_km:.1f}km away)"
            )
    else:
        lines.append("✅ No active wildfires nearby")

    if advisories:
        for adv in advisories:
            lines.append(f"🔔 {_e(adv.summary)} ({_e(adv.source)})")
    else:
        lines.append("✅ No wildlife advisories")

    lines.append("")

    if weather and weather.current_temp is not None:
        if weather.is_alpine and weather.elevation:
            lines.append(f"🏔️ <b>Alpine Weather ({weather.elevation:.0f}m)</b>")
        else:
            lines.append("🌤️ <b>Weather (next 24h)</b>")
        wind_str = f"{weather.current_wind:.0f} km/h" if weather.current_wind else "calm"
        gusts_str = f", gusts {weather.wind_gusts:.0f}" if weather.wind_gusts else ""
        lines.append(f"Now: {_e(weather.current_temp)}°C, {_e(wind_str)}{_e(gusts_str)}")
        if weather.forecast_24h:
            precip_12h = sum(h.get("precip", 0) for h in weather.forecast_24h[:12])
            freezing = weather.freezing_level if weather.freezing_level else "N/A"
            lines.append(f"Next 12h: {precip_12h:.1f}mm precip, freezing level {freezing}m")
        if weather.is_alpine:
            if weather.snow_depth is not None:
                lines.append(f"Snow depth: {weather.snow_depth:.0f}cm")
            if weather.snowfall_24h and weather.snowfall_24h > 0:
                lines.append(f"Recent snowfall: {weather.snowfall_24h:.1f}cm")
            if (
                weather.elevation
                and weather.freezing_level
                and weather.freezing_level < weather.elevation + 200
            ):
                lines.append("⚠️ Freezing level near or below terrain")
        if weather.alerts:
            for alert in weather.alerts[:2]:
                lines.append(f"⚠️ {_e(alert)}")
    else:
        lines.append("🌤️ <b>Weather</b>")
        lines.append("Data unavailable (timeout)")

    lines.append("")

    lines.append("🚗 <b>Driving</b>")
    if eta:
        lines.append(f"{eta.distance_text} · {eta.duration_traffic_text} with traffic")
    if road_events:
        lines.append("Monitor DriveBC for active events")
    else:
        lines.append("Highways open, normal flow")

    lines.append("")

    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    lines.append(
        f"<i>Report generated: {now}. Conditions change fast — verify before you go.</i>"
    )

    message = "\n".join(lines)

    if len(message) > 1500:
        message = message[:1497] + "…"

    return message


async def run_all_fetchers(
    corridor_polygon, start_point: tuple, destination_point: tuple, destination_name: str
) -> dict:
    """Run all data fetchers in parallel with 8-second timeout per fetcher."""

    results = {
        "road_events": [],
        "weather": None,
        "fires": [],
        "advisories": [],
        "eta": None,
    }

    async def _run(coro):
        try:
            return await asyncio.wait_for(coro, timeout=8)
        except (asyncio.TimeoutError, Exception):
            return None

    road_events, weather, fires, advisories, eta = await asyncio.gather(
        _run(asyncio.to_thread(fetch_drivebc_events, corridor_polygon)),
        _run(asyncio.to_thread(fetch_weather, destination_point[0], destination_point[1])),
        _run(asyncio.to_thread(fetch_wildfire, corridor_polygon, destination_point)),
        _run(asyncio.to_thread(fetch_wildlife_news, corridor_polygon, destination_name)),
        _run(asyncio.to_thread(fetch_eta, start_point, destination_point)),
    )

    results["road_events"] = road_events or []
    results["weather"] = weather
    results["fires"] = fires or []
    results["advisories"] = advisories or []
    results["eta"] = eta

    return results
