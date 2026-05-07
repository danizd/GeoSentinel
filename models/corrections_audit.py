import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class CorrectionsAudit(Base):
    __tablename__ = "corrections_audit"

    correction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    corrected_by: Mapped[str] = mapped_column(String, nullable=False, comment="user_id o 'system'")
    correction_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="'false_positive','reclassify','relocate','merge','close'",
    )
    before_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "correction_type IN ('false_positive','reclassify','relocate','merge','close')",
            name="check_correction_type",
        ),
    )