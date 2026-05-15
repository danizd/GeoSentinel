from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float


class AISVessel(BaseModel):
    id: str = Field(..., description="mmsi:timestamp_unix")
    mmsi: str
    name: Optional[str] = None
    callsign: Optional[str] = None
    location: Location
    sog: float = Field(..., ge=0, description="Speed over ground, knots")
    cog: float = Field(..., ge=0, le=360, description="Course over ground, degrees")
    heading: float = Field(..., ge=0, le=360, description="true heading")
    navigationalStatus: str = "underway"
    vesselType: Optional[str] = None
    flag: Optional[str] = None
    destination: Optional[str] = None
    isDark: bool = False
    lastAisUpdate: str = Field(..., description="ISO 8601 UTC")
    source: str = "aisstream"


class AISVesselCluster(BaseModel):
    center: Location
    count: int
    activityType: str = "unknown"


class AISVesselsResponse(BaseModel):
    vessels: list[AISVessel] = []
    clusters: list[AISVesselCluster] = []
    isStale: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))