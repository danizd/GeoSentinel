import hashlib
from datetime import datetime, timezone
from typing import Any

from schemas.events import CategoryEnum, EventCanonicalCreate, GeometryTypeEnum


FIRMS_TYPE_MAP = {
    0: "wildfire_hotspot",
    1: "volcanic_hotspot",
    2: "other_hotspot",
    3: "offshore_hotspot",
}

FIRMS_CONFIDENCE_FILTER = {"nominal", "high"}

FIRMS_TYPE_FILTER = {0, 1}

SEVERITY_FRP_MAP = {
    (0, 4): 1.0,
    (4, 8): 2.5,
    (8, 25): 5.0,
    (25, 50): 7.5,
    (50, float("inf")): 10.0,
}

LOCATION_ACCURACY = {
    "VIIRS_SNPP": 0.375,
    "MODIS": 1.0,
}


def _normalize_severity(frp: float) -> float:
    for (low, high), severity in SEVERITY_FRP_MAP.items():
        if low <= frp < high:
            return severity
    return 1.0


def _generate_event_id(latitude: float, longitude: float, acq_date: str, acq_time: str, satellite: str) -> str:
    key = f"{latitude}|{longitude}|{acq_date}|{acq_time}|{satellite}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _parse_datetime(acq_date: str, acq_time: str) -> datetime:
    acq_datetime = datetime.strptime(f"{acq_date} {acq_time.zfill(4)}", "%Y-%m-%d %H%M")
    return acq_datetime.replace(tzinfo=timezone.utc)


def normalize_firms_row(row: dict[str, Any], product: str = "VIIRS_SNPP_NRT") -> EventCanonicalCreate:
    latitude = row.get("latitude")
    longitude = row.get("longitude")
    acq_date = row.get("acq_date", "")
    acq_time = row.get("acq_time", "")
    satellite = row.get("satellite", "unknown")
    confidence = row.get("confidence", "").lower()

    if confidence not in FIRMS_CONFIDENCE_FILTER:
        raise ValueError(f"Confidence '{confidence}' not in {FIRMS_CONFIDENCE_FILTER}")

    event_id_source = _generate_event_id(latitude, longitude, acq_date, acq_time, satellite)

    event_time = _parse_datetime(acq_date, acq_time)

    fire_type = int(row.get("type", 0))
    if fire_type not in FIRMS_TYPE_FILTER:
        raise ValueError(f"Type '{fire_type}' not in {FIRMS_TYPE_FILTER}")

    event_type = FIRMS_TYPE_MAP.get(fire_type, "wildfire_hotspot")

    category = CategoryEnum.WILDFIRE if fire_type == 0 else CategoryEnum.OTHER

    frp = float(row.get("frp", 0))
    severity = _normalize_severity(frp)
    confidence_value = 8.0 if confidence == "high" else 6.0

    location_accuracy = LOCATION_ACCURACY.get(product.split("_")[0], 0.375)

    source_refs = [
        f"satellite: {satellite}",
        f"instrument: {row.get('instrument', 'unknown')}",
    ]
    if row.get("brightness"):
        source_refs.append(f"brightness: {row['brightness']}K")

    return EventCanonicalCreate(
        event_id_source=event_id_source,
        source="firms",
        event_time=event_time,
        event_type=event_type,
        category=category,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_km=location_accuracy,
        admin1=None,
        admin2=None,
        country_iso2=None,
        geometry=None,
        geometry_type=GeometryTypeEnum.POINT,
        actors=None,
        fatalities=None,
        severity=severity,
        confidence=confidence_value,
        source_url=None,
        source_refs=source_refs,
        raw_event_id=None,
        is_confirmed=True,
        is_rumor=False,
        raw_payload=row,
    )