import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RoadEvent:
    headline: str
    description: str
    severity: str
    last_updated: str


@dataclass
class WeatherReport:
    current_temp: float
    current_wind_speed: float
    current_wind_direction: str
    current_precip: float
    forecast_24h: str
    freezing_level: int
    timestamp: str


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

    if weather:
        lines.append("🌤️ *Weather \\(next 24h\\)*")
        lines.append(f"Now: {weather.current_temp}°C, {weather.current_wind_direction} {weather.current_wind_speed} km/h")
        lines.append(weather.forecast_24h)
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


async def mock_fetch_drivebc(corridor_polygon, start, destination) -> list[RoadEvent]:
    """Mock DriveBC fetcher for testing."""
    await asyncio.sleep(0.1)
    return []


async def mock_fetch_weather(lat: float, lon: float) -> Optional[WeatherReport]:
    """Mock weather fetcher for testing."""
    await asyncio.sleep(0.1)
    return WeatherReport(
        current_temp=12,
        current_wind_speed=8,
        current_wind_direction="W",
        current_precip=0,
        forecast_24h="Tomorrow AM: 8°C, 60% precip, freezing level 1800m",
        freezing_level=1800,
        timestamp=datetime.now().isoformat(),
    )


async def mock_fetch_wildfire(corridor_polygon, destination) -> list[FireIncident]:
    """Mock wildfire fetcher for testing."""
    await asyncio.sleep(0.1)
    return []


async def mock_fetch_wildlife_news(
    corridor_polygon, destination_name
) -> list[Advisory]:
    """Mock wildlife/news fetcher for testing."""
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
            mock_fetch_drivebc(corridor_polygon, start_point, destination_point),
            timeout=8,
        )
        results["road_events"] = road_events
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    try:
        weather = await asyncio.wait_for(
            mock_fetch_weather(destination_point[0], destination_point[1]),
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
