from datetime import datetime, timezone
from typing import Any

from schemas.events import Actor, CategoryEnum, EventCanonicalCreate, GeometryTypeEnum

GDELT_CATEGORY_MAP: dict[str, str] = {
    "PROTESTS": "social_protest",
    "RIOTS": "social_riot",
    "BATTLES": "conflict_battle",
    "EXPLOSIONS": "conflict_explosion",
    "CRIMINAL_VIOLENCE": "conflict_criminal",
    "TERRORISM": "conflict_terror",
    "UNKNOWN": "conflict_unknown",
}

GDELT_SUBCATEGORY_MAP: dict[str, str] = {
    "ARMED_CONFLICT": "conflict_battle",
    "BOMBINGS": "conflict_explosion",
    "SHELLING": "conflict_battle",
    "PROTESTS": "social_protest",
    "RIOTS": "social_riot",
    "CIVILIAN_VIOLENCE": "conflict_atrocity",
}

SEVERITY_GOLDSTEIN_MAP: list[tuple[float, float, float]] = [
    (float("-inf"), -8.0, 10.0),
    (-8.0, -6.0, 8.5),
    (-6.0, -4.0, 6.5),
    (-4.0, -2.0, 4.5),
    (-2.0, 0.0, 2.5),
    (0.0, float("inf"), 1.0),
]


def _parse_event_date(date_str: str | None) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _extract_geo(event: dict[str, Any]) -> tuple[float | None, float | None]:
    geo = event.get("geo")
    if isinstance(geo, dict):
        lat = geo.get("lat") or geo.get("latitude")
        lon = geo.get("lon") or geo.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    lat = event.get("latitude") or event.get("lat")
    lon = event.get("longitude") or event.get("lon")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return None, None


def _extract_fatalities(event: dict[str, Any]) -> int | None:
    if event.get("has_fatalities"):
        fat = event.get("fatalities")
        if fat is not None:
            return int(fat)
    return None


def _parse_actors(event: dict[str, Any]) -> list[Actor] | None:
    actors_list = event.get("actors")
    if not actors_list:
        return None
    actors: list[Actor] = []
    for actor_data in actors_list:
        if isinstance(actor_data, dict):
            name = actor_data.get("name", "")
            country = actor_data.get("country", "")
            role = actor_data.get("role", "")
            cameo = actor_data.get("cameo_code", "")
            actors.append(
                Actor(
                    role=role or "unknown",
                    name=name or "",
                    cameo_code=cameo or None,
                )
            )
    return actors if actors else None


def _normalize_severity(goldstein: float | None) -> float:
    if goldstein is None:
        return 1.0
    for low, high, severity in SEVERITY_GOLDSTEIN_MAP:
        if low <= goldstein < high:
            return severity
    return 1.0


def _map_category(category: str | None, subcategory: str | None, title: str | None = None) -> str:
    title_lower = title.lower() if title else ""

    if "drone" in title_lower or "strike" in title_lower or "missile" in title_lower or "bomb" in title_lower:
        return "conflict_airstrike"
    if "explosion" in title_lower or "blast" in title_lower:
        return "conflict_explosion"
    if "protest" in title_lower or "demonstration" in title_lower:
        return "social_protest"
    if "riot" in title_lower:
        return "social_riot"
    if "kill" in title_lower or "murder" in title_lower or "assassination" in title_lower:
        return "conflict_atrocity"
    if "terror" in title_lower or "attack" in title_lower:
        return "conflict_terror"
    if "battle" in title_lower or "clash" in title_lower or "fighting" in title_lower:
        return "conflict_battle"

    if subcategory:
        mapped = GDELT_SUBCATEGORY_MAP.get(subcategory.upper())
        if mapped:
            return mapped
    if category:
        mapped = GDELT_CATEGORY_MAP.get(category.upper())
        if mapped:
            return mapped
    return "conflict_unknown"


def normalize_gdelt_event(event: dict[str, Any]) -> EventCanonicalCreate:
    event_id = str(event.get("id", ""))
    event_date = _parse_event_date(event.get("event_date"))
    lat, lon = _extract_geo(event)
    category = event.get("category", "")
    subcategory = event.get("subcategory", "")
    event_type = _map_category(category, subcategory, event.get("title"))
    fatalities = _extract_fatalities(event)

    metrics = event.get("metrics", {})
    goldstein = metrics.get("goldstein_scale")
    severity = _normalize_severity(goldstein)
    significance = metrics.get("significance", 0)

    actors = None

    source_refs: list[str] = []
    if event.get("url"):
        source_refs.append(f"gdelt_url: {event['url']}")
    if event.get("primary_story_url"):
        source_refs.append(f"story_url: {event['primary_story_url']}")
    if event.get("event_code"):
        source_refs.append(f"event_code: {event['event_code']}")
    if event.get("domain"):
        source_refs.append(f"domain: {event['domain']}")

    top_articles = event.get("top_articles", [])
    if top_articles:
        source_refs.append(f"articles_count: {len(top_articles)}")

    confidence = 5.0
    if goldstein is not None:
        confidence = min(10.0, abs(goldstein) + 5.0)

    raw_payload_clean = {
        "id": event.get("id"),
        "url": event.get("url"),
        "event_date": event.get("event_date"),
        "category": event.get("category"),
        "subcategory": event.get("subcategory"),
        "geo_lat": event.get("geo", {}).get("latitude") if isinstance(event.get("geo"), dict) else None,
        "geo_lon": event.get("geo", {}).get("longitude") if isinstance(event.get("geo"), dict) else None,
        "fatalities": event.get("fatalities"),
        "metrics": event.get("metrics"),
        "title": event.get("title"),
    }

    return EventCanonicalCreate(
        event_id_source=event_id,
        source="gdelt",
        event_time=event_date,
        event_type=event_type,
        category=CategoryEnum.CONFLICT,
        latitude=lat,
        longitude=lon,
        location_accuracy_km=None,
        admin1=event.get("admin1"),
        admin2=event.get("admin2"),
        country_iso2=None,
        geometry=None,
        geometry_type=GeometryTypeEnum.POINT,
        actors=None,
        fatalities=fatalities,
        severity=severity,
        confidence=confidence,
        source_url=event.get("url"),
        source_refs=source_refs if source_refs else None,
        raw_event_id=None,
        is_confirmed=bool(fatalities),
        is_rumor=False,
        raw_payload=raw_payload_clean,
    )
