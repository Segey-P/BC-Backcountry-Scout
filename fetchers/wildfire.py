from __future__ import annotations

import math
from dataclasses import dataclass

import httpx
from shapely.geometry import shape, Point

_WILDFIRE_URL = (
    "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services"
    "/BCWS_ActiveFires_PublicView/FeatureServer/0/query"
    "?where=1%3D1&outFields=FIRE_NUMBER,GEOGRAPHIC_DESCRIPTION,STAGE_OF_CONTROL,SIZE_HA"
    "&f=geojson"
)
_FIREBANS_URL = (
    "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services"
    "/BCWS_FireRestrictions_and_Bans_PublicView/FeatureServer/0/query"
    "?where=1%3D1&outFields=ACCESS_PROHIBITION_DESCRIPTION,FIRE_CENTRE_NAME"
    "&f=geojson"
)
_TIMEOUT = 3.0
_NEARBY_KM = 25


@dataclass
class FireIncident:
    name: str
    stage_of_control: str
    size_hectares: float | None
    geometry: dict  # GeoJSON
    distance_to_destination_km: float


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _centroid_latlon(geojson_geom: dict) -> tuple[float, float] | None:
    try:
        geom = shape(geojson_geom)
        c = geom.centroid
        return c.y, c.x  # lat, lon
    except Exception:
        return None


def _distance_to_destination(geojson_geom: dict, dest: tuple[float, float]) -> float:
    latlon = _centroid_latlon(geojson_geom)
    if not latlon:
        return float("inf")
    return _haversine_km(latlon[0], latlon[1], dest[0], dest[1])


def _intersects_corridor(geojson_geom: dict, corridor) -> bool:
    try:
        return corridor.intersects(shape(geojson_geom))
    except Exception:
        return False


def _parse_incident(feature: dict, destination: tuple[float, float]) -> FireIncident | None:
    props = feature.get("properties") or {}
    geom = feature.get("geometry")
    if not geom:
        return None
    name = props.get("GEOGRAPHIC_DESCRIPTION") or props.get("FIRE_NUMBER") or "Unknown fire"
    return FireIncident(
        name=name,
        stage_of_control=props.get("STAGE_OF_CONTROL") or "UNKNOWN",
        size_hectares=props.get("SIZE_HA"),
        geometry=geom,
        distance_to_destination_km=_distance_to_destination(geom, destination),
    )


def fetch_wildfire(
    corridor_polygon,
    destination: tuple[float, float],
) -> list[FireIncident]:
    try:
        response = httpx.get(_WILDFIRE_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features") or []
    except (httpx.TimeoutException, httpx.HTTPError):
        return []

    results = []
    for feature in features:
        geom = feature.get("geometry")
        if not geom:
            continue
        dist = _distance_to_destination(geom, destination)
        if _intersects_corridor(geom, corridor_polygon) or dist <= _NEARBY_KM:
            incident = _parse_incident(feature, destination)
            if incident:
                results.append(incident)

    results.sort(key=lambda f: f.distance_to_destination_km)
    return results


def fetch_fire_bans(destination: tuple[float, float]) -> list[str]:
    """Return active fire restriction/ban descriptions near the destination."""
    try:
        response = httpx.get(_FIREBANS_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features") or []
    except (httpx.TimeoutException, httpx.HTTPError):
        return []

    bans = []
    for feature in features:
        geom = feature.get("geometry")
        props = feature.get("properties") or {}
        if not geom:
            continue
        try:
            if shape(geom).contains(Point(destination[1], destination[0])):
                desc = props.get("ACCESS_PROHIBITION_DESCRIPTION") or ""
                if desc:
                    bans.append(desc)
        except Exception:
            continue
    return bans
