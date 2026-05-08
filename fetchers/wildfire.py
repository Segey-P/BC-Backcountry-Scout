from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import httpx
from shapely.geometry import shape, Point

logger = logging.getLogger(__name__)

_WILDFIRE_URL = (
    "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services"
    "/BCWS_ActiveFires_PublicView/FeatureServer/0/query"
    "?where=1%3D1&outFields=FIRE_NUMBER,GEOGRAPHIC_DESCRIPTION,STAGE_OF_CONTROL,SIZE_HA"
    "&f=geojson"
)
# Primary: BCWS ArcGIS REST — same host as wildfires, does server-side spatial filter
_FIREBANS_ARCGIS_BASE = (
    "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services"
    "/BCWS_FireBans_PublicView/FeatureServer/0/query"
)
# Fallback: DataBC WFS with server-side CQL point-in-polygon filter
_FIREBANS_WFS_BASE = (
    "https://openmaps.gov.bc.ca/geo/pub/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeName=pub:WHSE_LAND_AND_NATURAL_RESOURCE.PROT_BANS_AND_PROHIBITIONS_SP"
    "&outputFormat=json&srsName=EPSG:4326"
)
_TIMEOUT = 3.0
_FIREBANS_TIMEOUT = 10.0
_NEARBY_KM = 25


@dataclass
class FireIncident:
    name: str
    stage_of_control: str
    size_hectares: float | None
    geometry: dict  # GeoJSON
    distance_to_destination_km: float


@dataclass
class FireBan:
    description: str
    fire_centre: str
    bulletin_url: str
    category: str
    type: str


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


def _parse_ban_feature(props: dict) -> FireBan:
    return FireBan(
        description=props.get("ACCESS_PROHIBITION_DESCRIPTION") or props.get("PROHIBITION_DESCRIPTION") or "Unknown prohibition",
        fire_centre=props.get("FIRE_CENTRE_NAME") or props.get("FireCentreName") or "Unknown Centre",
        bulletin_url=props.get("BULLETIN_URL") or props.get("BulletinUrl") or "https://www2.gov.bc.ca/gov/content/safety/wildfire-status/fire-bans-and-prohibitions",
        category=props.get("CATEGORY") or props.get("Category") or "N/A",
        type=props.get("TYPE") or props.get("Type") or "Restriction",
    )


def _fetch_fire_bans_arcgis(lat: float, lon: float) -> list[FireBan] | None:
    """Query BCWS ArcGIS with server-side point-in-polygon filter. Returns None on failure."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "geojson",
    }
    try:
        response = httpx.get(_FIREBANS_ARCGIS_BASE, params=params, timeout=_FIREBANS_TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features") or []
        return [_parse_ban_feature(f.get("properties") or {}) for f in features if f.get("properties")]
    except Exception as exc:
        logger.warning("fire_bans ArcGIS fetch failed: %s", exc)
        return None


def _fetch_fire_bans_wfs(lat: float, lon: float) -> list[FireBan]:
    """Fallback: DataBC WFS with server-side CQL point filter."""
    cql = f"CONTAINS(SHAPE,POINT({lon} {lat}))"
    try:
        response = httpx.get(
            _FIREBANS_WFS_BASE,
            params={"CQL_FILTER": cql},
            timeout=_FIREBANS_TIMEOUT,
        )
        response.raise_for_status()
        features = response.json().get("features") or []
        bans = []
        for feature in features:
            geom = feature.get("geometry")
            props = feature.get("properties") or {}
            if not geom:
                continue
            try:
                if shape(geom).contains(Point(lon, lat)):
                    bans.append(_parse_ban_feature(props))
            except Exception:
                continue
        return bans
    except Exception as exc:
        logger.warning("fire_bans WFS fetch failed: %s", exc)
        return []


def fetch_fire_bans(destination: tuple[float, float]) -> list[FireBan]:
    """Return active fire bans/restrictions covering the destination point."""
    lat, lon = destination
    result = _fetch_fire_bans_arcgis(lat, lon)
    if result is None:
        result = _fetch_fire_bans_wfs(lat, lon)
    return result
