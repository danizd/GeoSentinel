from datetime import datetime, timezone
from typing import Any

from backend.schemas.events import Actor, CategoryEnum, EventCanonicalCreate, GeometryTypeEnum

# F-NORM-CANON §2: mapeo de tipos ACLED al modelo canonico interno
ACLED_TYPE_MAP: dict[str, str] = {
    "Battles": "conflict_battle",
    "Explosions/Remote violence": "conflict_explosion",
    "Violence against civilians": "conflict_civilian_violence",
    "Protests": "social_protest",
    "Riots": "social_riot",
    "Strategic developments": "conflict_strategic",
}

# F-NORM-SEV §conflict: tabla por victimas fatales
SEVERITY_FATALITIES_MAP: list[tuple[int, int, float]] = [
    (0, 1, 1.0),
    (1, 6, 3.0),
    (6, 26, 5.0),
    (26, 101, 7.0),
    (101, 501, 8.5),
    (501, 999_999, 10.0),
]

# E-SOURCES §2.2: geo_precision -> location_accuracy_km
GEO_PRECISION_MAP: dict[int, float] = {
    1: 0.1,
    2: 5.0,
    3: 25.0,
    4: 100.0,
    5: 500.0,
}

# Lookup parcial country name -> ISO 3166-1 alpha-2 (paises principales de cobertura ACLED)
COUNTRY_ISO2_MAP: dict[str, str] = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "Angola": "AO",
    "Armenia": "AM", "Azerbaijan": "AZ", "Bahrain": "BH", "Bangladesh": "BD",
    "Belarus": "BY", "Benin": "BJ", "Bolivia": "BO", "Burkina Faso": "BF",
    "Burundi": "BI", "Cambodia": "KH", "Cameroon": "CM", "Central African Republic": "CF",
    "Chad": "TD", "Colombia": "CO", "Congo": "CG", "Cote d'Ivoire": "CI",
    "Democratic Republic of Congo": "CD", "Djibouti": "DJ", "Ecuador": "EC",
    "Egypt": "EG", "El Salvador": "SV", "Eritrea": "ER", "Ethiopia": "ET",
    "Gambia": "GM", "Georgia": "GE", "Ghana": "GH", "Guatemala": "GT",
    "Guinea": "GN", "Guinea-Bissau": "GW", "Haiti": "HT", "Honduras": "HN",
    "India": "IN", "Indonesia": "ID", "Iran": "IR", "Iraq": "IQ",
    "Israel": "IL", "Jordan": "JO", "Kazakhstan": "KZ", "Kenya": "KE",
    "Kosovo": "XK", "Kyrgyzstan": "KG", "Lebanon": "LB", "Liberia": "LR",
    "Libya": "LY", "Madagascar": "MG", "Malawi": "MW", "Malaysia": "MY",
    "Mali": "ML", "Mauritania": "MR", "Mexico": "MX", "Moldova": "MD",
    "Morocco": "MA", "Mozambique": "MZ", "Myanmar": "MM", "Nepal": "NP",
    "Nicaragua": "NI", "Niger": "NE", "Nigeria": "NG", "North Korea": "KP",
    "Pakistan": "PK", "Palestine": "PS", "Panama": "PA", "Papua New Guinea": "PG",
    "Peru": "PE", "Philippines": "PH", "Russia": "RU", "Rwanda": "RW",
    "Saudi Arabia": "SA", "Senegal": "SN", "Serbia": "RS", "Sierra Leone": "SL",
    "Somalia": "SO", "South Africa": "ZA", "South Sudan": "SS", "Sri Lanka": "LK",
    "Sudan": "SD", "Syria": "SY", "Tajikistan": "TJ", "Tanzania": "TZ",
    "Thailand": "TH", "Togo": "TG", "Tunisia": "TN", "Turkey": "TR",
    "Turkmenistan": "TM", "Uganda": "UG", "Ukraine": "UA", "Uzbekistan": "UZ",
    "Venezuela": "VE", "Vietnam": "VN", "Yemen": "YE", "Zambia": "ZM",
    "Zimbabwe": "ZW",
}


def _normalize_severity(fatalities: int | None) -> float:
    """Convierte el numero de victimas fatales a severidad 0-10 (F-NORM-SEV §conflict).

    Un valor -1 indica desconocido en ACLED; se trata como 0 para el calculo.
    """
    count = max(fatalities or 0, 0)
    for low, high, severity in SEVERITY_FATALITIES_MAP:
        if low <= count < high:
            return severity
    return 1.0


def _parse_actors(event: dict[str, Any]) -> list[Actor] | None:
    """Extrae actor1 y actor2 como lista de actores canonicos."""
    actors: list[Actor] = []
    for field in ("actor1", "actor2"):
        name = event.get(field, "").strip()
        if name:
            actors.append(Actor(role="unknown", name=name))
    return actors if actors else None


def normalize_acled_event(event: dict[str, Any]) -> EventCanonicalCreate:
    """Normaliza un evento ACLED al modelo canonico (F-ING-ACLED).

    Notas:
    - event_date se convierte a 00:00:00 UTC (D1, no hay hora disponible).
    - fatalities=-1 es el codigo ACLED para desconocido y se preserva tal cual
      (el validador permite values >= -1).
    - ACLED puede actualizar registros existentes; el upsert por
      (source, event_id_source) en event_processing.py lo maneja correctamente.

    Args:
        event: Diccionario con los campos del evento ACLED.

    Returns:
        EventCanonicalCreate listo para validacion y upsert.
    """
    event_date_str = event.get("event_date", "")
    event_time = (
        datetime.strptime(event_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if event_date_str
        else datetime.now(timezone.utc)
    )

    lat_raw = event.get("latitude")
    lon_raw = event.get("longitude")
    lat = float(lat_raw) if lat_raw is not None else None
    lon = float(lon_raw) if lon_raw is not None else None

    raw_event_type = event.get("event_type", "")
    event_type = ACLED_TYPE_MAP.get(raw_event_type, "conflict_unknown")

    fatalities_raw = event.get("fatalities")
    fatalities: int | None = None
    if fatalities_raw is not None:
        try:
            fatalities = int(fatalities_raw)
        except (ValueError, TypeError):
            fatalities = None

    severity = _normalize_severity(fatalities)

    geo_precision = event.get("geo_precision")
    location_accuracy_km = GEO_PRECISION_MAP.get(int(geo_precision), None) if geo_precision else None

    country_name = event.get("country", "")
    country_iso2 = COUNTRY_ISO2_MAP.get(country_name)

    source_refs: list[str] = []
    if event.get("notes"):
        source_refs.append(event["notes"][:500])
    if event.get("source"):
        source_refs.append(f"source: {event['source']}")

    return EventCanonicalCreate(
        event_id_source=str(event.get("data_id", "")),
        source="acled",
        event_time=event_time,
        event_type=event_type,
        category=CategoryEnum.CONFLICT,
        latitude=lat,
        longitude=lon,
        location_accuracy_km=location_accuracy_km,
        admin1=event.get("admin1"),
        admin2=event.get("admin2"),
        country_iso2=country_iso2,
        geometry=None,
        geometry_type=GeometryTypeEnum.POINT,
        actors=_parse_actors(event),
        fatalities=fatalities,
        severity=severity,
        confidence=7.0,
        source_url=event.get("source_url") or event.get("url"),
        source_refs=source_refs if source_refs else None,
        raw_event_id=None,
        is_confirmed=True,
        is_rumor=False,
        raw_payload=event,
    )
