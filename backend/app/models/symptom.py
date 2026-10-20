"""Symptom record — a single observed clinical sign.

Symptom names are stored as recorded by the clinician or owner. They are
deliberately *not* normalised to a controlled vocabulary here: the dataset
analysis found 935 distinct raw labels, and collapsing them is a Phase 2
data-cleaning decision that must be reviewable, not a silent side effect of
inserting a row.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SymptomRecord(Base, TimestampMixin):
    __tablename__ = "symptom_records"

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

    symptom_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_chronic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observed_by: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    normalized_code: Mapped[str | None] = mapped_column(String(64), index=True)

    health_record: Mapped["HealthRecord"] = relationship(  # noqa: F821
        back_populates="symptoms"
    )

    __table_args__ = (
        CheckConstraint(
            "severity IS NULL OR (severity >= 1 AND severity <= 5)",
            name="ck_symptom_records_severity_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<SymptomRecord {self.symptom_name}>"
