"""Job de post-procesado: deteccion de anomalias termicas en zonas de conflicto.

Logica:
  1. Toma hotspots FIRMS de las ultimas 24h
  2. Descarta los que estan en zonas con historial de incendios (90 dias, radio 5 km)
  3. Si el hotspot restante esta a < 10 km de un incidente 'conflict' activo
     → lo clasifica como thermal_anomaly y lo inserta como evento nuevo.

NO modifica el pipeline FIRMS existente. Es un paso posterior independiente.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from geoalchemy2.functions import ST_DWithin
from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.models.events_canonical import EventsCanonical
from backend.models.incidents import Incident
from backend.schemas.events import CategoryEnum, EventCanonicalCreate, GeometryTypeEnum

logger = logging.getLogger(__name__)

HISTORICAL_DAYS = 90
HISTORICAL_RADIUS_KM = 5
CONFLICT_PROXIMITY_KM = 10
HOTSPOT_LOOKBACK_HOURS = 24
MIN_CONFIDENCE = 5.0
SOURCE_NAME = "thermal_anomaly"


def _make_event_id(lat: float, lon: float, acq_time: str) -> str:
    raw = f"thermal|{lat:.4f}|{lon:.4f}|{acq_time}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _has_fire_history(session: Session, lat: float, lon: float) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORICAL_DAYS)
    stmt = select(func.count(EventsCanonical.id)).where(
        and_(
            EventsCanonical.category == CategoryEnum.WILDFIRE.value,
            EventsCanonical.event_time >= cutoff,
            ST_DWithin(
                EventsCanonical.location_point,
                func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
                HISTORICAL_RADIUS_KM * 1000,
            ),
        )
    )
    count = session.execute(stmt).scalar() or 0
    return count > 0


def _has_conflict_nearby(session: Session, lat: float, lon: float) -> bool:
    stmt = select(func.count(Incident.incident_id)).where(
        and_(
            Incident.category == "conflict",
            Incident.status.in_(["open", "updated"]),
            Incident.canonical_point.isnot(None),
            ST_DWithin(
                func.ST_GeomFromText(Incident.canonical_point, 4326),
                func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
                CONFLICT_PROXIMITY_KM * 1000,
            ),
        )
    )
    count = session.execute(stmt).scalar() or 0
    return count > 0


def _get_recent_hotspots(session: Session) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOTSPOT_LOOKBACK_HOURS)
    stmt = select(EventsCanonical).where(
        and_(
            EventsCanonical.source == "firms",
            EventsCanonical.event_type == "wildfire_hotspot",
            EventsCanonical.event_time >= cutoff,
        )
    )
    rows = session.execute(stmt).scalars().all()

    hotspots = []
    for row in rows:
        point = row.location_point
        lat, lon = None, None
        try:
            from geoalchemy2.shape import to_shape
            shape = to_shape(point)
            lat = shape.y
            lon = shape.x
        except Exception:
            continue

        if lat is None or lon is None:
            continue

        acq_time = None
        rp = row.raw_payload or {}
        for key in ("acq_time", "acq_datetime"):
            if key in rp:
                acq_time = str(rp[key])
                break

        hotspots.append({
            "lat": lat,
            "lon": lon,
            "brightness": rp.get("brightness"),
            "frp": rp.get("frp"),
            "acq_time": acq_time or row.event_time.isoformat(),
            "source_event": row,
        })

    return hotspots


def run_thermal_anomaly_detection(session: Session | None = None) -> dict:
    own_session = session is None
    if own_session:
        session = SessionLocal()

    try:
        hotspots = _get_recent_hotspots(session)
        logger.info(f"Thermal anomaly: analizando {len(hotspots)} hotspots FIRMS")

        detected = 0
        skipped_history = 0
        skipped_no_conflict = 0
        inserted = 0
        duplicates = 0

        for hs in hotspots:
            lat = hs["lat"]
            lon = hs["lon"]

            if _has_fire_history(session, lat, lon):
                skipped_history += 1
                continue

            if not _has_conflict_nearby(session, lat, lon):
                skipped_no_conflict += 1
                continue

            detected += 1

            event = EventCanonicalCreate(
                event_id_source=_make_event_id(lat, lon, hs["acq_time"]),
                source=SOURCE_NAME,
                event_time=hs["source_event"].event_time,
                event_type="thermal_anomaly_suspected",
                category=CategoryEnum.THERMAL_ANOMALY,
                latitude=lat,
                longitude=lon,
                location_accuracy_km=hs["source_event"].location_accuracy_km,
                severity=hs["source_event"].severity,
                confidence=max(MIN_CONFIDENCE, hs["source_event"].confidence or 0),
                geometry_type=GeometryTypeEnum.POINT,
                source_refs=[
                    f"firms_event_id: {hs['source_event'].id}",
                    f"brightness: {hs.get('brightness')}",
                    f"frp: {hs.get('frp')}",
                ],
                raw_payload={
                    "detection_source": "thermal_anomaly_job",
                    "firms_event_id": hs["source_event"].id,
                    "brightness": hs.get("brightness"),
                    "frp": hs.get("frp"),
                    "lat": lat,
                    "lon": lon,
                },
                is_confirmed=False,
                is_rumor=True,
            )

            from backend.jobs.event_processing import process_and_upsert_event
            result = process_and_upsert_event(session, event)
            if result.get("duplicate"):
                duplicates += 1
            else:
                inserted += 1

        if own_session:
            session.commit()

        stats = {
            "hotspots_analyzed": len(hotspots),
            "detected": detected,
            "inserted": inserted,
            "duplicates": duplicates,
            "skipped_history": skipped_history,
            "skipped_no_conflict": skipped_no_conflict,
        }
        logger.info(f"Thermal anomaly: {stats}")
        return stats

    finally:
        if own_session and session:
            session.close()
