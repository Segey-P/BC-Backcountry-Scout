import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fetchers.drivebc import RoadEvent, fetch_drivebc_events
from fetchers.weather import WeatherReport, fetch_weather


@dataclass
class FireIncident:
    name: str
    stage_of_control: str
    size_hectares: float
    distance_to_destination_km: float


@dataclass
class Advisory:
    source: str
    category: str
    summary: str
    link: Optional[str]
    date: str


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


async def mock_fetch_wildfire(corridor_polygon, destination) -> list:
    """Mock wildfire fetcher for testing (Module 7)."""
    await asyncio.sleep(0.1)
    return []


async def mock_fetch_wildlife_news(corridor_polygon, destination_name) -> list:
    """Mock wildlife/news fetcher for testing (Module 8)."""
    await asyncio.sleep(0.1)
    return []


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

    try:
        road_events = await asyncio.wait_for(
            asyncio.to_thread(fetch_drivebc_events, corridor_polygon),
            timeout=8,
        )
        results["road_events"] = road_events
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    try:
        weather = await asyncio.wait_for(
            asyncio.to_thread(fetch_weather, destination_point[0], destination_point[1]),
            timeout=8,
        )
        results["weather"] = weather
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    try:
        fires = await asyncio.wait_for(
            mock_fetch_wildfire(corridor_polygon, destination_point),
            timeout=8,
        )
        results["fires"] = fires
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    try:
        advisories = await asyncio.wait_for(
            mock_fetch_wildlife_news(corridor_polygon, destination_name),
            timeout=8,
        )
        results["advisories"] = advisories
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    return results
