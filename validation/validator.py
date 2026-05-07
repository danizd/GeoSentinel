from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.events_quarantine import EventsQuarantine
from schemas.events import EventCanonicalCreate, QuarantineInsertResult, ValidationResult

REJECTION_CODES = {
    "INVALID_COORDS": "Coordinates out of valid range",
    "NULL_COORDS": "Latitude or longitude is null",
    "FUTURE_DATE": "event_time is more than 1 hour in the future",
    "NULL_EVENT_TYPE": "event_type is null or empty",
    "NEGATIVE_FATALITIES": "fatalities value is invalid (< -1)",
    "SCHEMA_ERROR": "Failed to parse raw payload",
}


def validate_event(event: EventCanonicalCreate) -> ValidationResult:
    now = datetime.now(timezone.utc)
    one_hour_later = now + timedelta(hours=1)

    if event.latitude < -90 or event.latitude > 90:
        return ValidationResult(
            is_valid=False,
            rejection_code="INVALID_COORDS",
            rejection_detail=f"latitude {event.latitude} out of range [-90, 90]",
        )

    if event.longitude < -180 or event.longitude > 180:
        return ValidationResult(
            is_valid=False,
            rejection_code="INVALID_COORDS",
            rejection_detail=f"longitude {event.longitude} out of range [-180, 180]",
        )

    if event.event_time > one_hour_later:
        return ValidationResult(
            is_valid=False,
            rejection_code="FUTURE_DATE",
            rejection_detail=f"event_time {event.event_time} is more than 1 hour in the future",
        )

    if not event.event_type or not event.event_type.strip():
        return ValidationResult(
            is_valid=False,
            rejection_code="NULL_EVENT_TYPE",
            rejection_detail="event_type is null or empty",
        )

    if event.fatalities is not None and event.fatalities < -1:
        return ValidationResult(
            is_valid=False,
            rejection_code="NEGATIVE_FATALITIES",
            rejection_detail=f"fatalities value {event.fatalities} is invalid (minimum allowed is -1)",
        )

    return ValidationResult(is_valid=True, event=event)


def insert_quarantine(
    session: Session,
    source: str,
    raw_payload: dict[str, Any],
    rejection_code: str,
    rejection_detail: str | None = None,
) -> QuarantineInsertResult:
    try:
        quarantine_entry = EventsQuarantine(
            source=source,
            raw_payload=raw_payload,
            rejection_code=rejection_code,
            rejection_detail=rejection_detail,
        )
        session.add(quarantine_entry)
        session.commit()
        session.refresh(quarantine_entry)
        return QuarantineInsertResult(
            success=True, quarantine_id=quarantine_entry.id
        )
    except Exception as e:
        session.rollback()
        return QuarantineInsertResult(success=False, error=str(e))


def validate_and_quarantine(
    session: Session, event: EventCanonicalCreate
) -> ValidationResult:
    validation_result = validate_event(event)

    if not validation_result.is_valid:
        raw_payload = event.model_dump() if event.raw_payload is None else event.raw_payload
        insert_quarantine(
            session=session,
            source=event.source,
            raw_payload=raw_payload,
            rejection_code=validation_result.rejection_code,
            rejection_detail=validation_result.rejection_detail,
        )

    return validation_result