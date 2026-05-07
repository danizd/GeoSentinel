from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class EventsQuarantine(Base):
    __tablename__ = "events_quarantine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    rejection_code: Mapped[str] = mapped_column(
        String, nullable=False, comment="'INVALID_COORDS','FUTURE_DATE','NULL_REQUIRED','SCHEMA_ERROR'"
    )
    rejection_detail: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_events_quarantine_source_ingest_time", "source", "ingest_time"),
        Index("ix_events_quarantine_resolved", "resolved", postgresql_where=(~resolved)),
    )