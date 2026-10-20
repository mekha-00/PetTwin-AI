"""Diagnosis record — a conclusion reached about a pet's condition."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    DiagnosisStatus,
    TimestampMixin,
    enum_column,
)


class DiagnosisRecord(Base, TimestampMixin):
    __tablename__ = "diagnosis_records"

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

    diagnosis_name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    icd10_code: Mapped[str | None] = mapped_column(String(16), index=True)
    status: Mapped[DiagnosisStatus] = enum_column(DiagnosisStatus, "diagnosis_status")
    diagnosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    diagnosed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    diagnosed_by_name: Mapped[str | None] = mapped_column(String(200))
    is_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    health_record: Mapped["HealthRecord"] = relationship(  # noqa: F821
        back_populates="diagnoses"
    )

    def __repr__(self) -> str:
        return f"<DiagnosisRecord {self.diagnosis_name} status={self.status}>"
