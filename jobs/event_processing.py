import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models.events_canonical import EventsCanonical
from schemas.events import EventCanonicalCreate

logger = logging.getLogger(__name__)


def process_and_upsert_event(
    session: Session,
    event: EventCanonicalCreate,
) -> dict[str, Any]:
    existing = session.execute(
        select(EventsCanonical).where(
            EventsCanonical.source == event.source,
            EventsCanonical.event_id_source == event.event_id_source,
        )
    ).scalar_one_or_none()

    if existing:
        existing.ingest_time = datetime.now(timezone.utc)
        if event.raw_payload:
            pass
        session.commit()
        return {"duplicate": True, "id": existing.id}

    new_event = EventsCanonical(
        event_id_source=event.event_id_source,
        source=event.source,
        event_time=event.event_time,
        event_type=event.event_type,
        category=event.category.value,
        location_point=f"POINT({event.longitude} {event.latitude})",
        location_accuracy_km=event.location_accuracy_km,
        admin1=event.admin1,
        admin2=event.admin2,
        country_iso2=event.country_iso2,
        geometry=None,
        geometry_type=event.geometry_type.value if event.geometry_type else None,
        actors=event.actors,
        fatalities=event.fatalities,
        severity=event.severity,
        confidence=event.confidence,
        source_url=event.source_url,
        source_refs=event.source_refs,
        raw_event_id=event.raw_event_id,
        is_confirmed=event.is_confirmed,
        is_rumor=event.is_rumor,
    )

    session.add(new_event)
    session.commit()
    session.refresh(new_event)

    return {"duplicate": False, "id": new_event.id}


def run_ingestion_pipeline(
    session: Session,
    events: list[EventCanonicalCreate],
) -> dict[str, Any]:
    processed = 0
    duplicates = 0
    errors = 0

    for event in events:
        try:
            result = process_and_upsert_event(session, event)
            if result.get("duplicate"):
                duplicates += 1
            else:
                processed += 1
        except Exception as e:
            logger.error(f"Error processing event {event.event_id_source}: {e}")
            errors += 1

    return {
        "processed": processed,
        "duplicates": duplicates,
        "errors": errors,
    }