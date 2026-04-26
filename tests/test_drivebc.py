import time
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import Point, mapping

import fetchers.drivebc as drivebc
from fetchers.drivebc import RoadEvent, _is_relevant, _intersects_corridor, fetch_drivebc_events
from route_buffer import build_route_corridor, destination_buffer


@pytest.fixture(autouse=True)
def clear_cache():
    drivebc.clear_cache()
    yield
    drivebc.clear_cache()


def _make_event(severity="MINOR", description="", lat=49.73, lon=-123.11):
    return {
        "headline": "Test event",
        "description": description,
        "severity": severity,
        "geography": {"type": "Point", "coordinates": [lon, lat]},
        "updated": "2026-04-25T14:00:00Z",
    }


# --- filter logic ---

def test_major_event_included():
    assert _is_relevant(_make_event(severity="MAJOR"))


def test_moderate_event_included():
    assert _is_relevant(_make_event(severity="MODERATE"))


def test_minor_with_closed_keyword():
    assert _is_relevant(_make_event(severity="MINOR", description="Road is closed"))


def test_minor_with_avalanche_keyword():
    assert _is_relevant(_make_event(severity="MINOR", description="Avalanche risk on route"))


def test_minor_with_washout_keyword():
    assert _is_relevant(_make_event(severity="MINOR", description="Washout reported"))


def test_minor_no_keyword_excluded():
    assert not _is_relevant(_make_event(severity="MINOR", description="Slight delay expected"))


def test_unknown_severity_no_keyword_excluded():
    assert not _is_relevant(_make_event(severity="UNKNOWN", description="Traffic slow"))


# --- spatial filter ---

def test_event_inside_corridor_included():
    start = (49.70, -123.15)
    destination = (49.77, -123.12)
    corridor = build_route_corridor(start, destination)
    event = _make_event(lat=49.73, lon=-123.13)
    assert _intersects_corridor(event, corridor)


def test_event_outside_corridor_excluded():
    start = (49.70, -123.15)
    destination = (49.77, -123.12)
    corridor = build_route_corridor(start, destination)
    # Point far away — Vancouver Island
    event = _make_event(lat=48.5, lon=-123.4)
    assert not _intersects_corridor(event, corridor)


def test_event_no_geography_excluded():
    corridor = destination_buffer((49.7, -123.1), radius_km=10)
    event = {"headline": "Test", "description": "closed", "severity": "MAJOR", "geography": None}
    assert not _intersects_corridor(event, corridor)


# --- full fetch with mock ---

def _mock_response(events: list) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"events": events}
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_returns_relevant_intersecting_events():
    corridor = build_route_corridor((49.70, -123.15), (49.77, -123.12))
    events = [
        _make_event(severity="MAJOR", lat=49.73, lon=-123.13),   # inside, relevant
        _make_event(severity="MINOR", lat=49.73, lon=-123.13),   # inside, not relevant
        _make_event(severity="MAJOR", lat=48.5, lon=-123.4),     # outside, relevant
    ]
    with patch("fetchers.drivebc.httpx.get", return_value=_mock_response(events)):
        results = fetch_drivebc_events(corridor)
    assert len(results) == 1
    assert results[0].severity == "MAJOR"


def test_fetch_populates_cache():
    corridor = destination_buffer((49.7, -123.1), radius_km=50)
    events = [_make_event(severity="MAJOR", lat=49.7, lon=-123.1)]
    with patch("fetchers.drivebc.httpx.get", return_value=_mock_response(events)) as mock_get:
        fetch_drivebc_events(corridor)
        fetch_drivebc_events(corridor)
    # second call should use cache — httpx.get called only once
    mock_get.assert_called_once()


def test_cache_expires():
    corridor = destination_buffer((49.7, -123.1), radius_km=50)
    events = [_make_event(severity="MAJOR", lat=49.7, lon=-123.1)]
    with patch("fetchers.drivebc.httpx.get", return_value=_mock_response(events)) as mock_get:
        fetch_drivebc_events(corridor)
        # Force expiry by backdating cache timestamp
        drivebc._cache["ts"] = time.monotonic() - drivebc._CACHE_TTL - 1
        fetch_drivebc_events(corridor)
    assert mock_get.call_count == 2
