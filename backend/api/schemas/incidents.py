from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentPoint(BaseModel):
    lon: float
    lat: float


class IncidentResponse(BaseModel):
    incident_id: UUID
    status: str
    category: str
    event_type: str
    canonical_point: IncidentPoint | None = None
    first_seen: datetime
    last_seen: datetime
    severity_max: float | None = None
    severity_latest: float | None = None
    confidence: float | None = None
    fatalities_total: int | None = None
    sources: list[str] | None = None
    observation_count: int | None = None
    linked_event_ids: list[int] | None = None
    raw_payload: dict | None = None
    actors: list[dict] | None = None


class IncidentListResponse(BaseModel):
    total: int
    page: int
    incidents: list[IncidentResponse]


class IncidentFilters(BaseModel):
    bbox: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = "open,updated"
    since: Optional[datetime] = None
    min_severity: Optional[float] = Field(None, ge=0, le=10)
    min_confidence: Optional[float] = Field(None, ge=0, le=10)
    sources: Optional[str] = None
    include_fp: bool = False
    page: int = 1
    limit: int = Field(20, le=100)
    aoi_id: Optional[UUID] = None