"""Veterinary visit model — a single encounter with a pet."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    ProvenanceMixin,
    TimestampMixin,
    VisitStatus,
    VisitType,
    enum_column,
)


class VeterinaryVisit(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "veterinary_visits"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    visit_type: Mapped[VisitType] = enum_column(VisitType, "visit_type")
    status: Mapped[VisitStatus] = enum_column(VisitStatus, "visit_status")

    clinic_name: Mapped[str | None] = mapped_column(String(200))
    veterinarian_name: Mapped[str | None] = mapped_column(String(200))
    veterinarian_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason_for_visit: Mapped[str | None] = mapped_column(String(500))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    clinical_summary: Mapped[str | None] = mapped_column(Text)
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    pet: Mapped["Pet"] = relationship(back_populates="visits")  # noqa: F821
    health_records: Mapped[list["HealthRecord"]] = relationship(  # noqa: F821
        back_populates="visit",
        cascade="all, delete-orphan",
        foreign_keys="HealthRecord.visit_id",
    )

    def __repr__(self) -> str:
        return f"<VeterinaryVisit pet={self.pet_id} at={self.visit_at}>"
