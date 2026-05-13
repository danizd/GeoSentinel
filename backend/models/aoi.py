import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Aoi(Base):
    __tablename__ = "aoi"

    aoi_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    geometry: Mapped[Geometry] = mapped_column(Geometry(srid=4326), nullable=False)
    categories: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    min_severity: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_aoi_geometry", "geometry", postgresql_using="gist"),
        Index("ix_aoi_is_active", "is_active", postgresql_where=text("is_active = true")),
    )