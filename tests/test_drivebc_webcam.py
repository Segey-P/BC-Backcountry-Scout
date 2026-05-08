from unittest.mock import MagicMock, patch

import pytest

from fetchers.drivebc_webcam import Webcam, clear_cache, fetch_nearest_webcam


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


def _make_cam_feature(lon, lat, cam_id="cam001", name="Hwy 99 at Squamish"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "CAM_ID": cam_id,
            "CAM_NAME": name,
            "HIGHWAY_DESCRIPTION": "Hwy 99",
            "IMAGE_URL": f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id}/latest/image.jpg",
            "CAM_URL": f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id}.html",
        },
    }


def _mock_wfs(features):
    mock = MagicMock()
    mock.json.return_value = {"features": features}
    mock.raise_for_status.return_value = None
    return mock


def test_nearest_webcam_within_range():
    squamish = (49.7016, -123.1558)
    features = [_make_cam_feature(-123.14, 49.70, "cam1", "Hwy 99 South Squamish")]

    with patch("fetchers.drivebc_webcam.httpx.get", return_value=_mock_wfs(features)):
        result = fetch_nearest_webcam(squamish, max_distance_km=30)

    assert result is not None
    assert "Squamish" in result.name
    assert result.distance_km < 5


def test_nearest_webcam_too_far():
    squamish = (49.7016, -123.1558)
    features = [_make_cam_feature(-120.0, 51.5, "cam2", "Hwy 1 Cache Creek")]

    with patch("fetchers.drivebc_webcam.httpx.get", return_value=_mock_wfs(features)):
        result = fetch_nearest_webcam(squamish, max_distance_km=30)

    assert result is None


def test_nearest_webcam_picks_closest():
    squamish = (49.7016, -123.1558)
    features = [
        _make_cam_feature(-123.14, 49.70, "cam1", "Near Squamish"),   # ~2km away
        _make_cam_feature(-123.30, 50.10, "cam2", "Far North"),         # ~50km away
    ]

    with patch("fetchers.drivebc_webcam.httpx.get", return_value=_mock_wfs(features)):
        result = fetch_nearest_webcam(squamish, max_distance_km=30)

    assert result is not None
    assert "Near Squamish" in result.name


def test_nearest_webcam_api_failure_returns_none():
    import httpx

    squamish = (49.7016, -123.1558)
    with patch("fetchers.drivebc_webcam.httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = fetch_nearest_webcam(squamish)

    assert result is None


def test_webcam_image_url_built_from_id():
    squamish = (49.7016, -123.1558)
    features = [_make_cam_feature(-123.14, 49.70, "cam99", "Test Cam")]

    with patch("fetchers.drivebc_webcam.httpx.get", return_value=_mock_wfs(features)):
        result = fetch_nearest_webcam(squamish)

    assert result is not None
    assert "cam99" in result.image_url
    assert result.image_url.startswith("https://")
