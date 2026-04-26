from unittest.mock import MagicMock, patch

import pytest

from fetchers.wildlife_news import (
    Advisory,
    _categorize,
    _dedup,
    _is_relevant,
    _parse_rss,
    fetch_wildlife_news,
)


def _rss(items: list[dict]) -> str:
    """Build a minimal RSS XML string from a list of {title, description, link, pubDate}."""
    item_xml = ""
    for it in items:
        item_xml += (
            f"<item>"
            f"<title>{it.get('title','')}</title>"
            f"<description>{it.get('description','')}</description>"
            f"<link>{it.get('link','')}</link>"
            f"<pubDate>{it.get('pubDate','')}</pubDate>"
            f"</item>"
        )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{item_xml}</channel></rss>'


def _mock_rss_response(xml: str) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.text = xml
    return mock


# --- keyword filter ---

def test_bear_advisory_is_relevant():
    assert _is_relevant("Black bear spotted near Alice Lake trailhead")


def test_cougar_advisory_is_relevant():
    assert _is_relevant("Cougar warning issued for Mamquam area")


def test_trail_closure_is_relevant():
    assert _is_relevant("Elfin Lakes trail closed due to snow")


def test_unrelated_news_not_relevant():
    assert not _is_relevant("New coffee shop opens in downtown Squamish")


def test_avalanche_is_relevant():
    assert _is_relevant("High avalanche risk on Tantalus Range")


# --- category assignment ---

def test_categorize_bear():
    assert _categorize("Bear sighting reported at campsite") == "bear"


def test_categorize_cougar():
    assert _categorize("Cougar warning near Diamond Head") == "cougar"


def test_categorize_closure():
    assert _categorize("Trail closed due to maintenance") == "closure"


def test_categorize_avalanche():
    assert _categorize("Avalanche warning in effect") == "avalanche"


def test_categorize_hunting():
    assert _categorize("Hunting season opens for Zone 2-21") == "hunting"


# --- RSS parsing ---

def test_parse_rss_returns_relevant_items():
    xml = _rss([
        {"title": "Bear spotted near Alice Lake", "description": "", "link": "http://ex.com/1"},
        {"title": "Local restaurant review", "description": "", "link": "http://ex.com/2"},
    ])
    results = _parse_rss(xml, "WildSafeBC", "semi-official")
    assert len(results) == 1
    assert results[0].source == "WildSafeBC"
    assert results[0].reliability_tier == "semi-official"


def test_parse_rss_bad_xml_returns_empty():
    results = _parse_rss("not valid xml", "Test", "community")
    assert results == []


# --- deduplication ---

def test_dedup_removes_near_identical():
    a1 = Advisory("WildSafeBC", "bear", "Bear sighting near Alice Lake", "", "", "semi-official")
    a2 = Advisory("Squamish Chief", "bear", "Bear sighting near Alice Lake", "", "", "community")
    result = _dedup([a1, a2])
    assert len(result) == 1


def test_dedup_keeps_different_advisories():
    a1 = Advisory("WildSafeBC", "bear", "Bear near Alice Lake", "", "", "semi-official")
    a2 = Advisory("WildSafeBC", "cougar", "Cougar near Mamquam FSR", "", "", "semi-official")
    result = _dedup([a1, a2])
    assert len(result) == 2


# --- source reliability tiers ---

def test_parks_canada_stub_is_official():
    corridor = MagicMock()
    with patch("fetchers.wildlife_news._fetch_rss", return_value=[]):
        results = fetch_wildlife_news(corridor, "Alice Lake")
    official = [r for r in results if r.source == "Parks Canada"]
    assert official
    assert official[0].reliability_tier == "official"


def test_hunting_bc_stub_is_official():
    corridor = MagicMock()
    with patch("fetchers.wildlife_news._fetch_rss", return_value=[]):
        results = fetch_wildlife_news(corridor, "Alice Lake")
    hunting = [r for r in results if r.source == "Hunting BC"]
    assert hunting
    assert hunting[0].reliability_tier == "official"


# --- empty result ---

def test_no_relevant_news_returns_stubs_only():
    xml = _rss([{"title": "New coffee shop opens", "description": "", "link": ""}])
    corridor = MagicMock()
    with patch("fetchers.wildlife_news.httpx.get", return_value=_mock_rss_response(xml)):
        results = fetch_wildlife_news(corridor, "Alice Lake")
    # Should have at least the Parks Canada and Hunting BC stubs
    sources = {r.source for r in results}
    assert "Parks Canada" in sources
    assert "Hunting BC" in sources
