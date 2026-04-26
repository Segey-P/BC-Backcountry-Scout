import math

import pytest
from shapely.geometry import Point

import route_buffer as rb


def test_build_route_corridor_returns_polygon():
    start = (49.7, -123.1)
    destination = (49.8, -123.2)
    corridor = rb.build_route_corridor(start, destination)
    assert corridor.is_valid
    assert corridor.geom_type == "Polygon"


def test_build_route_corridor_contains_points():
    start = (49.7, -123.1)
    destination = (49.8, -123.2)
    corridor = rb.build_route_corridor(start, destination)
    assert corridor.contains(Point(start[1], start[0]))
    assert corridor.contains(Point(destination[1], destination[0]))


def test_destination_buffer_returns_polygon():
    destination = (49.7, -123.1)
    buffer = rb.destination_buffer(destination, radius_km=25)
    assert buffer.is_valid
    assert buffer.geom_type == "Polygon"


def test_destination_buffer_contains_destination():
    destination = (49.7, -123.1)
    buffer = rb.destination_buffer(destination, radius_km=25)
    assert buffer.contains(Point(destination[1], destination[0]))


def test_destination_buffer_area_scales_with_radius():
    destination = (49.7, -123.1)
    buffer_10km = rb.destination_buffer(destination, radius_km=10)
    buffer_20km = rb.destination_buffer(destination, radius_km=20)

    area_10 = buffer_10km.area
    area_20 = buffer_20km.area

    area_ratio = area_20 / area_10
    expected_ratio = (20 / 10) ** 2  # area scales with radius squared

    assert 3.5 < area_ratio < 4.5  # allow some latitude for projection distortion


def test_destination_buffer_default_radius():
    destination = (49.7, -123.1)
    buffer = rb.destination_buffer(destination)  # default 25 km
    assert buffer.is_valid


def test_same_start_and_destination_creates_buffer():
    point = (49.7, -123.1)
    corridor = rb.build_route_corridor(point, point)
    assert corridor.is_valid
    assert corridor.contains(Point(point[1], point[0]))


def test_corridor_area_increases_with_distance():
    start = (49.7, -123.1)
    destination_near = (49.71, -123.11)
    destination_far = (49.8, -123.2)

    corridor_near = rb.build_route_corridor(start, destination_near)
    corridor_far = rb.build_route_corridor(start, destination_far)

    assert corridor_far.area > corridor_near.area


def test_projection_consistency():
    start = (49.7, -123.1)
    destination = (49.8, -123.2)
    buffer = rb.destination_buffer(start, radius_km=10)

    assert buffer.is_valid
    point = Point(start[1], start[0])
    assert buffer.contains(point)
