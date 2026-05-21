import re
from datetime import datetime, timezone
from typing import Any

from backend.schemas.events import Actor, CategoryEnum, EventCanonicalCreate, GeometryTypeEnum

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


_TITLE_KEYWORDS: list[tuple[list[str], str]] = [
    (["drone strike", "airstrike", "air strike", "missile strike", "bombing raid"], "conflict_airstrike"),
    (["suicide bomb", "car bomb", "roadside bomb", "ied", "improvised explosive", "detonation"], "conflict_explosion"),
    (["assassination", "massacre", "execution", "ethnic cleansing"], "conflict_atrocity"),
    (["terrorist attack", "terrorism", "jihadist", "extremist attack"], "conflict_terror"),
    (["armed clash", "armed conflict", "gunfight", "firefight", "armed battle"], "conflict_battle"),
    (["mass protest", "mass demonstration"], "social_protest"),
]


def _match_title_keywords(title_lower: str) -> str | None:
    """Intenta clasificar por frases literales en el título. Solo frases inequívocas
    para evitar falsos positivos (p. ej. 'battle against drought', 'strike action').

    Args:
        title_lower: Título del artículo en minúsculas.

    Returns:
        Tipo de evento interno o None si no hay coincidencia.
    """
    for phrases, event_type in _TITLE_KEYWORDS:
        for phrase in phrases:
            if re.search(r'\b' + re.escape(phrase) + r'\b', title_lower):
                return event_type
    return None


def _map_category(category: str | None, subcategory: str | None, title: str | None = None) -> str:
    """Mapea los campos de categoría de GDELT Cloud al tipo de evento interno.

    Prioridad: subcategory API → category API → keywords de título (solo frases
    inequívocas con límites de palabra para evitar falsos positivos).

    Args:
        category: Campo 'category' de la respuesta GDELT Cloud.
        subcategory: Campo 'subcategory' de la respuesta GDELT Cloud.
        title: Título del artículo (fallback conservador).

    Returns:
        Tipo de evento interno como string.
    """
    if subcategory:
        mapped = GDELT_SUBCATEGORY_MAP.get(subcategory.upper())
        if mapped:
            return mapped
    if category:
        mapped = GDELT_CATEGORY_MAP.get(category.upper())
        if mapped:
            return mapped
    if title:
        matched = _match_title_keywords(title.lower())
        if matched:
            return matched
    return "conflict_unknown"


def _derive_canonical_category(event_type: str) -> CategoryEnum:
    """Deriva la categoría canónica a partir del tipo de evento interno.

    Args:
        event_type: Tipo de evento interno (p. ej. 'conflict_battle', 'social_protest').

    Returns:
        CategoryEnum correspondiente.
    """
    if event_type in ("social_protest", "social_riot"):
        return CategoryEnum.OTHER
    return CategoryEnum.CONFLICT


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
        category=_derive_canonical_category(event_type),
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
