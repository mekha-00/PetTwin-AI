"""Pydantic schemas for pets — full Phase 3 CRUD surface."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.base import Sex, SourceType, Species, VerificationStatus

NameStr = Annotated[str, Field(min_length=1, max_length=120)]
WeightKg = Annotated[float, Field(gt=0, le=2000)]
AgeMonths = Annotated[int, Field(ge=0, le=360)]


class PetBase(BaseModel):
    name: NameStr
    species: Species
    breed: str | None = Field(default=None, max_length=120)
    sex: Sex = Sex.UNKNOWN
    is_neutered: bool = False
    date_of_birth: date | None = None
    estimated_age_months: AgeMonths | None = None
    microchip_id: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=120)
    current_weight_kg: WeightKg | None = None
    notes: str | None = None

    @field_validator("name", "breed", "color", "microchip_id", mode="before")
    @classmethod
    def _reject_blank_text(cls, value):
        """A name of only spaces is not a name.

        ``min_length`` alone would accept ``"   "`` and create a pet that shows
        up in listings as an empty row, so blank text is stripped to ``None``
        and then rejected for the required fields.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return value

    @model_validator(mode="after")
    def _age_is_coherent(self) -> "PetBase":
        """Reject a birth date in the future, and age that contradicts it.

        Without this check a pet could be recorded as born tomorrow, or as five
        years old with a date of birth two weeks ago, and the Digital Twin would
        then report that age as fact.
        """
        today = date.today()
        if self.date_of_birth is not None:
            if self.date_of_birth > today:
                raise ValueError("date_of_birth cannot be in the future")
            if self.estimated_age_months is not None:
                implied = (today.year - self.date_of_birth.year) * 12 + (
                    today.month - self.date_of_birth.month
                )
                if today.day < self.date_of_birth.day:
                    implied -= 1
                if abs(implied - self.estimated_age_months) > 1:
                    raise ValueError(
                        "estimated_age_months conflicts with date_of_birth; "
                        "supply only one of them"
                    )
        return self


class PetCreate(PetBase):
    """Creating a pet. The owner grant is created server-side, never supplied."""

    source_type: SourceType = SourceType.MANUAL_ENTRY


class PetUpdate(BaseModel):
    """Partial update. Every field optional; ``None`` means "leave unchanged"."""

    name: NameStr | None = None
    species: Species | None = None
    breed: str | None = Field(default=None, max_length=120)
    sex: Sex | None = None
    is_neutered: bool | None = None
    date_of_birth: date | None = None
    estimated_age_months: AgeMonths | None = None
    microchip_id: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=120)
    current_weight_kg: WeightKg | None = None
    notes: str | None = None

    @field_validator(
        "name", "breed", "color", "microchip_id", "notes", mode="before"
    )
    @classmethod
    def _reject_blank_text(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "PetUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one field must be provided")
        return self


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    species: Species
    breed: str | None
    sex: Sex
    is_neutered: bool
    date_of_birth: date | None
    estimated_age_months: int | None
    microchip_id: str | None
    color: str | None
    current_weight_kg: float | None
    is_alive: bool
    source_type: SourceType
    verification_status: VerificationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    #: The calling user's role for this pet (owner/caregiver/veterinarian/clinic).
    #: Populated by the read endpoints so the client can gate UI without making a
    #: second call to the list endpoint. Always ``None`` on ``PetCreate``.
    viewer_role: str | None = None


class PetSummary(PetRead):
    """Pet plus the counts the list view needs, without a full twin assembly."""

    health_record_count: int = 0
    visit_count: int = 0
    allergy_count: int = 0


class PetDeleteResult(BaseModel):
    """Result of a delete. ``hard`` distinguishes the two deletion modes."""

    id: uuid.UUID
    deleted: bool
    hard: bool
    message: str
