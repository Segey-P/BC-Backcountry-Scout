import os
from unittest.mock import patch, MagicMock

import httpx
import pytest

from fetchers.eta import fetch_eta, ETAResult, clear_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


@patch("fetchers.eta.httpx.get")
@patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_key"})
def test_fetch_eta_success(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "status": "OK",
            "routes": [
                {
                    "legs": [
                        {
                            "duration": {"text": "1 hour 20 mins"},
                            "distance": {"text": "80 km"},
                            "duration_in_traffic": {"text": "1 hour 35 mins"},
                        }
                    ]
                }
            ],
        },
    )

    result = fetch_eta((49.7, -123.1), (50.1, -122.9))

    assert result == ETAResult(
        duration_text="1 hour 20 mins",
        duration_traffic_text="1 hour 35 mins",
        distance_text="80 km",
    )
    mock_get.assert_called_once()


@patch("fetchers.eta.httpx.get")
@patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_key"})
def test_fetch_eta_no_traffic(mock_get):
    mock_get.return_value = _mock_response(
        200,
        {
            "status": "OK",
            "routes": [
                {
                    "legs": [
                        {
                            "duration": {"text": "1 hour 20 mins"},
                            "distance": {"text": "80 km"},
                        }
                    ]
                }
            ],
        },
    )

    result = fetch_eta((49.7, -123.1), (50.1, -122.9))

    assert result.duration_traffic_text == "1 hour 20 mins"


@patch("fetchers.eta.httpx.get")
@patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_key"})
def test_fetch_eta_api_error(mock_get):
    mock_get.return_value = _mock_response(200, {"status": "ZERO_RESULTS"})
    result = fetch_eta((49.7, -123.1), (0, 0))
    assert result is None


@patch("fetchers.eta.httpx.get")
@patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_key"})
def test_fetch_eta_http_error(mock_get):
    mock_get.side_effect = httpx.HTTPError("Error")
    result = fetch_eta((49.7, -123.1), (50.1, -122.9))
    assert result is None


@patch.dict(os.environ, {}, clear=True)
def test_fetch_eta_no_api_key():
    # If key is missing from env, should return None without calling API
    result = fetch_eta((49.7, -123.1), (50.1, -122.9))
    assert result is None
