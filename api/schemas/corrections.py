from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CorrectionCreate(BaseModel):
    incident_id: UUID
    correction_type: str = Field(..., pattern="^(false_positive|reclassify|relocate|merge|close)$")
    reason: str = Field(..., min_length=1)
    new_category: Optional[str] = None
    new_event_type: Optional[str] = None
    new_coordinates: Optional[dict] = None
    target_incident_id: Optional[UUID] = None


class CorrectionResponse(BaseModel):
    correction_id: UUID
    incident_id: UUID
    correction_type: str
    before_state: dict
    after_state: dict
    reason: str | None
    created_at: str