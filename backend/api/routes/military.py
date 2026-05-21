import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

RELAY_URL = os.getenv("MILITARY_RELAY_URL", "http://localhost:8000")


class Location(BaseModel):
    latitude: float
    longitude: float


class MilitaryFlightDTO(BaseModel):
    id: str
    callsign: str
    hexCode: str
    location: Location
    altitude: int
    heading: int
    speed: int
    lastSeenAt: str
    aircraftType: Optional[str] = None
    aircraftModel: Optional[str] = None
    operator: Optional[str] = None
    operatorCountry: Optional[str] = None
    registration: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    isInteresting: bool = False
    trail: Optional[list[list[float]]] = None
    source: str = "opensky"


class MilitaryFlightClusterDTO(BaseModel):
    center: Location
    count: int
    avgAltitude: int
    avgSpeed: int


class MilitaryFlightsResponseDTO(BaseModel):
    flights: list[MilitaryFlightDTO] = []
    clusters: list[MilitaryFlightClusterDTO] = []
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


def _fetch_aoi_flights(aoi: dict) -> tuple[list[dict], list[dict], bool]:
    """Consulta el relay militar para una AOI. Devuelve (flights, clusters, is_stale)."""
    try:
        response = requests.get(
            f"{RELAY_URL}/api/military/v1/list-military-flights",
            params={
                "neLat": aoi["max_lat"],
                "neLon": aoi["max_lon"],
                "swLat": aoi["min_lat"],
                "swLon": aoi["min_lon"],
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        stale = response.headers.get("X-Stale", "").lower() == "true"
        return data.get("flights", []), data.get("clusters", []), stale
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch from relay for AOI {aoi['name']}: {e}")
        return [], [], False


@router.get("/military-flights", response_model=MilitaryFlightsResponseDTO)
def list_military_flights(
    db: Session = Depends(get_db),
) -> MilitaryFlightsResponseDTO:
    aois = get_aoi_bboxes(db)

    if not aois:
        logger.warning("No active AOIs found for military flights")
        return MilitaryFlightsResponseDTO()

    all_flights: list[dict] = []
    all_clusters: list[dict] = []
    is_stale = False

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_aoi_flights, aoi): aoi for aoi in aois}
        for future in as_completed(futures, timeout=20):
            flights, clusters, stale = future.result()
            all_flights.extend(flights)
            all_clusters.extend(clusters)
            if stale:
                is_stale = True

    flights_dto = [MilitaryFlightDTO(**f) for f in all_flights]
    clusters_dto = [MilitaryFlightClusterDTO(**c) for c in all_clusters]

    return MilitaryFlightsResponseDTO(
        flights=flights_dto,
        clusters=clusters_dto,
        isStale=is_stale,
    )