import pytest

import geocoder as gc
from geocoder import GeoResult, SQUAMISH_DEFAULT, _haversine_km, _similarity, _token_match_score


# --- exact match ---

def test_exact_match_alice_lake():
    results = gc.geocode_destination("Alice Lake")
    assert len(results) > 0
    assert any("Alice Lake" in r.name for r in results)


def test_exact_match_uses_gnws_source():
    results = gc.geocode_destination("Alice Lake")
    sources = {r.source for r in results}
    assert "gnws" in sources


def test_exact_match_mamquam():
    results = gc.geocode_destination("Mamquam")
    assert len(results) > 0
    assert any("Mamquam" in r.name for r in results)


# --- typo / fuzzy fallback ---

def test_typo_triggers_fuzzy_fallback():
    results = gc.geocode_destination("alce lake")
    assert len(results) > 0
    assert any("Alice Lake" in r.name for r in results)


def test_typo_results_tagged_fuzzy():
    results = gc.geocode_destination("alce lake")
    assert all(r.source == "fuzzy" for r in results)


# --- out-of-BC ---

def test_out_of_bc_returns_empty():
    results = gc.geocode_destination("Seattle Washington")
    assert results == []


def test_out_of_bc_far_location():
    results = gc.geocode_destination("Toronto Ontario")
    assert results == []


# --- distance sorting ---

def test_distance_sorting(monkeypatch):
    far = GeoResult("Test Spot Alpha", 51.5, -120.0, "gnws")   # ~250 km from Squamish
    close = GeoResult("Test Spot Beta", 49.72, -123.15, "gnws")  # ~2 km from Squamish
    mid = GeoResult("Test Spot Gamma", 50.1, -122.9, "gnws")   # ~45 km from Squamish

    monkeypatch.setattr(gc, "_gnws_lookup", lambda q: [far, close, mid])
    monkeypatch.setattr(gc, "_nominatim_lookup", lambda q: [])

    results = gc.geocode_destination("test spot", bias_point=SQUAMISH_DEFAULT)

    assert results[0].name == "Test Spot Beta"
    assert results[-1].name == "Test Spot Alpha"


def test_distance_sorting_closer_wins(monkeypatch):
    equidistant_a = GeoResult("Place A", 50.0, -123.5, "gnws")
    equidistant_b = GeoResult("Place B", 50.0, -122.7, "gnws")
    closer = GeoResult("Place C", 49.75, -123.16, "gnws")

    monkeypatch.setattr(gc, "_gnws_lookup", lambda q: [equidistant_a, equidistant_b, closer])
    monkeypatch.setattr(gc, "_nominatim_lookup", lambda q: [])

    results = gc.geocode_destination("place", bias_point=SQUAMISH_DEFAULT)

    assert results[0].name == "Place C"


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


# --- deduplication ---

def test_deduplication_removes_same_location(monkeypatch):
    dup1 = GeoResult("Alice Lake Provincial Park", 49.7696, -123.1163, "gnws")
    dup2 = GeoResult("Alice Lake, BC", 49.7697, -123.1164, "nominatim")  # <0.5 km away

    monkeypatch.setattr(gc, "_gnws_lookup", lambda q: [dup1])
    monkeypatch.setattr(gc, "_nominatim_lookup", lambda q: [dup2])

    results = gc.geocode_destination("Alice Lake")
    names = [r.name for r in results]
    assert len([n for n in names if "Alice Lake" in n]) == 1
