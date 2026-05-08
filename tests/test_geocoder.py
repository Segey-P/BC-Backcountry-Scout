import pytest

import geocoder as gc
from geocoder import GeoResult, SQUAMISH_DEFAULT, _haversine_km


# --- Google results used when returned ---

def test_google_result_returned(monkeypatch):
    google_hit = GeoResult("Watersprite Lake", 50.0412, -123.1284, "google")
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [google_hit])
    results = gc.geocode_destination("Watersprite Lake")
    assert any(r.source == "google" for r in results)


def test_google_result_out_of_bc_filtered(monkeypatch):
    # Google result outside BC bounding box should already be filtered in _google_maps_lookup,
    # but if it slips through, fuzzy fallback should dominate
    outside_bc = GeoResult("Seattle", 47.6062, -122.3321, "google")
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [outside_bc])
    results = gc.geocode_destination("Seattle Washington")
    assert all(r.lat >= gc._BC_LAT_MIN for r in results)


# --- distance sorting ---

def test_distance_sorting(monkeypatch):
    far = GeoResult("Test Spot Alpha", 51.5, -120.0, "google")    # ~250 km from Squamish
    close = GeoResult("Test Spot Beta", 49.72, -123.15, "google")  # ~2 km from Squamish
    mid = GeoResult("Test Spot Gamma", 50.1, -122.9, "google")    # ~45 km from Squamish

    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [far, close, mid])
    results = gc.geocode_destination("test spot", bias_point=SQUAMISH_DEFAULT)

    assert results[0].name == "Test Spot Beta"
    assert results[-1].name == "Test Spot Alpha"


def test_distance_sorting_closer_wins(monkeypatch):
    equidistant_a = GeoResult("Place A", 50.0, -123.5, "google")
    equidistant_b = GeoResult("Place B", 50.0, -122.7, "google")
    closer = GeoResult("Place C", 49.75, -123.16, "google")

    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [equidistant_a, equidistant_b, closer])
    results = gc.geocode_destination("place", bias_point=SQUAMISH_DEFAULT)

    assert results[0].name == "Place C"


# --- deduplication ---

def test_deduplication_removes_same_location(monkeypatch):
    dup1 = GeoResult("Alice Lake Provincial Park", 49.7696, -123.1163, "google")
    dup2 = GeoResult("Alice Lake, BC", 49.7697, -123.1164, "google")  # <0.5 km away

    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [dup1, dup2])
    results = gc.geocode_destination("Alice Lake")
    names = [r.name for r in results]
    assert len([n for n in names if "Alice Lake" in n]) == 1


