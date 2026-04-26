import asyncio
from datetime import datetime
from typing import Optional

from fetchers.drivebc import RoadEvent, fetch_drivebc_events
from fetchers.weather import WeatherReport, fetch_weather
from fetchers.wildfire import FireIncident, fetch_wildfire
from fetchers.wildlife_news import Advisory, fetch_wildlife_news


def assemble_report(
    destination_name: str,
    start_name: str,
    road_events: list[RoadEvent],
    weather: Optional[WeatherReport],
    fires: list[FireIncident],
    advisories: list[Advisory],
) -> str:
    """Assemble a single Telegram MarkdownV2 message from fetched data."""

    lines = []

    lines.append(f"🌲 *{destination_name}*")
    lines.append(f"From: {start_name}")
    lines.append("")

    lines.append("🚨 *Safety*")

    if road_events:
        for event in road_events:
            lines.append(f"⚠️ {event.headline}")
    else:
        lines.append("✅ No major road events")

    if fires:
        for fire in fires:
            lines.append(
                f"🔥 {fire.name} ({fire.size_hectares:.0f}ha, {fire.distance_to_destination_km:.1f}km away)"
            )
    else:
        lines.append("✅ No active wildfires nearby")

    if advisories:
        for adv in advisories:
            lines.append(f"⚠️ {adv.summary} ({adv.source})")
    else:
        lines.append("✅ No wildlife advisories")

    lines.append("")

    if weather and weather.current_temp is not None:
        lines.append("🌤️ *Weather \\(next 24h\\)*")
        wind_str = f"{weather.current_wind} km/h" if weather.current_wind else "calm"
        lines.append(f"Now: {weather.current_temp}°C, {wind_str}")
        if weather.forecast_24h:
            precip_12h = sum(h.get("precip", 0) for h in weather.forecast_24h[:12])
            freezing = weather.freezing_level if weather.freezing_level else "N/A"
            lines.append(f"Next 12h: {precip_12h:.1f}mm precip, freezing level {freezing}m")
        if weather.alerts:
            for alert in weather.alerts[:2]:
                lines.append(f"⚠️ {alert}")
    else:
        lines.append("🌤️ *Weather*")
        lines.append("Data unavailable \\(timeout\\)")

    lines.append("")

    lines.append("🚗 *Driving conditions*")
    if road_events:
        lines.append("Monitor DriveBC for active events")
    else:
        lines.append("Highways open, normal flow")

    lines.append("")

    now = datetime.now().strftime("%H:%M %Z").replace("UTC", "PDT")
    lines.append(
        f"_Report generated: {now}\\. Conditions change fast — verify before you go\\._"
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
    }

    async def _run(coro):
        try:
            return await asyncio.wait_for(coro, timeout=8)
        except (asyncio.TimeoutError, Exception):
            return None

    road_events, weather, fires, advisories = await asyncio.gather(
        _run(asyncio.to_thread(fetch_drivebc_events, corridor_polygon)),
        _run(asyncio.to_thread(fetch_weather, destination_point[0], destination_point[1])),
        _run(asyncio.to_thread(fetch_wildfire, corridor_polygon, destination_point)),
        _run(asyncio.to_thread(fetch_wildlife_news, corridor_polygon, destination_name)),
    )

    results["road_events"] = road_events or []
    results["weather"] = weather
    results["fires"] = fires or []
    results["advisories"] = advisories or []

    return results
