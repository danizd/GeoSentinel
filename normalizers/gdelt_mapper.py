from datetime import datetime, timezone
from typing import Any

from normalizers.actor_mapper import cameo_to_actor
from schemas.events import Actor, CategoryEnum, EventCanonicalCreate, GeometryTypeEnum

GDELT_CAMEO_TYPE_MAP: dict[str, str] = {
    "14": "social_protest",
    "145": "social_riot",
    "17": "conflict_coercion",
    "18": "conflict_battle",
    "180": "conflict_battle",
    "181": "conflict_battle",
    "182": "conflict_explosion",
    "183": "conflict_battle",
    "19": "conflict_battle",
    "190": "conflict_battle",
    "191": "conflict_battle",
    "192": "conflict_battle",
    "193": "conflict_battle",
    "194": "conflict_battle",
    "195": "conflict_battle",
    "20": "conflict_atrocity",
    "200": "conflict_atrocity",
    "201": "conflict_atrocity",
    "202": "conflict_atrocity",
    "203": "conflict_atrocity",
    "204": "conflict_atrocity",
}

# F-NORM-SEV §conflict: la spec menciona GoldsteinScale como fuente pero no define
# tabla explicita de rangos. Se usa mapeo derivado: escala -10..+10 invertida a 1..10.
SEVERITY_GOLDSTEIN_MAP: list[tuple[float, float, float]] = [
    (float("-inf"), -8.0, 10.0),
    (-8.0, -6.0, 8.5),
    (-6.0, -4.0, 6.5),
    (-4.0, -2.0, 4.5),
    (-2.0, 0.0, 2.5),
    (0.0, float("inf"), 1.0),
]


def _cameo_to_event_type(cameo_code: str) -> str:
    """Busca el tipo canonico por el codigo CAMEO usando prefijo de mayor a menor."""
    for length in (3, 2):
        prefix = cameo_code[:length]
        if prefix in GDELT_CAMEO_TYPE_MAP:
            return GDELT_CAMEO_TYPE_MAP[prefix]
    return "conflict_unknown"


def _normalize_severity(goldstein: float) -> float:
    """Convierte GoldsteinScale [-10, +10] a severidad [1.0, 10.0]."""
    for low, high, severity in SEVERITY_GOLDSTEIN_MAP:
        if low <= goldstein < high:
            return severity
    return 1.0


def _parse_actors(event: dict[str, Any]) -> list[Actor]:
    """Extrae y normaliza actores Actor1 y Actor2 del evento GDELT."""
    actors: list[Actor] = []
    for prefix in ("Actor1", "Actor2"):
        code = event.get(f"{prefix}Code", "")
        name = event.get(f"{prefix}Name", "")
        if code or name:
            actors.append(cameo_to_actor(code or "UNK", name or None))
    return actors or None


def _parse_sqldate(sqldate: str) -> datetime:
    """Convierte SQLDATE (YYYYMMDD) a datetime UTC (D1: hora 00:00:00 UTC)."""
    return datetime.strptime(str(sqldate), "%Y%m%d").replace(tzinfo=timezone.utc)


def normalize_gdelt_event(event: dict[str, Any]) -> EventCanonicalCreate:
    """Normaliza un evento GDELT Cloud Events v2 al modelo canonico (F-ING-GDELT).

    Args:
        event: Diccionario con los campos del evento GDELT.

    Returns:
        EventCanonicalCreate listo para validacion y upsert.
    """
    lat_raw = event.get("ActionGeo_Lat")
    lon_raw = event.get("ActionGeo_Long")
    lat = float(lat_raw) if lat_raw is not None else None
    lon = float(lon_raw) if lon_raw is not None else None

    event_id_source = str(event.get("GLOBALEVENTID", ""))
    sqldate = event.get("SQLDATE", "")
    event_time = _parse_sqldate(sqldate) if sqldate else datetime.now(timezone.utc)

    cameo_code = str(event.get("EventCode", ""))
    event_type = _cameo_to_event_type(cameo_code) if cameo_code else "conflict_unknown"

    goldstein = event.get("GoldsteinScale")
    severity = _normalize_severity(float(goldstein)) if goldstein is not None else 1.0

    source_refs: list[str] = []
    if cameo_code:
        source_refs.append(f"cameo_code: {cameo_code}")
    if event.get("ActionGeo_FullName"):
        source_refs.append(event["ActionGeo_FullName"])

    return EventCanonicalCreate(
        event_id_source=event_id_source,
        source="gdelt",
        event_time=event_time,
        event_type=event_type,
        category=CategoryEnum.CONFLICT,
        latitude=lat,
        longitude=lon,
        location_accuracy_km=None,
        admin1=event.get("ActionGeo_ADM1Code"),
        admin2=event.get("ActionGeo_ADM2Code"),
        country_iso2=event.get("ActionGeo_CountryCode"),
        geometry=None,
        geometry_type=GeometryTypeEnum.POINT,
        actors=_parse_actors(event),
        fatalities=None,
        severity=severity,
        confidence=5.0,
        source_url=event.get("SOURCEURL"),
        source_refs=source_refs if source_refs else None,
        raw_event_id=None,
        is_confirmed=False,
        is_rumor=False,
        raw_payload=event,
    )
