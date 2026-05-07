import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class IncidentStatus:
    OPEN = "open"
    UPDATED = "updated"
    STALE = "stale"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    country_iso2: Mapped[str | None] = mapped_column(String)
    admin1: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    canonical_point: Mapped[str | None] = mapped_column(String)
    canonical_geometry: Mapped[str | None] = mapped_column(String)
    severity_max: Mapped[float | None] = mapped_column(Float)
    severity_latest: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    fatalities_total: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    linked_event_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    __table_args__ = (
        CheckConstraint("severity_max BETWEEN 0 AND 10", name="check_incidents_severity_max"),
        CheckConstraint("severity_latest BETWEEN 0 AND 10", name="check_incidents_severity_latest"),
        CheckConstraint("confidence BETWEEN 0 AND 10", name="check_incidents_confidence"),
    )