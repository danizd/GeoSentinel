from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class EventsCanonical(Base):
    __tablename__ = "events_canonical"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id_source: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    location_point: Mapped[Geometry] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    location_accuracy_km: Mapped[float | None] = mapped_column(Float)
    admin1: Mapped[str | None] = mapped_column(String)
    admin2: Mapped[str | None] = mapped_column(String)
    country_iso2: Mapped[str | None] = mapped_column(String)
    geometry: Mapped[Geometry | None] = mapped_column(Geometry(srid=4326))
    geometry_type: Mapped[str | None] = mapped_column(String)
    actors: Mapped[list[dict] | None] = mapped_column(JSONB)
    fatalities: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    raw_event_id: Mapped[int | None] = mapped_column(Integer)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rumor: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("source", "event_id_source", name="uq_events_canonical_source_event_id"),
        CheckConstraint("category IN ('conflict','disaster_natural','wildfire','mobility','humanitarian','other')", name="check_category"),
        CheckConstraint("severity BETWEEN 0 AND 10", name="check_severity"),
        CheckConstraint("confidence BETWEEN 0 AND 10", name="check_confidence"),
        CheckConstraint("geometry_type IN ('POINT','POLYGON','MULTIPOLYGON')", name="check_geometry_type"),
        Index("ix_events_canonical_location_point", "location_point", postgresql_using="gist"),
        Index("ix_events_canonical_event_time_category", "event_time", "category"),
        Index("ix_events_canonical_source_event_time", "source", "event_time"),
        Index("ix_events_canonical_category_is_confirmed", "category", "is_confirmed"),
    )