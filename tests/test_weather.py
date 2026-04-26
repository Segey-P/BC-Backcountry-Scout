from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from fetchers.weather import WeatherReport, fetch_weather


def _mock_response(data: dict) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    mock.status_code = 200
    return mock


_SAMPLE_OPEN_METEO = {
    "current_weather": {
        "temperature": 12.5,
        "windspeed": 8.3,
        "time": "2026-04-25T14:00",
    },
    "hourly": {
        "time": [f"2026-04-25T{h:02d}:00" for h in range(24)],
        "temperature_2m": [10.0 + i * 0.1 for i in range(24)],
        "windspeed_10m": [5.0 + i * 0.2 for i in range(24)],
        "precipitation": [0.0] * 12 + [1.5] * 12,
        "freezinglevel_height": [1800.0] * 24,
    },
}


# --- structure ---

def test_report_has_all_fields():
    with patch("fetchers.weather.httpx.get", return_value=_mock_response(_SAMPLE_OPEN_METEO)):
        with patch("fetchers.weather._fetch_ec_alerts", return_value=[]):
            report = fetch_weather(49.7016, -123.1558)
    assert isinstance(report, WeatherReport)
    assert report.current_temp == 12.5
    assert report.current_wind == 8.3
    assert isinstance(report.forecast_24h, list)
    assert len(report.forecast_24h) == 24
    assert report.freezing_level == 1800.0
    assert isinstance(report.alerts, list)
    assert report.timestamp == "2026-04-25T14:00"


def test_forecast_24h_structure():
    with patch("fetchers.weather.httpx.get", return_value=_mock_response(_SAMPLE_OPEN_METEO)):
        with patch("fetchers.weather._fetch_ec_alerts", return_value=[]):
            report = fetch_weather(49.7016, -123.1558)
    first = report.forecast_24h[0]
    assert "time" in first
    assert "temp" in first
    assert "wind" in first
    assert "precip" in first
    assert "freezing_level" in first


# --- timeout handling ---

def test_timeout_returns_empty_report():
    with patch("fetchers.weather.httpx.get", side_effect=httpx.TimeoutException("timed out")):
        report = fetch_weather(49.7016, -123.1558)
    assert report.current_temp is None
    assert report.forecast_24h == []
    assert report.alerts == []
    assert report.timestamp is not None  # always set


def test_http_error_returns_empty_report():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    with patch("fetchers.weather.httpx.get", return_value=mock_resp):
        report = fetch_weather(49.7016, -123.1558)
    assert report.current_temp is None


# --- missing / null data ---

def test_missing_hourly_fields_handled():
    data = {
        "current_weather": {"temperature": 5.0, "windspeed": None, "time": "2026-04-25T10:00"},
        "hourly": {},  # all fields missing
    }
    with patch("fetchers.weather.httpx.get", return_value=_mock_response(data)):
        with patch("fetchers.weather._fetch_ec_alerts", return_value=[]):
            report = fetch_weather(49.7016, -123.1558)
    assert report.current_temp == 5.0
    assert report.current_wind is None
    assert report.forecast_24h == []
    assert report.freezing_level is None


def test_null_current_weather_handled():
    data = {"current_weather": None, "hourly": {}}
    with patch("fetchers.weather.httpx.get", return_value=_mock_response(data)):
        with patch("fetchers.weather._fetch_ec_alerts", return_value=[]):
            report = fetch_weather(49.7016, -123.1558)
    assert report.current_temp is None


def test_partial_hourly_data():
    data = {
        "current_weather": {"temperature": 8.0, "windspeed": 5.0, "time": "2026-04-25T10:00"},
        "hourly": {
            "time": ["2026-04-25T10:00", "2026-04-25T11:00"],
            "temperature_2m": [8.0, 9.0],
            "windspeed_10m": [5.0, 6.0],
            "precipitation": [0.0, 0.5],
            "freezinglevel_height": [2000.0, 2100.0],
        },
    }
    with patch("fetchers.weather.httpx.get", return_value=_mock_response(data)):
        with patch("fetchers.weather._fetch_ec_alerts", return_value=[]):
            report = fetch_weather(49.7016, -123.1558)
    assert len(report.forecast_24h) == 2
