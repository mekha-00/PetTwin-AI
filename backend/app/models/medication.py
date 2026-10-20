"""Medication record — a prescribed or administered medication."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MedicationRecord(Base, TimestampMixin):
    __tablename__ = "medication_records"

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

    medication_name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    dose_amount: Mapped[float | None] = mapped_column(nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(32))
    route: Mapped[str | None] = mapped_column(String(64))
    frequency: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    prescribed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    prescribed_by_name: Mapped[str | None] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text)

    health_record: Mapped["HealthRecord"] = relationship(  # noqa: F821
        back_populates="medications"
    )

    def __repr__(self) -> str:
        return f"<MedicationRecord {self.medication_name}>"
