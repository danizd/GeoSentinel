import logging
import os

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

AIS_RELAY_URL = os.getenv("AIS_RELAY_URL", "http://localhost:8003")


class Location(BaseModel):
    latitude: float
    longitude: float


class AISVesselDTO(BaseModel):
    id: str
    mmsi: str
    name: str | None = None
    callsign: str | None = None
    location: Location
    sog: float
    cog: float
    heading: float
    navigationalStatus: str
    vesselType: str | None = None
    flag: str | None = None
    destination: str | None = None
    isDark: bool = False
    lastAisUpdate: str
    source: str


class AISVesselClusterDTO(BaseModel):
    center: Location
    count: int
    activityType: str


class AISVesselsResponseDTO(BaseModel):
    vessels: list[AISVesselDTO] = []
    clusters: list[AISVesselClusterDTO] = []
    isStale: bool = False


def get_aoi_bboxes(db: Session) -> list[dict]:
    result = db.execute(
        text("""
            SELECT aoi_id, name, ST_XMax(geometry) as max_lon, ST_YMax(geometry) as max_lat,
                   ST_XMin(geometry) as min_lon, ST_YMin(geometry) as min_lat
            FROM aoi
            WHERE is_active = true
        """)
    )
    aois = []
    for row in result:
        aois.append({
            "aoi_id": str(row[0]),
            "name": row[1],
            "max_lon": float(row[2]),
            "max_lat": float(row[3]),
            "min_lon": float(row[4]),
            "min_lat": float(row[5]),
        })
    return aois


@router.get("/ais-vessels", response_model=AISVesselsResponseDTO)
def list_ais_vessels(db: Session = Depends(get_db)) -> AISVesselsResponseDTO:
    aois = get_aoi_bboxes(db)

    if not aois:
        logger.warning("No active AOIs found for AIS vessels")
        return AISVesselsResponseDTO()

    all_vessels: list[dict] = []
    is_stale = False

    for aoi in aois:
        try:
            response = requests.get(
                f"{AIS_RELAY_URL}/api/ais/v1/list-vessels",
                params={
                    "neLat": aoi["max_lat"],
                    "neLon": aoi["max_lon"],
                    "swLat": aoi["min_lat"],
                    "swLon": aoi["min_lon"],
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if response.headers.get("X-Stale", "").lower() == "true":
                is_stale = True

            all_vessels.extend(data.get("vessels", []))

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch AIS vessels for AOI {aoi['name']}: {e}")
            continue

    unique: dict[str, dict] = {}
    for v in all_vessels:
        if v["id"] not in unique:
            unique[v["id"]] = v

    vessels_dto = [AISVesselDTO(**v) for v in unique.values()]
    clusters_dto = []

    return AISVesselsResponseDTO(
        vessels=vessels_dto,
        clusters=clusters_dto,
        isStale=is_stale,
    )
