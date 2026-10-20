"""Pet allergy — a substance the pet is known to react to.

Allergies are stored as rows rather than a comma-separated column on ``pets``
because an allergy is clinical information with structure: *what* the substance
is, *what* happened when the pet was exposed to it, and *how severe* the
reaction was. Flattening that into a text list on the pet would discard the
reaction detail that makes an allergy actionable.

Every other profile-level fact a pet profile is expected to show -- existing
conditions, current medications, vaccination status -- is deliberately **not**
stored on ``pets``. Those are derived from the clinical record tables by the
Digital Twin service, so there is exactly one place each fact lives and nothing
can drift. See ``app/services/digital_twin_service.py``.
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
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ProvenanceMixin, TimestampMixin


class PetAllergy(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "pet_allergies"
    __table_args__ = (
        CheckConstraint(
            "severity IS NULL OR (severity >= 1 AND severity <= 5)",
            name="ck_pet_allergies_severity_range",
        ),
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
    allergen: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    reaction: Mapped[str | None] = mapped_column(String(500))
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    pet: Mapped["Pet"] = relationship(back_populates="allergies")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PetAllergy {self.allergen} pet={self.pet_id}>"
