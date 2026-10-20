"""Pydantic schemas for pet allergies."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import SourceType, VerificationStatus

Severity = Annotated[int, Field(ge=1, le=5)]


class PetAllergyCreate(BaseModel):
    allergen: str = Field(min_length=1, max_length=200)
    reaction: str | None = Field(default=None, max_length=500)
    severity: Severity | None = None
    onset_at: datetime | None = None
    is_active: bool = True
    source_type: SourceType = SourceType.MANUAL_ENTRY
    #: Settable at creation for the same reason as on ``VisitCreate``: a reaction
    #: confirmed by a clinic is filed as verified rather than requiring a second
    #: round trip. Without this the field would be unreachable, and since the
    #: Digital Twin reports verified state only, every allergy would be
    #: permanently invisible to the twin.
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED


class PetAllergyUpdate(BaseModel):
    allergen: str | None = Field(default=None, min_length=1, max_length=200)
    reaction: str | None = Field(default=None, max_length=500)
    severity: Severity | None = None
    onset_at: datetime | None = None
    is_active: bool | None = None
    verification_status: VerificationStatus | None = None

    def model_post_init(self, _context) -> None:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one field must be provided")


class PetAllergyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pet_id: uuid.UUID
    allergen: str
    reaction: str | None
    severity: int | None
    onset_at: datetime | None
    is_active: bool
    source_type: SourceType
    verification_status: VerificationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
