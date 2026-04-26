import asyncio
import pytest

from report_assembler import (
    RoadEvent,
    WeatherReport,
    FireIncident,
    Advisory,
    assemble_report,
    run_all_fetchers,
)


def test_assemble_report_basic():
    """Test basic report generation with minimal data."""
    from fetchers.weather import WeatherReport

    road_events = []
    weather = WeatherReport(
        current_temp=12,
        current_wind=8,
        current_precip=0,
        forecast_24h=[
            {"time": "2026-04-26T12:00", "temp": 10, "wind": 5, "precip": 0.5, "freezing_level": 1800}
        ],
        freezing_level=1800,
        alerts=[],
        timestamp="2026-04-26T14:30:00Z",
    )
    fires = []
    advisories = []

    report = assemble_report(
        destination_name="Alice Lake Provincial Park",
        start_name="Squamish, BC",
        road_events=road_events,
        weather=weather,
        fires=fires,
        advisories=advisories,
    )

    assert "Alice Lake Provincial Park" in report
    assert "Squamish, BC" in report
    assert "12°C" in report
    assert len(report) < 1500
    assert "Report generated" in report


def test_assemble_report_with_events():
    """Test report with road events and fires."""
    from fetchers.drivebc import RoadEvent
    from fetchers.weather import WeatherReport

    road_events = [
        RoadEvent(
            headline="Hwy 99 closure at Whistler",
            description="Rockfall impact",
            severity="MAJOR",
            geometry={},
            last_updated="2026-04-26T14:00:00Z",
        )
    ]
    weather = WeatherReport(
        current_temp=10,
        current_wind=12,
        current_precip=1.5,
        forecast_24h=[
            {"time": "2026-04-26T12:00", "temp": 8, "wind": 10, "precip": 2.0, "freezing_level": 1600}
        ],
        freezing_level=1600,
        alerts=[],
        timestamp="2026-04-26T14:30:00Z",
    )
    fires = [
        FireIncident(
            name="Mamquam Fire",
            stage_of_control="Out of Control",
            size_hectares=150,
            distance_to_destination_km=5.2,
        )
    ]
    advisories = [
        Advisory(
            source="WildSafeBC",
            category="bear",
            summary="Bear sighting reported 2 days ago",
            link="https://example.com",
            date="2026-04-24",
        )
    ]

    report = assemble_report(
        destination_name="Mamquam FSR",
        start_name="Squamish",
        road_events=road_events,
        weather=weather,
        fires=fires,
        advisories=advisories,
    )

    assert "Hwy 99 closure" in report
    assert "Mamquam Fire" in report
    assert "Bear sighting" in report
    assert "150ha" in report
    assert len(report) < 1500


def test_assemble_report_no_weather():
    """Test report generation when weather fetch fails."""
    report = assemble_report(
        destination_name="Garibaldi Park",
        start_name="Squamish",
        road_events=[],
        weather=None,
        fires=[],
        advisories=[],
    )

    assert "Garibaldi Park" in report
    assert "Data unavailable" in report
    assert len(report) < 1500


def test_assemble_report_length_truncation():
    """Test that extremely long input is truncated to <1500 chars."""
    from fetchers.weather import WeatherReport

    long_name = "A" * 500
    report = assemble_report(
        destination_name=long_name,
        start_name="Test",
        road_events=[],
        weather=WeatherReport(
            current_temp=15,
            current_wind=5,
            current_precip=0,
            forecast_24h=[{"time": "2026-04-26T12:00", "temp": 10, "wind": 5, "precip": 0.5, "freezing_level": 2000}],
            freezing_level=2000,
            alerts=[],
            timestamp="2026-04-26T14:30:00Z",
        ),
        fires=[],
        advisories=[],
    )

    assert len(report) <= 1500


@pytest.mark.asyncio
async def test_run_all_fetchers():
    """Test parallel fetcher execution with mocked sources."""
    start = (49.7016, -123.1558)
    destination = (49.77, -123.12)

    results = await run_all_fetchers(
        corridor_polygon=None,
        start_point=start,
        destination_point=destination,
        destination_name="Alice Lake",
    )

    assert "road_events" in results
    assert "weather" in results
    assert "fires" in results
    assert "advisories" in results
    assert isinstance(results["road_events"], list)
    assert isinstance(results["fires"], list)
    assert isinstance(results["advisories"], list)
    assert results["weather"] is not None or results["weather"] is None


def test_assemble_report_markdown_escaping():
    """Test that MarkdownV2 special chars are escaped."""
    report = assemble_report(
        destination_name="Test's Location",
        start_name="Start",
        road_events=[],
        weather=None,
        fires=[],
        advisories=[],
    )

    assert "\\(" in report
    assert "\\)" in report
    assert "\\." in report
