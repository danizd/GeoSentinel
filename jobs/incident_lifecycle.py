import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.incidents import Incident
from models.corrections_audit import CorrectionsAudit

logger = logging.getLogger(__name__)

INCIDENT_STALE_HOURS = 72
UPDATE_TO_OPEN_MINUTES = 15

INVALID_TRANSITIONS = {
    "closed": ["open", "updated", "stale"],
    "false_positive": ["updated", "stale"],
}


def transition_to_open(session: Session, incident: Incident, reason: str | None = None) -> Incident:
    if incident.status in INVALID_TRANSITIONS.get("closed", []):
        raise ValueError(f"Invalid transition from {incident.status} to open")
    if incident.status in INVALID_TRANSITIONS.get("false_positive", []):
        if reason != "operator_reversion" and incident.status == "false_positive":
            raise ValueError(f"Invalid transition from false_positive to open without operator reversion")

    incident.status = "open"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Incident {incident.incident_id} transitioned to open (reason: {reason})")
    return incident


def transition_to_updated(session: Session, incident: Incident) -> Incident:
    incident.status = "updated"
    incident.status_changed_at = datetime.now(timezone.utc)
    incident.last_updated = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Incident {incident.incident_id} transitioned to updated")
    return incident


def transition_to_stale(session: Session, incident: Incident) -> Incident:
    if incident.status not in ["open", "updated"]:
        raise ValueError(f"Cannot transition from {incident.status} to stale")

    incident.status = "stale"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Incident {incident.incident_id} transitioned to stale")
    return incident


def transition_to_closed(session: Session, incident: Incident, corrected_by: str = "system", reason: str | None = None) -> Incident:
    before_state = {
        "status": incident.status,
        "last_seen": incident.last_seen.isoformat() if incident.last_seen else None,
    }

    incident.status = "closed"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()

    correction = CorrectionsAudit(
        incident_id=incident.incident_id,
        corrected_by=corrected_by,
        correction_type="close",
        before_state=before_state,
        after_state={"status": "closed"},
        reason=reason,
    )
    session.add(correction)
    session.commit()

    logger.info(f"Incident {incident.incident_id} transitioned to closed")
    return incident


def transition_to_false_positive(session: Session, incident: Incident, corrected_by: str, reason: str | None = None) -> Incident:
    before_state = {
        "status": incident.status,
        "last_seen": incident.last_seen.isoformat() if incident.last_seen else None,
    }

    incident.status = "false_positive"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()

    correction = CorrectionsAudit(
        incident_id=incident.incident_id,
        corrected_by=corrected_by,
        correction_type="false_positive",
        before_state=before_state,
        after_state={"status": "false_positive"},
        reason=reason,
    )
    session.add(correction)
    session.commit()

    logger.info(f"Incident {incident.incident_id} marked as false_positive by {corrected_by}")
    return incident


def resolve_false_positive(session: Session, incident: Incident, corrected_by: str, reason: str | None = None) -> Incident:
    if incident.status != "false_positive":
        raise ValueError(f"Cannot resolve false_positive from status {incident.status}")

    before_state = {"status": "false_positive"}

    incident.status = "open"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()

    correction = CorrectionsAudit(
        incident_id=incident.incident_id,
        corrected_by=corrected_by,
        correction_type="reclassify",
        before_state=before_state,
        after_state={"status": "open"},
        reason=reason,
    )
    session.add(correction)
    session.commit()

    logger.info(f"Incident {incident.incident_id} resolved from false_positive")
    return incident


def reopen_closed(session: Session, incident: Incident, corrected_by: str, reason: str | None = None) -> Incident:
    if incident.status != "closed":
        raise ValueError(f"Cannot reopen incident with status {incident.status}")

    before_state = {"status": "closed"}

    incident.status = "open"
    incident.status_changed_at = datetime.now(timezone.utc)
    session.commit()

    correction = CorrectionsAudit(
        incident_id=incident.incident_id,
        corrected_by=corrected_by,
        correction_type="reclassify",
        before_state=before_state,
        after_state={"status": "open"},
        reason=reason,
    )
    session.add(correction)
    session.commit()

    logger.info(f"Incident {incident.incident_id} reopened from closed")
    return incident


def run_lifecycle_job(session: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=INCIDENT_STALE_HOURS)
    updated_threshold = now - timedelta(minutes=UPDATE_TO_OPEN_MINUTES)

    stale_transitions = 0
    open_transitions = 0

    stale_incidents = session.execute(
        select(Incident).where(
            Incident.status.in_(["open", "updated"]),
            Incident.last_seen < stale_threshold,
        )
    ).scalars().all()

    for incident in stale_incidents:
        try:
            transition_to_stale(session, incident)
            stale_transitions += 1
        except Exception as e:
            logger.error(f"Error transitioning incident {incident.incident_id} to stale: {e}")

    updated_incidents = session.execute(
        select(Incident).where(
            Incident.status == "updated",
            Incident.status_changed_at < updated_threshold,
        )
    ).scalars().all()

    for incident in updated_incidents:
        try:
            transition_to_open(session, incident, reason="auto_transition_after_15min")
            open_transitions += 1
        except Exception as e:
            logger.error(f"Error transitioning incident {incident.incident_id} to open: {e}")

    return {
        "stale_transitions": stale_transitions,
        "updated_to_open": open_transitions,
    }


if __name__ == "__main__":
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    logging.basicConfig(level=logging.INFO)

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    session = Session()
    try:
        result = run_lifecycle_job(session)
        logger.info(f"Lifecycle job result: {result}")
    finally:
        session.close()