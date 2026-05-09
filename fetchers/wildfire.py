from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import httpx
from shapely.geometry import shape, Point
from datetime import date, datetime

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
<<<<<<< Updated upstream
_TIMEOUT = 3.0
_FIREBANS_TIMEOUT = 10.0
=======
_FIRE_CENTRES_URL = (
    "https://openmaps.gov.bc.ca/geo/pub/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeName=pub:WHSE_LEGAL_ADMIN_BOUNDARIES.DRP_MOF_FIRE_CENTRES_SP"
    "&outputFormat=json&srsName=EPSG:4326"
)
_TIMEOUT = 5.0
>>>>>>> Stashed changes
_NEARBY_KM = 25

# Global cache for Fire Centre polygons
_FIRE_CENTRES_CACHE = []

def _load_fire_centres():
    global _FIRE_CENTRES_CACHE
    if _FIRE_CENTRES_CACHE:
        return _FIRE_CENTRES_CACHE
    try:
        response = httpx.get(_FIRE_CENTRES_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features") or []
        for f in features:
            geom = f.get("geometry")
            name = f.get("properties", {}).get("MOF_FIRE_CENTRE_NAME")
            if geom and name:
                _FIRE_CENTRES_CACHE.append({"name": name, "shape": shape(geom)})
    except Exception:
        pass
    return _FIRE_CENTRES_CACHE

def _get_fire_centre_for_point(lat: float, lon: float) -> str | None:
    p = Point(lon, lat)
    for fc in _load_fire_centres():
        if fc["shape"].intersects(p):
            return fc["name"]
    return None

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
# ... (keeping existing _haversine_km, _centroid_latlon, _distance_to_destination, _intersects_corridor, _parse_incident, fetch_wildfire unchanged)
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


<<<<<<< Updated upstream
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
=======
def fetch_fire_bans(destination: tuple[float, float]) -> list[FireBan]:
    """Return active fire restriction/ban details for the destination."""
    dest_lat, dest_lon = destination
    dest_point = Point(dest_lon, dest_lat)
    
    # Identify destination's fire centre to match centre-wide bans
    dest_fire_centre = _get_fire_centre_for_point(dest_lat, dest_lon)
    
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream

def fetch_fire_bans(destination: tuple[float, float]) -> list[FireBan]:
    """Return active fire bans/restrictions covering the destination point."""
    lat, lon = destination
    result = _fetch_fire_bans_arcgis(lat, lon)
    if result is None:
        result = _fetch_fire_bans_wfs(lat, lon)
    return result
=======
    today = date.today()
    bans = []
    for feature in features:
        geom = feature.get("geometry")
        props = feature.get("properties") or {}
        if not geom:
            continue
            
        # 1. Check if ban is already effective
        eff_date_str = props.get("ACCESS_STATUS_EFFECTIVE_DATE")
        if eff_date_str:
            try:
                # Format: 2026-05-07Z or 2026-05-07
                date_part = eff_date_str.split("T")[0].split("Z")[0]
                eff_date = datetime.strptime(date_part, "%Y-%m-%d").date()
                if eff_date > today:
                    continue
            except (ValueError, IndexError):
                pass

        # 2. Match logic
        is_spatial_match = False
        try:
            ban_shape = shape(geom)
            is_spatial_match = ban_shape.intersects(dest_point)
        except Exception:
            pass
            
        ban_centre = props.get("FIRE_CENTRE_NAME") or ""
        # Handle cases where names might slightly differ (e.g. "Coastal" vs "Coastal Fire Centre")
        is_centre_match = False
        if dest_fire_centre and ban_centre:
            if ban_centre.lower() in dest_fire_centre.lower() or dest_fire_centre.lower() in ban_centre.lower():
                # For centre-wide match, we also check if it's a "Full Prohibition" 
                # or if the user mentioned it specifically.
                if props.get("TYPE") == "Full Prohibition":
                    is_centre_match = True

        if is_spatial_match or is_centre_match:
            bans.append(FireBan(
                description=props.get("ACCESS_PROHIBITION_DESCRIPTION") or "Unknown prohibition",
                fire_centre=ban_centre or "Unknown Centre",
                bulletin_url=props.get("BULLETIN_URL") or "https://bcwildfire.ca",
                category=props.get("CATEGORY") or "N/A",
                type=props.get("TYPE") or "Restriction",
            ))
            
    return bans
>>>>>>> Stashed changes
