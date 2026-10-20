"""Pydantic schemas for user accounts and authentication.

``UserRead`` deliberately has no ``hashed_password`` field, so the hash cannot
leak into a response even if a caller forgets to filter it.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import (
    MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
    PasswordTooLongError,
    validate_password,
)
from app.models.base import UserRole


#: Roles a visitor is allowed to choose at signup. ``admin`` and
#: ``clinic_staff`` are deliberately excluded: neither is offered in the UI, and
#: accepting them from an unauthenticated request would let anyone claim a
#: privileged account. Privileged roles must be assigned by an administrator.
SELF_SIGNUP_ROLES = frozenset({UserRole.PET_OWNER, UserRole.VETERINARIAN})


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_BYTES,
    )
    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    role: UserRole = UserRole.PET_OWNER
    clinic_name: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        try:
            validate_password(value)
        except PasswordTooLongError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("role")
    @classmethod
    def _only_self_signup_roles(cls, value: UserRole) -> UserRole:
        if value not in SELF_SIGNUP_ROLES:
            raise ValueError(
                "only 'pet_owner' and 'veterinarian' accounts can self-register"
            )
        return value

    @field_validator("clinic_name", mode="before")
    @classmethod
    def _blank_clinic_is_none(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    is_staff: bool
    phone: str | None
    clinic_name: str | None
    created_at: datetime
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    clinic_name: str | None = Field(default=None, max_length=200)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
