#!/usr/bin/env python3
"""
Fetch DriveBC highway webcam data and save to data/webcams.json.

Run this from any machine that can reach api.open511.gov.bc.ca
(e.g. GitHub Actions, your laptop — NOT Oracle Cloud which is blocked).

Usage:
    python scripts/fetch_webcams.py

Output: data/webcams.json with camera name, lat, lon, image_url, page_url.
"""

import json
import sys
from pathlib import Path

import httpx

_OPEN511_URL = "https://api.open511.gov.bc.ca/webcams"
_WFS_URL = (
    "https://openmaps.gov.bc.ca/geo/pub/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeName=pub:WHSE_IMAGERY_AND_BASE_MAPS.HWAY_WEBCAM_IMAGERY_SP"
    "&outputFormat=json&srsName=EPSG:4326"
)
_OUT = Path(__file__).parent.parent / "data" / "webcams.json"


def _fetch_open511() -> list[dict]:
    resp = httpx.get(_OPEN511_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    cameras = data.get("webcams") or []
    results = []
    for cam in cameras:
        loc = cam.get("location") or {}
        coords = loc.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        cam_id = str(cam.get("id", ""))
        name = cam.get("name", "BC Highway Webcam")
        image_url = cam.get("url") or (
            f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id}/latest/image.jpg"
            if cam_id else ""
        )
        page_url = f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id}.html" if cam_id else ""
        results.append({"name": name, "lat": lat, "lon": lon, "image_url": image_url, "page_url": page_url})
    return results


def _fetch_wfs() -> list[dict]:
    from urllib.parse import quote
    resp = httpx.get(_WFS_URL, timeout=60)
    resp.raise_for_status()
    features = resp.json().get("features") or []
    results = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        cam_id = props.get("CAM_ID") or props.get("CAM_NAME") or ""
        name = props.get("CAM_NAME") or "BC Highway Webcam"
        highway = props.get("HIGHWAY_DESCRIPTION") or ""
        if highway and highway not in name:
            name = f"{name} ({highway})"
        cam_id_safe = quote(str(cam_id), safe="") if cam_id else ""
        image_url = props.get("IMAGE_URL") or (
            f"https://images.drivebc.ca/bchighwaycam/pub/cameras/{cam_id_safe}/latest/image.jpg"
            if cam_id_safe else ""
        )
        page_url = props.get("CAM_URL") or (
            f"https://www.drivebc.ca/mobile/pub/webcam/id/{cam_id_safe}.html" if cam_id_safe else ""
        )
        results.append({"name": name, "lat": lat, "lon": lon, "image_url": image_url, "page_url": page_url})
    return results


def main():
    cameras = []

    print("Trying Open511 API...")
    try:
        cameras = _fetch_open511()
        print(f"  Got {len(cameras)} cameras from Open511")
    except Exception as e:
        print(f"  Open511 failed: {e}")

    if not cameras:
        print("Trying DataBC WFS...")
        try:
            cameras = _fetch_wfs()
            print(f"  Got {len(cameras)} cameras from WFS")
        except Exception as e:
            print(f"  WFS failed: {e}")

    if not cameras:
        print("ERROR: Both sources failed. Are you running from a network that can reach BC government APIs?")
        sys.exit(1)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved {len(cameras)} cameras to {_OUT}")


if __name__ == "__main__":
    main()
