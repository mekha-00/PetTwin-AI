"""Pet model — the subject of a Digital Twin.

This is the pet's identity only. Health state is *not* a column here; it is
derived from the pet's records by the Digital Twin service in a later phase.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    ProvenanceMixin,
    Sex,
    Species,
    TimestampMixin,
    VerificationStatus,
    enum_column,
)


class Pet(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "pets"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    species: Mapped[Species] = enum_column(Species, "species")
    breed: Mapped[str | None] = mapped_column(String(120), index=True)
    sex: Mapped[Sex] = enum_column(Sex, "sex")
    is_neutered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_age_months: Mapped[int | None] = mapped_column(nullable=True)

    microchip_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    color: Mapped[str | None] = mapped_column(String(120))

    current_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    primary_vet_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    access: Mapped[list["PetAccess"]] = relationship(  # noqa: F821
        back_populates="pet",
        cascade="all, delete-orphan",
        foreign_keys="PetAccess.pet_id",
    )
    visits: Mapped[list["VeterinaryVisit"]] = relationship(  # noqa: F821
        back_populates="pet",
        cascade="all, delete-orphan",
    )
    timeline_events: Mapped[list["HealthTimelineEvent"]] = relationship(  # noqa: F821
        back_populates="pet",
        cascade="all, delete-orphan",
    )
    health_records: Mapped[list["HealthRecord"]] = relationship(  # noqa: F821
        back_populates="pet",
        cascade="all, delete-orphan",
        foreign_keys="HealthRecord.pet_id",
    )
    allergies: Mapped[list["PetAllergy"]] = relationship(  # noqa: F821
        back_populates="pet",
        cascade="all, delete-orphan",
        order_by="PetAllergy.allergen",
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("verification_status", VerificationStatus.UNVERIFIED)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Pet {self.name}>"
