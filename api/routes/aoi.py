from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_GeomFromText, ST_Intersects
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from api.schemas.aoi import AoiCreate, AoiListResponse, AoiResponse, AoiUpdate
from api.schemas.incidents import IncidentListResponse, IncidentPoint, IncidentResponse
from api.database import get_db
from models.aoi import Aoi
from models.incidents import Incident

router = APIRouter()


def geojson_to_wkt(geometry: dict) -> str | None:
    geom_type = geometry.get("type", "").lower()
    coords = geometry.get("coordinates", [])

    if geom_type == "polygon":
        ring = coords[0] if coords else []
        points = " ".join([f"{c[0]} {c[1]}" for c in ring])
        return f"POLYGON(({points}))"
    elif geom_type == "multipolygon":
        polygons = []
        for poly in coords:
            ring = poly[0] if poly else []
            points = " ".join([f"{c[0]} {c[1]}" for c in ring])
            polygons.append(f"({points})")
        return f"MULTIPOLYGON({','.join(polygons)})"
    return None


def wkb_to_geojson(geometry) -> dict:
    try:
        shape = to_shape(geometry)
        return mapping(shape)
    except Exception:
        return {"type": "Unknown", "coordinates": []}


@router.post("/aoi", response_model=AoiResponse, status_code=201)
def create_aoi(data: AoiCreate, db: Session = Depends(get_db)) -> AoiResponse:
    wkt = geojson_to_wkt(data.geometry.model_dump())
    if not wkt:
        raise HTTPException(status_code=400, detail="Invalid geometry format")

    aoi = Aoi(
        name=data.name,
        description=data.description,
        geometry=wkt,
        categories=data.categories,
        min_severity=data.min_severity,
        is_active=True,
        created_by="system",
    )

    db.add(aoi)
    db.commit()
    db.refresh(aoi)

    return AoiResponse(
        aoi_id=aoi.aoi_id,
        name=aoi.name,
        description=aoi.description,
        geometry=data.geometry.model_dump(),
        categories=aoi.categories,
        min_severity=aoi.min_severity,
        is_active=aoi.is_active,
        created_by=aoi.created_by,
        created_at=aoi.created_at,
    )


@router.get("/aoi", response_model=AoiListResponse)
def list_aois(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
) -> AoiListResponse:
    query = select(Aoi).where(Aoi.is_active == True)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    results = db.execute(query).scalars().all()

    aois = []
    for a in results:
        aois.append(AoiResponse(
            aoi_id=a.aoi_id,
            name=a.name,
            description=a.description,
            geometry=wkb_to_geojson(a.geometry),
            categories=a.categories,
            min_severity=a.min_severity,
            is_active=a.is_active,
            created_by=a.created_by,
            created_at=a.created_at,
        ))

    return AoiListResponse(total=total, aois=aois)


@router.get("/aoi/{aoi_id}", response_model=AoiResponse)
def get_aoi(aoi_id: UUID, db: Session = Depends(get_db)) -> AoiResponse:
    aoi = db.get(Aoi, aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    return AoiResponse(
        aoi_id=aoi.aoi_id,
        name=aoi.name,
        description=aoi.description,
        geometry=wkb_to_geojson(aoi.geometry),
        categories=aoi.categories,
        min_severity=aoi.min_severity,
        is_active=aoi.is_active,
        created_by=aoi.created_by,
        created_at=aoi.created_at,
    )


@router.put("/aoi/{aoi_id}", response_model=AoiResponse)
def update_aoi(aoi_id: UUID, data: AoiUpdate, db: Session = Depends(get_db)) -> AoiResponse:
    aoi = db.get(Aoi, aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    if data.name is not None:
        aoi.name = data.name
    if data.description is not None:
        aoi.description = data.description
    if data.categories is not None:
        aoi.categories = data.categories
    if data.min_severity is not None:
        aoi.min_severity = data.min_severity
    if data.is_active is not None:
        aoi.is_active = data.is_active
    if data.geometry is not None:
        wkt = geojson_to_wkt(data.geometry.model_dump())
        if wkt:
            aoi.geometry = wkt

    db.commit()
    db.refresh(aoi)

    return AoiResponse(
        aoi_id=aoi.aoi_id,
        name=aoi.name,
        description=aoi.description,
        geometry=wkb_to_geojson(aoi.geometry),
        categories=aoi.categories,
        min_severity=aoi.min_severity,
        is_active=aoi.is_active,
        created_by=aoi.created_by,
        created_at=aoi.created_at,
    )


@router.delete("/aoi/{aoi_id}", status_code=204)
def delete_aoi(aoi_id: UUID, db: Session = Depends(get_db)):
    aoi = db.get(Aoi, aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    aoi.is_active = False
    db.commit()

    return None


@router.get("/aoi/{aoi_id}/incidents", response_model=IncidentListResponse)
def get_aoi_incidents(
    aoi_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    aoi = db.get(Aoi, aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    spatial_filter = ST_Intersects(
        ST_GeomFromText(Incident.canonical_point, 4326),
        aoi.geometry,
    )

    base_filter = and_(
        Incident.status.in_(["open", "updated"]),
        Incident.canonical_point.isnot(None),
        spatial_filter,
    )

    count_query = select(func.count()).select_from(Incident).where(base_filter)
    total = db.execute(count_query).scalar() or 0

    offset = (page - 1) * limit
    query = select(Incident).where(base_filter).offset(offset).limit(limit)

    results = db.execute(query).scalars().all()

    from api.routes.incidents import parse_wkt_point

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