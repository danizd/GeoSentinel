from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CategoryEnum(str, Enum):
    CONFLICT = "conflict"
    DISASTER_NATURAL = "disaster_natural"
    WILDFIRE = "wildfire"
    MOBILITY = "mobility"
    HUMANITARIAN = "humanitarian"
    THERMAL_ANOMALY = "thermal_anomaly"
    OTHER = "other"


class GeometryTypeEnum(str, Enum):
    POINT = "POINT"
    POLYGON = "POLYGON"
    MULTIPOLYGON = "MULTIPOLYGON"


class Actor(BaseModel):
    role: str
    name: str
    cameo_code: str | None = None


class EventCanonicalCreate(BaseModel):
    # NOTA: las restricciones de lat/lon, severity, confidence y event_type
    # se aplican en la capa de validacion (validation.validator), no aqui,
    # para que los eventos invalidos puedan llegar a quarantine en lugar de
    # romper la construccion del schema.
    event_id_source: str
    source: str
    event_time: datetime
    event_type: str | None = None
    category: CategoryEnum
    latitude: float
    longitude: float
    location_accuracy_km: float | None = None
    admin1: str | None = None
    admin2: str | None = None
    country_iso2: str | None = None
    geometry: dict[str, Any] | None = None
    geometry_type: GeometryTypeEnum | None = None
    actors: list[Actor] | None = None
    fatalities: int | None = None
    severity: float = Field(..., ge=0.0, le=10.0)
    confidence: float = Field(..., ge=0.0, le=10.0)
    source_url: str | None = None
    source_refs: list[str] | None = None
    raw_event_id: int | None = None
    is_confirmed: bool = False
    is_rumor: bool = False
    raw_payload: dict[str, Any] | None = None


class EventQuarantineCreate(BaseModel):
    source: str
    raw_payload: dict[str, Any]
    rejection_code: str
    rejection_detail: str | None = None


class ValidationResult(BaseModel):
    is_valid: bool
    rejection_code: str | None = None
    rejection_detail: str | None = None
    event: EventCanonicalCreate | None = None


class QuarantineInsertResult(BaseModel):
    success: bool
    quarantine_id: int | None = None
    error: str | None = None