from shapely.geometry import Point, LineString, Polygon
from pyproj import Proj, Transformer

BC_ALBERS = "EPSG:3005"  # BC Albers projection
WGS84 = "EPSG:4326"      # Latitude/longitude

_ROUTE_CORRIDOR_BUFFER_KM = 5
_DESTINATION_DEFAULT_RADIUS_KM = 25


def build_route_corridor(
    start: tuple[float, float],
    destination: tuple[float, float],
) -> Polygon:
    """Build a 5km buffer polygon around the route from start to destination.

    Args:
        start: (lat, lon)
        destination: (lat, lon)

    Returns:
        Polygon in WGS84 coordinates (lat/lon)
    """
    transformer = Transformer.from_crs(WGS84, BC_ALBERS, always_xy=True)
    transformer_back = Transformer.from_crs(BC_ALBERS, WGS84, always_xy=True)

    coords = [(start[1], start[0]), (destination[1], destination[0])]
    xs, ys = transformer.transform(*zip(*coords))
    line_proj = LineString(list(zip(xs, ys)))

    buffered = line_proj.buffer(_ROUTE_CORRIDOR_BUFFER_KM * 1000)

    lons, lats = transformer_back.transform(*zip(*buffered.exterior.coords))
    exterior_coords = list(zip(lons, lats))

    interior_coords = []
    if buffered.interiors:
        for interior in buffered.interiors:
            lons_int, lats_int = transformer_back.transform(*zip(*interior.coords))
            interior_coords.append(list(zip(lons_int, lats_int)))

    if interior_coords:
        return Polygon(exterior_coords, holes=interior_coords)
    return Polygon(exterior_coords)


def destination_buffer(
    destination: tuple[float, float],
    radius_km: float = _DESTINATION_DEFAULT_RADIUS_KM,
) -> Polygon:
    """Build a circular buffer polygon around a destination point.

    Args:
        destination: (lat, lon)
        radius_km: radius in kilometers

    Returns:
        Polygon in WGS84 coordinates (lat/lon)
    """
    transformer = Transformer.from_crs(WGS84, BC_ALBERS, always_xy=True)
    transformer_back = Transformer.from_crs(BC_ALBERS, WGS84, always_xy=True)

    lon, lat = transformer.transform(destination[1], destination[0])
    point_proj = Point(lon, lat)
    buffered = point_proj.buffer(radius_km * 1000)

    coords = list(buffered.exterior.coords)
    lons, lats = transformer_back.transform(*zip(*coords))
    exterior_coords = list(zip(lons, lats))

    return Polygon(exterior_coords)
