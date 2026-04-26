import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx

_TIMEOUT = 3.0
_WILDLIFE_KEYWORDS = frozenset({"bear", "cougar", "wolf", "elk", "deer", "moose", "wildlife"})
_CLOSURE_KEYWORDS = frozenset({"closure", "closed", "restricted", "prohibited", "banned"})
_TRAIL_KEYWORDS = frozenset({"trail", "path", "route", "track"})
_AVALANCHE_KEYWORDS = frozenset({"avalanche", "snowpack", "cornice"})
_HUNTING_KEYWORDS = frozenset({"hunt", "hunting", "season", "bag limit", "wildlife alert"})

_DEDUP_THRESHOLD = 0.85


@dataclass
class Advisory:
    source: str
    category: str  # bear | cougar | closure | avalanche | hunting | general
    summary: str
    link: str
    date: str
    reliability_tier: str  # official | semi-official | community


def _categorize(text: str) -> str:
    t = text.lower()
    if any(kw in t for kw in _AVALANCHE_KEYWORDS):
        return "avalanche"
    if any(kw in t for kw in {"bear"}):
        return "bear"
    if any(kw in t for kw in {"cougar", "mountain lion"}):
        return "cougar"
    if any(kw in t for kw in _HUNTING_KEYWORDS):
        return "hunting"
    if any(kw in t for kw in _CLOSURE_KEYWORDS):
        return "closure"
    if any(kw in t for kw in _TRAIL_KEYWORDS):
        return "closure"
    return "general"


def _is_relevant(text: str) -> bool:
    t = text.lower()
    all_keywords = (
        _WILDLIFE_KEYWORDS | _CLOSURE_KEYWORDS | _TRAIL_KEYWORDS
        | _AVALANCHE_KEYWORDS | _HUNTING_KEYWORDS
    )
    return any(kw in t for kw in all_keywords)


def _parse_rss(xml_text: str, source: str, tier: str) -> list[Advisory]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    advisories = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = (item.findtext("pubDate") or "").strip()
        text = f"{title} {desc}"
        if _is_relevant(text):
            advisories.append(Advisory(
                source=source,
                category=_categorize(text),
                summary=title or desc[:120],
                link=link,
                date=date,
                reliability_tier=tier,
            ))
    return advisories


def _dedup(advisories: list[Advisory]) -> list[Advisory]:
    unique: list[Advisory] = []
    for a in advisories:
        if not any(
            SequenceMatcher(None, a.summary.lower(), u.summary.lower()).ratio() >= _DEDUP_THRESHOLD
            for u in unique
        ):
            unique.append(a)
    return unique


def _fetch_rss(url: str, source: str, tier: str) -> list[Advisory]:
    try:
        response = httpx.get(
            url, timeout=_TIMEOUT, headers={"User-Agent": "BCBackcountryScout/1.0"}
        )
        if response.status_code != 200:
            return []
        return _parse_rss(response.text, source, tier)
    except (httpx.TimeoutException, httpx.HTTPError):
        return []


def _stub_parks_canada() -> list[Advisory]:
    return [
        Advisory(
            source="Parks Canada",
            category="closure",
            summary="Check parkscanada.gc.ca for current Garibaldi trail closures and permit requirements.",
            link="https://www.pc.gc.ca/en/pn-np/bc/garibaldi",
            date="",
            reliability_tier="official",
        )
    ]


def _stub_hunting_bc() -> list[Advisory]:
    return [
        Advisory(
            source="Hunting BC",
            category="hunting",
            summary="Verify current hunting season dates and wildlife alerts at huntingbc.ca before your trip.",
            link="https://www.huntingbc.ca",
            date="",
            reliability_tier="official",
        )
    ]


def fetch_wildlife_news(
    corridor_polygon,
    destination_name: str,
) -> list[Advisory]:
    results: list[Advisory] = []

    results += _fetch_rss(
        "https://wildsafebc.com/feed/",
        source="WildSafeBC",
        tier="semi-official",
    )
    results += _fetch_rss(
        "https://www.squamishchief.com/feed/",
        source="Squamish Chief",
        tier="community",
    )
    results += _stub_parks_canada()
    results += _stub_hunting_bc()

    return _dedup(results)
