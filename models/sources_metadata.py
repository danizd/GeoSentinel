from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class SourcesMetadata(Base):
    __tablename__ = "sources_metadata"

    source: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    independence_class: Mapped[str] = mapped_column(
        Text, nullable=False, comment="'sensor','field_reported','media_derived'"
    )
    typical_latency_min: Mapped[int | None] = mapped_column(Integer)
    update_frequency: Mapped[str | None] = mapped_column(String)
    coverage_notes: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "independence_class IN ('sensor','field_reported','media_derived')",
            name="check_independence_class",
        ),
    )