"""Pet access grants — invite, list and revoke collaborators.

Every function is owner-gated through :func:`require_pet_owner_access`, which is
the same rule that guards soft deletion: only the owner may change who else can
read the pet. A caregiver or veterinarian who can already write records must not
be able to widen or shrink someone else's access.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import PetAccess
from app.models.base import PetAccessRole
from app.models.pet import Pet
from app.models.user import User
from app.schemas.access import PetAccessGrant
from app.services.auth_service import get_user_by_email
from app.services.authorization import (
    get_active_access,
    grant_pet_access,
    require_pet_owner_access,
)


def _require_pet(db: Session, pet_id: uuid.UUID) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    return pet


def grant_access(
    db: Session,
    *,
    pet_id: uuid.UUID,
    requester_id: uuid.UUID,
    payload: PetAccessGrant,
) -> tuple[PetAccess, User]:
    """Invite an existing account to a pet. Owner-only.

    Resolving the email happens here, not through a public lookup endpoint, so
    the only way to learn whether an address has an account is to already own a
    pet and try to share it. The error for an unknown address is deliberately
    generic for the same reason.
    """
    require_pet_owner_access(db, pet_id=pet_id, user_id=requester_id)
    _require_pet(db, pet_id)

    target = get_user_by_email(db, str(payload.email))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account exists for that email address",
        )
    if target.id == requester_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have owner access to this pet",
        )

    existing = get_active_access(db, pet_id=pet_id, user_id=target.id)
    if existing is not None and existing.role is PetAccessRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That account already owns this pet",
        )

    access = grant_pet_access(
        db,
        pet_id=pet_id,
        user_id=target.id,
        role=payload.role,
        granted_by_user_id=requester_id,
        reason=payload.reason or f"granted by owner as {payload.role.value}",
    )
    db.commit()
    db.refresh(access)
    return access, target


def list_access(
    db: Session, *, pet_id: uuid.UUID, requester_id: uuid.UUID
) -> list[tuple[PetAccess, User]]:
    """List every live grant on a pet, owner included. Owner-only."""
    require_pet_owner_access(db, pet_id=pet_id, user_id=requester_id)
    _require_pet(db, pet_id)

    stmt = (
        select(PetAccess, User)
        .join(User, User.id == PetAccess.user_id)
        .where(PetAccess.pet_id == pet_id, PetAccess.revoked_at.is_(None))
        .order_by(PetAccess.granted_at)
    )
    return list(db.execute(stmt).all())


def revoke_access(
    db: Session, *, pet_id: uuid.UUID, requester_id: uuid.UUID, target_user_id: uuid.UUID
) -> PetAccess:
    """Revoke a collaborator's grant. Owner-only.

    The owner's own grant cannot be revoked: that would leave the pet with no
    one able to manage it or reach its history.
    """
    require_pet_owner_access(db, pet_id=pet_id, user_id=requester_id)
    _require_pet(db, pet_id)

    access = get_active_access(db, pet_id=pet_id, user_id=target_user_id)
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active access grant for that account",
        )
    if access.role is PetAccessRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The owner's access cannot be revoked",
        )

    access.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(access)
    return access
