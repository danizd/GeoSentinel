from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

TrailCoordinates = list[list[float]]


class Location(BaseModel):
    latitude: float
    longitude: float


class MilitaryFlight(BaseModel):
    id: str = Field(..., description="hex:timestamp_unix")
    callsign: str
    hexCode: str = Field(..., description="Always uppercase")
    location: Location
    altitude: int = Field(..., ge=0, description="feet")
    heading: int = Field(..., ge=0, le=360, description="degrees 0-360")
    speed: int = Field(..., ge=0, description="knots")
    lastSeenAt: str = Field(..., description="ISO 8601 UTC")
    aircraftType: Optional[str] = None
    operator: Optional[str] = None
    operatorCountry: Optional[str] = None
    registration: Optional[str] = None
    aircraftModel: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    isInteresting: Optional[bool] = False
    confidence: Optional[float] = Field(None, ge=0.0, le=10.0)
    trail: Optional[TrailCoordinates] = Field(default=None, description="Path of last 5 positions [lon, lat]")


class MilitaryFlightCluster(BaseModel):
    center: Location
    count: int
    avgAltitude: int
    avgSpeed: int


class MilitaryFlightsResponse(BaseModel):
    flights: list[MilitaryFlight] = []
    clusters: list[MilitaryFlightCluster] = []
    isStale: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)