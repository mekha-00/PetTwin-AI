"""Lab report — a single test result.

Reference range bounds are stored so that an out-of-range result can be flagged
later without needing the original lab's reference table. ``is_abnormal`` is
deliberately not populated here: deriving it is a data-cleaning decision, and
range conventions differ between laboratories.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LabReport(Base, TimestampMixin):
    __tablename__ = "lab_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    health_record_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("health_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    test_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    test_category: Mapped[str | None] = mapped_column(String(120), index=True)
    result_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_text: Mapped[str | None] = mapped_column(String(255))

    unit: Mapped[str | None] = mapped_column(String(64))
    reference_range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_range_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_abnormal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    lab_name: Mapped[str | None] = mapped_column(String(200))
    ordered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interpretation: Mapped[str | None] = mapped_column(Text)

    health_record: Mapped["HealthRecord"] = relationship(  # noqa: F821
        back_populates="lab_reports"
    )

    def __repr__(self) -> str:
        return f"<LabReport {self.test_name} at={self.performed_at}>"
