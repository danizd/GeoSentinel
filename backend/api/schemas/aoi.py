from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AoiGeometry(BaseModel):
    type: str
    coordinates: Any


class AoiCreate(BaseModel):
    name: str
    geometry: AoiGeometry
    categories: list[str] | None = None
    min_severity: float = Field(0.0, ge=0.0, le=10.0)
    description: str | None = None


class AoiUpdate(BaseModel):
    name: str | None = None
    geometry: AoiGeometry | None = None
    categories: list[str] | None = None
    min_severity: float | None = Field(None, ge=0.0, le=10.0)
    description: str | None = None
    is_active: bool | None = None


class AoiResponse(BaseModel):
    aoi_id: UUID
    name: str
    description: str | None = None
    geometry: dict
    categories: list[str] | None = None
    min_severity: float
    is_active: bool
    created_by: str | None = None
    created_at: datetime


class AoiListResponse(BaseModel):
    total: int
    aois: list[AoiResponse]