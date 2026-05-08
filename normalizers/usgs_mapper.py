import math
from datetime import datetime, timezone
from typing import Any

from schemas.events import CategoryEnum, EventCanonicalCreate, GeometryTypeEnum


USGS_TYPE_MAP = {
    "earthquake": "earthquake",
    "explosion": "explosion_seismic",
    "quarry blast": "quarry_blast",
    "ice quake": "ice_quake",
    "sonic boom": "sonic_boom",
}

SEVERITY_MAGNITUDE_MAP = {
    (0, 4.0): 1.0,
    (4.0, 5.0): 2.0,
    (5.0, 6.0): 4.0,
    (6.0, 7.0): 6.0,
    (7.0, 8.0): 8.0,
    (8.0, float("inf")): 10.0,
}


def _normalize_severity(magnitude: float) -> float:
    for (low, high), severity in SEVERITY_MAGNITUDE_MAP.items():
        if low <= magnitude < high:
            return severity
    return 1.0


def _normalize_category(event_type: str) -> CategoryEnum:
    if event_type in ("earthquake", "quarry_blast", "ice_quake", "explosion_seismic", "sonic_boom"):
        return CategoryEnum.DISASTER_NATURAL
    return CategoryEnum.OTHER


def normalize_usgs_event(usgs_feature: dict[str, Any]) -> EventCanonicalCreate:
    props = usgs_feature.get("properties", {})
    geom = usgs_feature.get("geometry", {})
    coords = geom.get("coordinates", [])

    lon = coords[0] if len(coords) > 0 else None
    lat = coords[1] if len(coords) > 1 else None
    depth_km = coords[2] if len(coords) > 2 else None

    event_id_source = props.get("ids", "").split(",")[0].strip(",")

    event_time = datetime.fromtimestamp(props.get("time", 0) / 1000, tz=timezone.utc)

    raw_event_type = props.get("type", "earthquake").lower()
    if raw_event_type in USGS_TYPE_MAP:
        event_type = USGS_TYPE_MAP[raw_event_type]
        category = _normalize_category(event_type)
    else:
        # Tipo desconocido: mantener "earthquake" por defecto pero categorizar
        # como OTHER para no contaminar las metricas de desastres naturales.
        event_type = "earthquake"
        category = CategoryEnum.OTHER

    magnitude = props.get("mag", 0.0)
    # En la integracion se redondea hacia arriba para reflejar la magnitud
    # observada por encima del umbral entero (e.g. mag 5.8 ~ severidad de 6).
    severity = _normalize_severity(math.ceil(magnitude)) if magnitude else _normalize_severity(0)
    confidence = 8.0

    source_refs = []
    if props.get("place"):
        source_refs.append(props["place"])
    if depth_km is not None:
        source_refs.append(f"depth: {depth_km} km")
    if props.get("url"):
        source_refs.append(props["url"])

    return EventCanonicalCreate(
        event_id_source=event_id_source or usgs_feature.get("id", "unknown"),
        source="usgs",
        event_time=event_time,
        event_type=event_type,
        category=category,
        latitude=lat,
        longitude=lon,
        location_accuracy_km=props.get("horizontalError"),
        admin1=None,
        admin2=None,
        country_iso2=None,
        geometry=None,
        geometry_type=GeometryTypeEnum.POINT,
        actors=None,
        fatalities=None,
        severity=severity,
        confidence=confidence,
        source_url=props.get("url"),
        source_refs=source_refs,
        raw_event_id=None,
        is_confirmed=True,
        is_rumor=False,
        raw_payload=usgs_feature,
    )