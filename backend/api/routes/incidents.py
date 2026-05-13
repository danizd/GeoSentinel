from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from geoalchemy2.functions import ST_AsText, ST_GeomFromText, ST_Intersects, ST_MakeEnvelope, ST_Within
from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.types import Text

from backend.api.schemas.incidents import IncidentFilters, IncidentListResponse, IncidentPoint, IncidentResponse
from backend.api.database import get_db
from backend.models.aoi import Aoi
from backend.models.incidents import Incident

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
    if bbox:
        parts = bbox.split(",")
        if len(parts) == 4:
            lon_min, lat_min, lon_max, lat_max = (float(p) for p in parts)
            envelope = ST_MakeEnvelope(lon_min, lat_min, lon_max, lat_max, 4326)
            filters.append(Incident.canonical_point.isnot(None))
            filters.append(ST_Within(Incident.canonical_point, envelope))
    if sources:
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        if source_list:
            filters.append(Incident.sources.overlap(cast(source_list, PG_ARRAY(Text))))
    if aoi_id:
        aoi = db.get(Aoi, aoi_id)
        if aoi:
            filters.append(Incident.canonical_point.isnot(None))
            filters.append(ST_Intersects(Incident.canonical_point, aoi.geometry))

    where_clause = and_(*filters)

    count_result = db.execute(
        select(func.count()).select_from(Incident).where(where_clause)
    ).scalar()
    total = count_result or 0

    offset = (page - 1) * limit
    rows = db.execute(
        select(Incident, ST_AsText(Incident.canonical_point))
        .where(where_clause)
        .offset(offset)
        .limit(limit)
    ).all()

    incidents = []
    for inc, point_wkt in rows:
        incidents.append(IncidentResponse(
            incident_id=inc.incident_id,
            status=inc.status,
            category=inc.category,
            event_type=inc.event_type,
            canonical_point=parse_wkt_point(point_wkt) if point_wkt else None,
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
    row = db.execute(
        select(Incident, ST_AsText(Incident.canonical_point))
        .where(Incident.incident_id == incident_id)
    ).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    incident, point_wkt = row
    return IncidentResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        category=incident.category,
        event_type=incident.event_type,
        canonical_point=parse_wkt_point(point_wkt) if point_wkt else None,
        first_seen=incident.first_seen,
        last_seen=incident.last_seen,
        severity_max=incident.severity_max,
        severity_latest=incident.severity_latest,
        confidence=incident.confidence,
        fatalities_total=incident.fatalities_total,
        sources=incident.sources,
        observation_count=incident.observation_count,
    )