"""Vaccination record.

``next_due_at`` is stored alongside ``administered_at`` so that due-date
reminders can be computed later from data already captured, without needing to
re-derive a schedule.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class VaccinationRecord(Base, TimestampMixin):
    __tablename__ = "vaccination_records"

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

    vaccine_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    batch_number: Mapped[str | None] = mapped_column(String(120))
    administered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    next_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    is_booster: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    route: Mapped[str | None] = mapped_column(String(64))
    administered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    clinic_name: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    health_record: Mapped["HealthRecord"] = relationship(  # noqa: F821
        back_populates="vaccinations"
    )

    def __repr__(self) -> str:
        return f"<VaccinationRecord {self.vaccine_name}>"
