"""Health record — the canonical verified record header for a clinical event.

A health record groups the detail rows (symptom, diagnosis, medication,
vaccination, lab report) that belong to one clinical event. It is the unit that
carries provenance and verification state, and it is what a future AI analysis
will reference — never the other way around.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    HealthRecordType,
    ProvenanceMixin,
    TimestampMixin,
    VerificationStatus,
    enum_column,
)


class HealthRecord(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "health_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("veterinary_visits.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    record_type: Mapped[HealthRecordType] = enum_column(
        HealthRecordType, "health_record_type"
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    clinic_name: Mapped[str | None] = mapped_column(String(200))
    external_reference: Mapped[str | None] = mapped_column(String(120))

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    pet: Mapped["Pet"] = relationship(  # noqa: F821
        back_populates="health_records", foreign_keys=[pet_id]
    )
    visit: Mapped["VeterinaryVisit | None"] = relationship(  # noqa: F821
        back_populates="health_records", foreign_keys=[visit_id]
    )

    symptoms: Mapped[list["SymptomRecord"]] = relationship(  # noqa: F821
        back_populates="health_record", cascade="all, delete-orphan"
    )
    diagnoses: Mapped[list["DiagnosisRecord"]] = relationship(  # noqa: F821
        back_populates="health_record", cascade="all, delete-orphan"
    )
    medications: Mapped[list["MedicationRecord"]] = relationship(  # noqa: F821
        back_populates="health_record", cascade="all, delete-orphan"
    )
    vaccinations: Mapped[list["VaccinationRecord"]] = relationship(  # noqa: F821
        back_populates="health_record", cascade="all, delete-orphan"
    )
    lab_reports: Mapped[list["LabReport"]] = relationship(  # noqa: F821
        back_populates="health_record", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("verification_status", VerificationStatus.UNVERIFIED)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<HealthRecord {self.title} pet={self.pet_id}>"
