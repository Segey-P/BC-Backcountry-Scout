import asyncio
import html
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fetchers.avalanche import AvalancheReport, fetch_avalanche
from fetchers.drivebc import RoadEvent, fetch_drivebc_events
from fetchers.eta import ETAResult, fetch_eta
from fetchers.weather import DayForecast, WeatherReport, fetch_weather, fetch_weather_3day
from fetchers.wildfire import FireBan, FireIncident, fetch_fire_bans, fetch_wildfire
from fetchers.wildlife_news import Advisory, fetch_wildlife_news

_PACIFIC = ZoneInfo("America/Vancouver")


def _is_avalanche_season() -> bool:
    """Avalanche forecasts are only issued Oct 1 – Apr 30."""
    m = date.today().month
    return m <= 4 or m >= 10


def _is_fire_ban_season() -> bool:
    """Fire bans/restrictions are typically relevant May 1 – Oct 31."""
    m = date.today().month
    return 5 <= m <= 10


def _is_wildlife_season() -> bool:
    """Wildlife advisories are relevant Apr 1 – Nov 30."""
    m = date.today().month
    return 4 <= m <= 11


def _e(value) -> str:
    """Escape dynamic content for HTML — converts to str first so numbers are safe."""
    return html.escape(str(value))


def _freezing_level_trend(forecast_24h: list[dict]) -> str:
    levels = [h["freezing_level"] for h in forecast_24h if h.get("freezing_level") is not None]
    if len(levels) < 6:
        return ""
    first = sum(levels[:4]) / 4
    last = sum(levels[-4:]) / 4
    delta = last - first
    if delta > 150:
        return " ↑ rising"
    if delta < -150:
        return " ↓ falling"
    return " → stable"


def assemble_report(
    destination_name: str,
    start_name: str,
    road_events: list[RoadEvent],
    weather: Optional[WeatherReport],
    fires: list[FireIncident],
    advisories: list[Advisory],
    eta: Optional[ETAResult] = None,
    avalanche: Optional[AvalancheReport] = None,
    bans: list[FireBan] = None,
) -> str:
    """Assemble a single Telegram HTML message from fetched data."""

    lines = []

    lines.append(f"<b>To: {_e(destination_name)}</b>")
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

    if _is_fire_ban_season():
        if bans:
            # We just show a summary in the main report
            for ban in bans:
                lines.append(f"🚫 <b>Fire Ban:</b> {_e(ban.fire_centre)} ({_e(ban.category)})")
        else:
            lines.append("✅ No fire bans in effect")

    if _is_wildlife_season():
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
        gusts_str = f", gusts {weather.wind_gusts:.0f} km/h" if weather.wind_gusts else ""
        lines.append(f"Now: {_e(weather.current_temp)}°C, {_e(wind_str)}{_e(gusts_str)}")
        if weather.forecast_24h:
            precip_12h = sum(h.get("precip", 0) for h in weather.forecast_24h[:12])
            freezing = weather.freezing_level if weather.freezing_level else "N/A"
            trend = _freezing_level_trend(weather.forecast_24h)
            lines.append(f"Next 12h: {precip_12h:.1f}mm precip, freezing level {freezing}m{trend}")
        if weather.is_alpine:
            if weather.snowfall_24h and weather.snowfall_24h > 0:
                lines.append(f"New snow today: {weather.snowfall_24h:.1f}cm")
            if (
                weather.elevation
                and weather.freezing_level
                and weather.freezing_level < weather.elevation + 200
            ):
                lines.append("⚠️ Freezing level near or below terrain")
        if weather.sunset:
            try:
                from datetime import datetime as dt_cls
                sunset_time = dt_cls.fromisoformat(weather.sunset.replace('Z', '+00:00')).astimezone(_PACIFIC)
                lines.append(f"🌅 Sunset: {sunset_time.strftime('%H:%M')}")
            except (ValueError, AttributeError, TypeError):
                pass
        if weather.is_alpine:
            if _is_avalanche_season() and avalanche and avalanche.days:
                today = avalanche.days[0]
                if today.alpine.value == 0 and today.treeline.value == 0:
                    lines.append("Avalanche: No forecast issued — check <a href=\"https://www.avalanche.ca\">avalanche.ca</a>")
                else:
                    lines.append(
                        f"Avalanche: {today.alpine.icon} {today.alpine.label} (alpine)"
                        f" · {today.treeline.icon} {today.treeline.label} (treeline)"
                    )
        if weather.alerts:
            for alert in weather.alerts[:2]:
                lines.append(f"⚠️ {_e(alert)}")
    else:
        lines.append("🌤️ <b>Weather</b>")
        lines.append("Data unavailable (timeout)")

    lines.append("")

    lines.append("🚗 <b>Driving</b>")
    if eta:
        lines.append(f"{_e(eta.distance_text)} · {_e(eta.duration_traffic_text)} with traffic")
    else:
        lines.append("⚠️ Travel time unavailable (API error or timeout)")
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


def assemble_3day_report(
    destination_name: str,
    forecasts: list[DayForecast],
    lat: float | None = None,
    lon: float | None = None,
) -> str:
    if not forecasts:
        return f"📅 <b>3-Day Forecast — {_e(destination_name)}</b>\n\nData unavailable."

    elevation = forecasts[0].elevation if forecasts else None
    elev_str = f" ({elevation:.0f}m)" if elevation else ""
    lines = [f"📅 <b>3-Day Forecast — {_e(destination_name)}</b>{elev_str}", ""]

    for day in forecasts:
        snow_str = f", {day.snow_cm:.0f}cm snow" if day.snow_cm >= 0.5 else ""
        freeze_str = f", freezing {day.freezing_level:.0f}m" if day.freezing_level is not None else ""
        lines.append(
            f"<b>{_e(day.date)}</b>: {_e(day.condition)}"
            f" ↑{day.temp_max:.0f}° ↓{day.temp_min:.0f}°"
            f", {day.precip_mm:.1f}mm{snow_str}{freeze_str}"
        )

    lines.append("")
    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    windy_link = (
        f' · <a href="https://www.windy.com/{lat:.2f}/{lon:.2f}">Windy</a>'
        if lat is not None and lon is not None else ""
    )
    lines.append(f"<i>Source: Open-Meteo · {now}{windy_link}</i>")
    return "\n".join(lines)


def assemble_avalanche_report(
    destination_name: str,
    avx: Optional[AvalancheReport],
    weather: Optional[WeatherReport] = None,
) -> str:
    if not avx or not avx.days:
        return (
            f"🏔️ <b>Avalanche Forecast — {_e(destination_name)}</b>\n\n"
            "No forecast available. Check <a href=\"https://www.avalanche.ca\">avalanche.ca</a> directly."
        )

    if all(d.alpine.value == 0 and d.treeline.value == 0 and d.below_treeline.value == 0 for d in avx.days):
        return (
            f"🏔️ <b>Avalanche Forecast — {_e(destination_name)}</b>\n"
            f"Region: {_e(avx.region_name)}\n\n"
            "No forecast currently issued for this region. "
            "Typical at end of season (spring) or before season opens (fall).\n\n"
            '<i>Check <a href="https://www.avalanche.ca">avalanche.ca</a> directly.</i>'
        )

    lines = [
        f"🏔️ <b>Avalanche Forecast — {_e(destination_name)}</b>",
        f"Region: {_e(avx.region_name)}",
        "",
    ]
    for day in avx.days:
        alp = day.alpine
        tln = day.treeline
        btl = day.below_treeline
        lines.append(
            f"<b>{_e(day.date)}</b>: "
            f"Alpine {alp.icon} {_e(alp.label)}"
            f" · Treeline {tln.icon} {_e(tln.label)}"
            f" · Below {btl.icon} {_e(btl.label)}"
        )

    if avx.highlights:
        lines.append("")
        lines.append(_e(avx.highlights[:300]))

    if weather and weather.is_alpine and weather.current_temp is not None:
        lines.append("")
        wind_str = f"{weather.current_wind:.0f} km/h" if weather.current_wind else "calm"
        gusts_str = f", gusts {weather.wind_gusts:.0f} km/h" if weather.wind_gusts else ""
        lines.append(f"❄️ Alpine now: {_e(weather.current_temp)}°C, {_e(wind_str)}{_e(gusts_str)}")
        if weather.snowfall_24h and weather.snowfall_24h > 0:
            lines.append(f"New snow today: {weather.snowfall_24h:.1f}cm")
        if weather.freezing_level:
            lines.append(f"Freezing level: {weather.freezing_level:.0f}m")

    lines.append("")
    lines.append('<i>Source: <a href="https://www.avalanche.ca">avalanche.ca</a> · Always verify before you go.</i>')
    return "\n".join(lines)


def assemble_driving_report(
    destination_name: str,
    start_name: str,
    road_events: list[RoadEvent],
    eta: Optional[ETAResult],
) -> str:
    lines = [f"🚗 <b>Driving: {_e(start_name)} → {_e(destination_name)}</b>", ""]

    if road_events:
        for event in road_events:
            lines.append(f"⚠️ {_e(event.headline)}")
    else:
        lines.append("✅ No road events on route")

    lines.append("")
    if eta:
        lines.append(f"ETA: <b>{_e(eta.duration_traffic_text)}</b> with traffic ({_e(eta.distance_text)})")
    else:
        lines.append("⚠️ Travel time unavailable")

    lines.append("")
    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    lines.append(f"<i>Source: DriveBC + Google Maps · {now}</i>")
    return "\n".join(lines)


def assemble_wildfire_report(destination_name: str, fires: list[FireIncident]) -> str:
    lines = [f"🔥 <b>Wildfire Status — {_e(destination_name)}</b>", ""]

    if fires:
        for fire in fires:
            lines.append(
                f"🔥 {_e(fire.name)} ({fire.size_hectares:.0f}ha, {fire.distance_to_destination_km:.1f}km away)"
            )
    else:
        lines.append("✅ No active wildfires within 25km of destination or on route")

    lines.append("")
    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    lines.append(
        f"<i>Source: BC Wildfire Service · {now} · "
        '<a href="https://www2.gov.bc.ca/gov/content/safety/wildfire-status">bcwildfire.ca</a></i>'
    )
    return "\n".join(lines)


def assemble_fire_ban_report(destination_name: str, bans: list[FireBan]) -> str:
    lines = [f"🚫 <b>Fire Bans & Restrictions — {_e(destination_name)}</b>", ""]

    if bans:
        for ban in bans:
            lines.append(f"📍 <b>{_e(ban.fire_centre)} Fire Centre</b>")
            lines.append(f"Type: {_e(ban.type)}")
            lines.append(f"Prohibited: {_e(ban.description)}")
            if ban.bulletin_url:
                lines.append(f'🔗 <a href="{ban.bulletin_url}">Official Bulletin</a>')
            lines.append("")
    else:
        lines.append("✅ No active fire bans or prohibitions for this location.")
        lines.append("")
        lines.append("Note: Municipalities may have their own bylaws. Always check local signs.")

    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    lines.append(
        f"<i>Source: BC Wildfire Service · {now} · "
        '<a href="https://www2.gov.bc.ca/gov/content/safety/wildfire-status/fire-bans-and-prohibitions">bcwildfire.ca</a></i>'
    )
    return "\n".join(lines)


def assemble_wildlife_report(destination_name: str, advisories: list[Advisory]) -> str:
    lines = [f"🐻 <b>Wildlife Advisories — {_e(destination_name)}</b>", ""]

    if advisories:
        for adv in advisories:
            lines.append(f"🔔 {_e(adv.summary)} ({_e(adv.source)})")
    else:
        lines.append("✅ No active wildlife advisories for this area")

    lines.append("")
    now = datetime.now(tz=_PACIFIC).strftime("%H:%M %Z")
    lines.append(f"<i>Source: WildSafeBC + Squamish Chief · {now}</i>")
    return "\n".join(lines)


async def run_all_fetchers(
    corridor_polygon, start_point: tuple, destination_point: tuple, destination_name: str,
    focus: str | None = None,
) -> dict:
    """Run data fetchers in parallel with 8-second timeout each.

    When focus is set, only fetchers relevant to that focus are called.
    focus=None runs everything (full scout report).
    """
    results = {
        "road_events": [],
        "weather": None,
        "weather_3day": [],
        "fires": [],
        "advisories": [],
        "eta": None,
        "avalanche": None,
        "bans": [],
    }

    async def _run(coro):
        try:
            return await asyncio.wait_for(coro, timeout=8)
        except (asyncio.TimeoutError, Exception):
            return None

    list_keys = {"road_events", "fires", "advisories", "weather_3day", "bans"}

    task_map = {}
    if focus in (None, "driving"):
        task_map["road_events"] = asyncio.to_thread(fetch_drivebc_events, corridor_polygon)
        task_map["eta"] = asyncio.to_thread(fetch_eta, start_point, destination_point)
    if focus in (None, "avalanche"):
        task_map["weather"] = asyncio.to_thread(fetch_weather, destination_point[0], destination_point[1])
        if _is_avalanche_season():
            task_map["avalanche"] = asyncio.to_thread(fetch_avalanche, destination_point[0], destination_point[1])
    if focus == "weather":
        task_map["weather_3day"] = asyncio.to_thread(fetch_weather_3day, destination_point[0], destination_point[1])
    if focus in (None, "wildfire"):
        task_map["fires"] = asyncio.to_thread(fetch_wildfire, corridor_polygon, destination_point)
    if focus in (None, "fireban") and _is_fire_ban_season():
        task_map["bans"] = asyncio.to_thread(fetch_fire_bans, destination_point)
    if focus in (None, "wildlife") and _is_wildlife_season():
        task_map["advisories"] = asyncio.to_thread(fetch_wildlife_news, corridor_polygon, destination_name)

    keys = list(task_map.keys())
    fetched = await asyncio.gather(*[_run(task_map[k]) for k in keys])
    for key, value in zip(keys, fetched):
        results[key] = (value or []) if key in list_keys else value

    return results
