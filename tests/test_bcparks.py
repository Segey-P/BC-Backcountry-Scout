from unittest.mock import MagicMock, patch

import pytest

from fetchers.bcparks import ParkAdvisory, clear_cache, fetch_park_advisories


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


def _make_advisory(park_name, lat, lon, urgency_level=2, title="Trail Closure"):
    return {
        "title": title,
        "description": "Trails closed due to bear activity in the area.",
        "urgency": {"urgencyLevel": urgency_level, "id": urgency_level},
        "protectedArea": {
            "protectedAreaName": park_name,
            "name": park_name,
            "slug": park_name.lower().replace(" ", "-"),
            "latitude": lat,
            "longitude": lon,
        },
    }


def _mock_response(advisories):
    mock = MagicMock()
    mock.json.return_value = advisories
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_advisories_within_radius():
    squamish = (49.7016, -123.1558)
    # Alice Lake is ~5km from Squamish
    advisories = [_make_advisory("Alice Lake Provincial Park", 49.77, -123.12)]

    with patch("fetchers.bcparks.httpx.get", return_value=_mock_response(advisories)):
        results = fetch_park_advisories(squamish, radius_km=50)

    assert len(results) == 1
    assert "Alice Lake" in results[0].park_name


def test_fetch_advisories_outside_radius():
    squamish = (49.7016, -123.1558)
    # Okanagan is ~300km away
    advisories = [_make_advisory("Okanagan Park", 49.8, -119.5)]

    with patch("fetchers.bcparks.httpx.get", return_value=_mock_response(advisories)):
        results = fetch_park_advisories(squamish, radius_km=50)

    assert len(results) == 0


def test_fetch_advisories_api_error_returns_empty():
    import httpx

    squamish = (49.7016, -123.1558)
    with patch("fetchers.bcparks.httpx.get", side_effect=httpx.TimeoutException("timeout")):
        results = fetch_park_advisories(squamish)

    assert results == []


def test_advisory_url_uses_slug():
    squamish = (49.7016, -123.1558)
    advisories = [_make_advisory("Alice Lake Provincial Park", 49.77, -123.12)]

    with patch("fetchers.bcparks.httpx.get", return_value=_mock_response(advisories)):
        results = fetch_park_advisories(squamish)

    assert results[0].url.startswith("https://bcparks.ca")
    assert "alice" in results[0].url


def test_advisory_sorted_by_distance_then_urgency():
    squamish = (49.7016, -123.1558)
    advisories = [
        _make_advisory("Far Park", 50.5, -123.2, urgency_level=4),    # high urgency, far
        _make_advisory("Near Park", 49.75, -123.18, urgency_level=2),  # low urgency, near
    ]

    with patch("fetchers.bcparks.httpx.get", return_value=_mock_response(advisories)):
        results = fetch_park_advisories(squamish, radius_km=200)

    # Nearest park should be first (distance wins over urgency)
    assert "Near Park" in results[0].park_name


def test_description_truncated_at_120_chars():
    squamish = (49.7016, -123.1558)
    long_desc = "A" * 200
    advisory = _make_advisory("Alice Lake Provincial Park", 49.77, -123.12)
    advisory["description"] = long_desc

    with patch("fetchers.bcparks.httpx.get", return_value=_mock_response([advisory])):
        results = fetch_park_advisories(squamish)

    assert len(results[0].description) <= 120
    assert results[0].description.endswith("…")
