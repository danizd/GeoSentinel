from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from api.schemas.incidents import IncidentFilters, IncidentListResponse, IncidentPoint, IncidentResponse
from api.database import get_db
from models.incidents import Incident

router = APIRouter()


def parse_wkt_point(wkt: str) -> Optional[IncidentPoint]:
    if not wkt or not wkt.startswith("POINT("):
        return None
    coords = wkt.replace("POINT(", "").replace(")", "").split()
    return IncidentPoint(lon=float(coords[0]), lat=float(coords[1]))


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    bbox: Optional[str] = Query(None, description="lon_min,lat_min,lon_max,lat_max"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query("open,updated"),
    since: Optional[str] = Query(None),
    min_severity: Optional[float] = Query(None, ge=0, le=10),
    min_confidence: Optional[float] = Query(None, ge=0, le=10),
    sources: Optional[str] = Query(None),
    include_fp: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    aoi_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    query = select(Incident)

    status_list = status.split(",") if status else ["open", "updated"]
    if not include_fp:
        status_list = [s for s in status_list if s != "false_positive"]

    filters = [Incident.status.in_(status_list)]

    if category:
        filters.append(Incident.category == category)
    if since:
        filters.append(Incident.last_seen >= since)
    if min_severity is not None:
        filters.append(Incident.severity_max >= min_severity)
    if min_confidence is not None:
        filters.append(Incident.confidence >= min_confidence)
    if sources:
        source_list = sources.split(",")
        filters.append(Incident.source.any(source_list))

    query = query.where(and_(*filters))

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    results = db.execute(query).scalars().all()

    incidents = []
    for inc in results:
        incidents.append(IncidentResponse(
            incident_id=inc.incident_id,
            status=inc.status,
            category=inc.category,
            event_type=inc.event_type,
            canonical_point=parse_wkt_point(inc.canonical_point) if inc.canonical_point else None,
            first_seen=inc.first_seen,
            last_seen=inc.last_seen,
            severity_max=inc.severity_max,
            severity_latest=inc.severity_latest,
            confidence=inc.confidence,
            fatalities_total=inc.fatalities_total,
            sources=inc.sources,
            observation_count=inc.observation_count,
        ))

    return IncidentListResponse(total=total, page=page, incidents=incidents)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: UUID, db: Session = Depends(get_db)) -> IncidentResponse:
    incident = db.get(Incident, incident_id)
    if not incident:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    return IncidentResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        category=incident.category,
        event_type=incident.event_type,
        canonical_point=parse_wkt_point(incident.canonical_point) if incident.canonical_point else None,
        first_seen=incident.first_seen,
        last_seen=incident.last_seen,
        severity_max=incident.severity_max,
        severity_latest=incident.severity_latest,
        confidence=incident.confidence,
        fatalities_total=incident.fatalities_total,
        sources=incident.sources,
        observation_count=incident.observation_count,
    )