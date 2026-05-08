#!/usr/bin/env python3
"""
Fetch DriveBC highway webcam data and save to data/webcams.json.

Run this from GitHub Actions or any machine that can reach BC government servers.
Oracle Cloud IPs are blocked by all *.gov.bc.ca and *.drivebc.ca endpoints.

Usage:
    python scripts/fetch_webcams.py

Output: data/webcams.json with camera name, lat, lon, image_url, page_url.
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

_OUT = Path(__file__).parent.parent / "data" / "webcams.json"

# DriveBC REST API (used by the drivebc.ca website)
_DRIVEBC_URLS = [
    "https://www.drivebc.ca/api/webcams/?format=json",
    "https://www.drivebc.ca/api/webcams/",
    "https://www.drivebc.ca/api/v1/webcams/",
    "https://drivebc.ca/api/webcams/",
]

# DataBC WFS — try multiple parameter combinations
_WFS_BASE = "https://openmaps.gov.bc.ca/geo/pub/wfs"
_WFS_VARIANTS = [
    # WFS 1.1.0 with pub: prefix
    f"{_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=pub:WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP&outputFormat=application/json&maxFeatures=2000",
    # WFS 1.1.0 without pub: prefix
    f"{_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP&outputFormat=application/json&maxFeatures=2000",
    # WFS 2.0.0 with count
    f"{_WFS_BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName=pub:WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP&outputFormat=application/json&count=2000",
    # WFS 2.0.0 json (not application/json)
    f"{_WFS_BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName=pub:WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP&outputFormat=json&count=2000",
]

# Open511 (kept as last resort — endpoint may have moved)
_OPEN511_URLS = [
    "https://api.open511.gov.bc.ca/webcams",
    "https://api.open511.gov.bc.ca/cameras",
    "https://api.open511.gov.bc.ca/webcam",
]


def _try_get(url: str, timeout: float = 30) -> httpx.Response | None:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "BCBackcountryScout/1.0"})
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"    {url} → {e}")
        return None


def _parse_drivebc(data: dict) -> list[dict]:
    results = []
    cameras = data.get("webcams") or data.get("results") or data.get("cameras") or []
    if not cameras and isinstance(data, list):
        cameras = data
    for cam in cameras:
        loc = cam.get("location") or cam.get("coordinates") or {}
        if isinstance(loc, dict):
            coords = loc.get("coordinates")
        else:
            coords = None
        if not coords and "longitude" in cam:
            coords = [cam["longitude"], cam["latitude"]]
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        cam_id = str(cam.get("id", cam.get("cam_id", "")))
        name = cam.get("name", cam.get("cam_name", "BC Highway Webcam"))
        image_url = (cam.get("url") or cam.get("image_url") or
            (f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id}/latest/image.jpg" if cam_id else ""))
        page_url = (cam.get("page_url") or
            (f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id}.html" if cam_id else ""))
        results.append({"name": name, "lat": lat, "lon": lon, "image_url": image_url, "page_url": page_url})
    return results


def _parse_wfs(data: dict) -> list[dict]:
    results = []
    for feat in data.get("features") or []:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        cam_id = str(props.get("CAM_ID") or props.get("CAM_NAME") or "")
        name = props.get("CAM_NAME") or "BC Highway Webcam"
        highway = props.get("HIGHWAY_DESCRIPTION") or ""
        if highway and highway not in name:
            name = f"{name} ({highway})"
        cam_id_safe = quote(cam_id, safe="") if cam_id else ""
        image_url = props.get("IMAGE_URL") or (
            f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id_safe}/latest/image.jpg"
            if cam_id_safe else "")
        page_url = props.get("CAM_URL") or (
            f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id_safe}.html" if cam_id_safe else "")
        results.append({"name": name, "lat": lat, "lon": lon, "image_url": image_url, "page_url": page_url})
    return results


def _parse_open511(data: dict) -> list[dict]:
    results = []
    for cam in data.get("webcams") or data.get("cameras") or []:
        loc = cam.get("location") or {}
        coords = loc.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        cam_id = str(cam.get("id", ""))
        name = cam.get("name", "BC Highway Webcam")
        image_url = cam.get("url") or (
            f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id}/latest/image.jpg" if cam_id else "")
        page_url = f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id}.html" if cam_id else ""
        results.append({"name": name, "lat": lat, "lon": lon, "image_url": image_url, "page_url": page_url})
    return results


def main():
    cameras = []

    print("Trying DriveBC REST API...")
    for url in _DRIVEBC_URLS:
        r = _try_get(url)
        if r:
            try:
                cameras = _parse_drivebc(r.json())
                if cameras:
                    print(f"  Got {len(cameras)} cameras from {url}")
                    break
            except Exception as e:
                print(f"    parse error: {e}")

    if not cameras:
        print("Trying DataBC WFS...")
        for url in _WFS_VARIANTS:
            r = _try_get(url, timeout=60)
            if r:
                try:
                    cameras = _parse_wfs(r.json())
                    if cameras:
                        print(f"  Got {len(cameras)} cameras from WFS")
                        break
                except Exception as e:
                    print(f"    parse error: {e}")

    if not cameras:
        print("Trying Open511...")
        for url in _OPEN511_URLS:
            r = _try_get(url)
            if r:
                try:
                    cameras = _parse_open511(r.json())
                    if cameras:
                        print(f"  Got {len(cameras)} cameras from {url}")
                        break
                except Exception as e:
                    print(f"    parse error: {e}")

    if not cameras:
        print("ERROR: All sources failed.")
        print("  Check that the runner can reach *.drivebc.ca and *.gov.bc.ca")
        sys.exit(1)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved {len(cameras)} cameras to {_OUT}")


if __name__ == "__main__":
    main()
