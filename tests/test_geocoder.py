import pytest

import geocoder as gc
from geocoder import GeoResult, SQUAMISH_DEFAULT, _haversine_km, _similarity, _token_match_score


# --- fuzzy fallback (no API needed) ---

def test_fuzzy_finds_alice_lake(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("Alice Lake")
    assert len(results) > 0
    assert any("Alice Lake" in r.name for r in results)


def test_fuzzy_finds_elfin_lakes(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("Elfin Lakes")
    assert any("Elfin Lakes" in r.name for r in results)


def test_typo_triggers_fuzzy_fallback(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("alce lake")
    assert len(results) > 0
    assert any("Alice Lake" in r.name for r in results)


def test_typo_results_tagged_fuzzy(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("alce lake")
    assert all(r.source == "fuzzy" for r in results)


def test_mamquam_fuzzy(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("Mamquam")
    assert any("Mamquam" in r.name for r in results)


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


# --- similarity helper ---

def test_similarity_substring_is_max():
    assert _similarity("Alice Lake", "Alice Lake Provincial Park") == 1.0


def test_similarity_exact_is_max():
    assert _similarity("Squamish", "Squamish") == 1.0


def test_similarity_unrelated_is_low():
    score = _similarity("Seattle", "Squamish, BC")
    assert score < 0.7


def test_token_match_score_typo():
    score = _token_match_score("alce lake", "Alice Lake Provincial Park")
    assert score == 1.0


def test_token_match_score_unrelated():
    score = _token_match_score("Seattle", "Levette Lake")
    assert score == 0.0


# --- stop-word regression: generic geo words cannot sole-justify a match ---

def test_william_lake_does_not_match_alice_lake(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("william lake")
    names = [r.name for r in results]
    assert not any("Alice Lake" in n for n in names), (
        "'william lake' should not fuzzy-match Alice Lake via shared 'lake' token"
    )


def test_williams_lake_fuzzy(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("williams lake")
    assert any("Williams Lake" in r.name for r in results)


def test_brentwood_fuzzy(monkeypatch):
    monkeypatch.setattr(gc, "_google_maps_lookup", lambda q, b: [])
    results = gc.geocode_destination("brentwood")
    assert any("Brentwood" in r.name for r in results)


# --- no API key graceful degradation ---

def test_no_api_key_falls_back_to_fuzzy(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    results = gc.geocode_destination("Whistler")
    assert len(results) > 0
    assert all(r.source == "fuzzy" for r in results)
