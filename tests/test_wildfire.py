from unittest.mock import MagicMock, patch

import pytest

import fetchers.wildfire as wf
from fetchers.wildfire import FireIncident, _haversine_km, _intersects_corridor, fetch_wildfire
from route_buffer import build_route_corridor, destination_buffer


def _make_feature(lat=49.73, lon=-123.13, soc="OUT_OF_CONTROL", size=50.0, name="Test Fire"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "GEOGRAPHIC_DESCRIPTION": name,
            "STAGE_OF_CONTROL": soc,
            "SIZE_HA": size,
        },
    }


def _mock_response(features: list) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"features": features}
    mock.raise_for_status.return_value = None
    return mock


# --- spatial filter: corridor intersection ---

def test_fire_intersecting_corridor_included():
    corridor = build_route_corridor((49.70, -123.15), (49.77, -123.12))
    dest = (49.77, -123.12)
    features = [_make_feature(lat=49.73, lon=-123.13)]  # inside corridor
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response(features)):
        results = fetch_wildfire(corridor, dest)
    assert len(results) == 1


def test_fire_outside_corridor_and_far_excluded():
    corridor = build_route_corridor((49.70, -123.15), (49.77, -123.12))
    dest = (49.77, -123.12)
    # Fire on Vancouver Island ~200km away
    features = [_make_feature(lat=49.0, lon=-125.5)]
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response(features)):
        results = fetch_wildfire(corridor, dest)
    assert results == []


# --- distance filter: within 25km ---

def test_fire_within_25km_of_destination_included():
    corridor = build_route_corridor((49.70, -123.15), (49.77, -123.12))
    dest = (49.77, -123.12)
    # Fire 10km east — outside corridor but within 25km
    features = [_make_feature(lat=49.77, lon=-122.98)]
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response(features)):
        results = fetch_wildfire(corridor, dest)
    assert len(results) == 1


def test_fire_beyond_25km_excluded():
    corridor = destination_buffer((49.77, -123.12), radius_km=5)
    dest = (49.77, -123.12)
    # Fire 50km away
    features = [_make_feature(lat=50.20, lon=-123.12)]
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response(features)):
        results = fetch_wildfire(corridor, dest)
    assert results == []


# --- empty result ---

def test_no_fires_returns_empty():
    corridor = destination_buffer((49.7, -123.1), radius_km=5)
    dest = (49.7, -123.1)
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response([])):
        results = fetch_wildfire(corridor, dest)
    assert results == []


def test_timeout_returns_empty():
    import httpx
    corridor = destination_buffer((49.7, -123.1), radius_km=5)
    dest = (49.7, -123.1)
    with patch("fetchers.wildfire.httpx.get", side_effect=httpx.TimeoutException("timed out")):
        results = fetch_wildfire(corridor, dest)
    assert results == []


# --- results sorted by distance ---

def test_results_sorted_by_distance():
    dest = (49.77, -123.12)
    corridor = build_route_corridor((49.70, -123.15), (49.77, -123.12))
    features = [
        _make_feature(lat=49.77, lon=-122.98, name="Fire Far"),   # ~10km
        _make_feature(lat=49.73, lon=-123.13, name="Fire Near"),  # ~5km
    ]
    with patch("fetchers.wildfire.httpx.get", return_value=_mock_response(features)):
        results = fetch_wildfire(corridor, dest)
    assert results[0].name == "Fire Near"


# --- haversine ---

def test_haversine_zero_distance():
    assert _haversine_km(49.7, -123.1, 49.7, -123.1) == 0.0


def test_haversine_known_distance():
    # Squamish to Whistler is ~48km as the crow flies
    dist = _haversine_km(49.7016, -123.1558, 50.1163, -122.9574)
    assert 44 < dist < 54
