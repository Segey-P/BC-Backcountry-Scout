from unittest.mock import MagicMock, patch

import pytest

from fetchers.aqhi import (
    AirQualityReport,
    aqhi_level,
    calculate_aqhi,
    clear_cache,
    fetch_air_quality,
)


@pytest.fixture(autouse=True)
def _clear_aqhi_cache():
    """Clear AQHI cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


def test_calculate_aqhi_valid():
    """Test AQHI calculation with typical summer values."""
    aqhi = calculate_aqhi(pm25=20.0, no2_ug=25.0, o3_ug=40.0)
    assert aqhi is not None
    assert 9 < aqhi < 12


def test_calculate_aqhi_missing_pm25():
    """Returns None if PM2.5 is missing."""
    aqhi = calculate_aqhi(pm25=None, no2_ug=25.0, o3_ug=40.0)
    assert aqhi is None


def test_calculate_aqhi_missing_no2():
    """Returns None if NO2 is missing."""
    aqhi = calculate_aqhi(pm25=20.0, no2_ug=None, o3_ug=40.0)
    assert aqhi is None


def test_calculate_aqhi_missing_o3():
    """Returns None if O3 is missing."""
    aqhi = calculate_aqhi(pm25=20.0, no2_ug=25.0, o3_ug=None)
    assert aqhi is None


def test_aqhi_level_good():
    """Good air quality (AQHI 1-3)."""
    label, emoji, color = aqhi_level(1.5)
    assert label == "Good"
    assert emoji == "🟢"
    assert color == "#00dd00"


def test_aqhi_level_moderate():
    """Moderate air quality (AQHI 4-6)."""
    label, emoji, color = aqhi_level(5.0)
    assert label == "Moderate"
    assert emoji == "🟡"


def test_aqhi_level_poor():
    """Poor air quality (AQHI 7-10)."""
    label, emoji, color = aqhi_level(8.5)
    assert label == "Poor"
    assert emoji == "🟠"


def test_aqhi_level_high():
    """High air quality (AQHI 11-15)."""
    label, emoji, color = aqhi_level(12.0)
    assert label == "High"
    assert emoji == "🔴"


def test_aqhi_level_very_high():
    """Very high air quality (AQHI 16+)."""
    label, emoji, color = aqhi_level(18.0)
    assert label == "Very High"
    assert emoji == "🟣"


def test_aqhi_level_unknown():
    """Unknown air quality (None input)."""
    label, emoji, color = aqhi_level(None)
    assert label == "Unknown"
    assert emoji == "❓"


def test_aqhi_level_boundary_3_4():
    """Boundary between Good and Moderate."""
    label_good, _, _ = aqhi_level(3.9)
    label_moderate, _, _ = aqhi_level(4.0)
    assert label_good == "Good"
    assert label_moderate == "Moderate"


def test_fetch_air_quality_timeout():
    """Timeout returns None values."""
    import httpx

    with patch("fetchers.aqhi.httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = fetch_air_quality(49.7, -123.1)

    assert result.aqhi is None
    assert result.pm25 is None
    assert result.level == "Unknown"


def test_fetch_air_quality_http_error():
    """HTTP error returns None values gracefully."""
    import httpx

    with patch("fetchers.aqhi.httpx.get", side_effect=httpx.HTTPError("error")):
        result = fetch_air_quality(49.7, -123.1)

    assert result.aqhi is None
    assert result.level == "Unknown"


def test_fetch_air_quality_success():
    """Successful API call returns parsed data."""
    mock = MagicMock()
    mock.json.return_value = {
        "current": {
            "pm2_5": 25.0,
            "nitrogen_dioxide": 30.0,
            "ozone": 50.0,
        }
    }
    mock.raise_for_status.return_value = None

    with patch("fetchers.aqhi.httpx.get", return_value=mock):
        result = fetch_air_quality(49.7, -123.1)

    assert result.pm25 == 25.0
    assert result.no2 == 30.0
    assert result.o3 == 50.0
    assert result.aqhi is not None
    assert 11 < result.aqhi < 15
    assert result.level in ("High", "Very High")  # With these values


def test_fetch_air_quality_cache():
    """Verify cache works within TTL (5 minutes)."""
    mock = MagicMock()
    mock.json.return_value = {
        "current": {"pm2_5": 10.0, "nitrogen_dioxide": 20.0, "ozone": 30.0}
    }
    mock.raise_for_status.return_value = None

    with patch("fetchers.aqhi.httpx.get", return_value=mock) as mock_get:
        # First call
        result1 = fetch_air_quality(49.7, -123.1)
        # Second call (should use cache)
        result2 = fetch_air_quality(49.7, -123.1)

    assert mock_get.call_count == 1, "Second call should use cache"
    assert result2.aqhi == result1.aqhi


def test_fetch_air_quality_cache_different_coords():
    """Different coordinates bypass cache."""
    mock = MagicMock()
    mock.json.return_value = {
        "current": {"pm2_5": 10.0, "nitrogen_dioxide": 20.0, "ozone": 30.0}
    }
    mock.raise_for_status.return_value = None

    with patch("fetchers.aqhi.httpx.get", return_value=mock) as mock_get:
        fetch_air_quality(49.7, -123.1)  # First location
        fetch_air_quality(50.0, -122.0)  # Different location

    assert mock_get.call_count == 2, "Different coords should bypass cache"
