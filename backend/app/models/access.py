"""Pet ownership and access relationship.

This table is the authorization gate for every private pet record. A user may
only read or write a pet's records if an active row exists here linking them to
that pet. Ownership is expressed as a row with ``role = OWNER`` rather than a
column on ``users`` or ``pets``, so a pet can have an owner plus a veterinarian,
a caregiver, and a clinic without duplicating the pet.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PetAccessRole, TimestampMixin, enum_column


class PetAccess(Base, TimestampMixin):
    __tablename__ = "pet_access"
    __table_args__ = (
        Index("ix_pet_access_user_active", "user_id", "revoked_at"),
        Index("ix_pet_access_pet_active", "pet_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[PetAccessRole] = enum_column(PetAccessRole, "pet_access_role")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(255))

    pet: Mapped["Pet"] = relationship(  # noqa: F821
        back_populates="access", foreign_keys=[pet_id]
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="pet_access", foreign_keys=[user_id]
    )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def __init__(self, **kwargs) -> None:
        # ``granted_at`` has no database default, so a grant created without an
        # explicit timestamp would fail on insert. Defaulting it here means
        # callers only name the pet, the user and the role.
        kwargs.setdefault("granted_at", datetime.now(timezone.utc))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<PetAccess pet={self.pet_id} user={self.user_id} role={self.role}>"
