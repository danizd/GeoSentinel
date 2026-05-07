from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.corrections import CorrectionCreate, CorrectionResponse
from api.database import get_db
from jobs.incident_lifecycle import (
    transition_to_closed,
    transition_to_false_positive,
    resolve_false_positive,
    reopen_closed,
)
from models.corrections_audit import CorrectionsAudit
from models.incidents import Incident

router = APIRouter()


@router.post("/corrections", response_model=CorrectionResponse)
def create_correction(data: CorrectionCreate, db: Session = Depends(get_db)) -> CorrectionResponse:
    incident = db.get(Incident, data.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    before_state = {
        "status": incident.status,
        "category": incident.category,
        "event_type": incident.event_type,
        "canonical_point": incident.canonical_point,
    }

    corrected_by = "operator"

    needs_manual_audit = True

    if data.correction_type == "false_positive":
        transition_to_false_positive(db, incident, corrected_by, data.reason)
        needs_manual_audit = False
    elif data.correction_type == "close":
        transition_to_closed(db, incident, corrected_by, data.reason)
        needs_manual_audit = False
    elif data.correction_type == "reclassify":
        if incident.status == "false_positive":
            resolve_false_positive(db, incident, corrected_by, data.reason)
            needs_manual_audit = False
        else:
            if data.new_category:
                incident.category = data.new_category
            if data.new_event_type:
                incident.event_type = data.new_event_type
            db.commit()
    elif data.correction_type == "relocate":
        if data.new_coordinates:
            lon = data.new_coordinates.get("lon")
            lat = data.new_coordinates.get("lat")
            if lon and lat:
                incident.canonical_point = f"POINT({lon} {lat})"
                db.commit()
    elif data.correction_type == "merge":
        if not data.target_incident_id:
            raise HTTPException(status_code=400, detail="target_incident_id required for merge")
        target = db.get(Incident, data.target_incident_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target incident not found")

        for event_id in (incident.linked_event_ids or []):
            if event_id not in (target.linked_event_ids or []):
                target.linked_event_ids = (target.linked_event_ids or []) + [event_id]

        target.observation_count = len(target.linked_event_ids or [])
        target.last_updated = datetime.now(timezone.utc)

        incident.status = "closed"
        db.commit()

    after_state = {
        "status": incident.status,
        "category": incident.category,
        "event_type": incident.event_type,
        "canonical_point": incident.canonical_point,
    }

    if needs_manual_audit:
        correction = CorrectionsAudit(
            incident_id=incident.incident_id,
            corrected_by=corrected_by,
            correction_type=data.correction_type,
            before_state=before_state,
            after_state=after_state,
            reason=data.reason,
        )
        db.add(correction)
        db.commit()
        db.refresh(correction)
    else:
        correction = (
            db.query(CorrectionsAudit)
            .filter(CorrectionsAudit.incident_id == incident.incident_id)
            .order_by(CorrectionsAudit.created_at.desc())
            .first()
        )

    return CorrectionResponse(
        correction_id=correction.correction_id,
        incident_id=correction.incident_id,
        correction_type=correction.correction_type,
        before_state=correction.before_state,
        after_state=correction.after_state,
        reason=correction.reason,
        created_at=correction.created_at.isoformat(),
    )