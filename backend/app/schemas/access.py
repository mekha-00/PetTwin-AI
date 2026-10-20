"""Pydantic schemas for pet access grants.

A grant links an account to a pet with a role. The owner's grant is created
server-side when a pet is registered (see :mod:`app.services.pet_service`);
every other grant is issued by the pet's owner through these schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.base import PetAccessRole

#: Roles an owner may hand out. ``owner`` is excluded on purpose: transferring
#: ownership is outside this scope, and allowing a second owner grant would let
#: one owner revoke another's access.
GRANTABLE_ROLES = frozenset(
    {
        PetAccessRole.CAREGIVER,
        PetAccessRole.VETERINARIAN,
        PetAccessRole.CLINIC,
    }
)


class PetAccessGrant(BaseModel):
    """Invite an existing account to a pet, addressed by email."""

    email: EmailStr
    role: PetAccessRole = PetAccessRole.VETERINARIAN
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("role")
    @classmethod
    def _grantable_only(cls, value: PetAccessRole) -> PetAccessRole:
        if value not in GRANTABLE_ROLES:
            raise ValueError(
                "only 'caregiver', 'veterinarian' and 'clinic' access can be granted"
            )
        return value


class PetAccessRead(BaseModel):
    """A live grant, flattened with the collaborator's identity."""

    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: PetAccessRole
    granted_at: datetime
    reason: str | None = None

    @classmethod
    def from_grant(cls, access, user) -> "PetAccessRead":
        """Build from a ``PetAccess`` row and its related ``User``."""
        return cls(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=access.role,
            granted_at=access.granted_at,
            reason=access.reason,
        )
