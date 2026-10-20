"""Authorization checks for private pet records.

A user may only reach a pet's records if an active ``PetAccess`` row links them
to that pet. Every private pet endpoint must go through these helpers.

Two layers of check are used:

* **Reachability** — does an active grant exist at all? Handled by
  :func:`load_accessible_pet`, which answers 404 for both "no such pet" and
  "not yours" so pet ids cannot be enumerated.
* **Capability** — is this grant allowed to perform this *action*? Handled by
  :func:`require_pet_role`. A caregiver may read a pet and add records to it but
  may not purge it, because erasure destroys the owner's medical history.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import PetAccess
from app.models.base import PetAccessRole
from app.models.pet import Pet


def _now() -> datetime:
    return datetime.now(timezone.utc)


#: Roles permitted to purge a pet and permanently destroy its clinical history.
#: Deliberately owner-only: a caregiver or clinic account must not be able to
#: erase the record of what was previously known about the animal.
PURGE_ROLES = frozenset({PetAccessRole.OWNER})

#: Alias for :data:`PURGE_ROLES`, for actions gated on ownership rather than on
#: erasing history (notably soft deletion, which revokes collaborators' access).
OWNER_ROLES = PURGE_ROLES

#: Roles permitted to create and edit clinical records for a pet.
WRITE_ROLES = frozenset(
    {
        PetAccessRole.OWNER,
        PetAccessRole.CAREGIVER,
        PetAccessRole.VETERINARIAN,
        PetAccessRole.CLINIC,
    }
)


def grant_pet_access(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    role,
    granted_by_user_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> PetAccess:
    """Create an access grant, revoking any prior grant for the same pair."""
    stmt = select(PetAccess).where(
        PetAccess.pet_id == pet_id,
        PetAccess.user_id == user_id,
        PetAccess.revoked_at.is_(None),
    )
    for existing in db.execute(stmt).scalars():
        existing.revoked_at = _now()
    db.flush()

    access = PetAccess(
        pet_id=pet_id,
        user_id=user_id,
        role=role,
        granted_at=_now(),
        granted_by_user_id=granted_by_user_id,
        reason=reason,
    )
    db.add(access)
    db.flush()
    return access


def get_active_access(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> PetAccess | None:
    stmt = select(PetAccess).where(
        PetAccess.pet_id == pet_id,
        PetAccess.user_id == user_id,
        PetAccess.revoked_at.is_(None),
    )
    return db.execute(stmt).scalars().first()


def user_can_access_pet(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    return get_active_access(db, pet_id=pet_id, user_id=user_id) is not None


def load_accessible_pet(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> Pet:
    """Load a pet the user is allowed to see, or raise 404.

    A non-existent pet and a pet the caller has no grant for both produce 404
    rather than 403. A 403 would confirm that the id exists, letting a caller
    enumerate other people's pets.
    """
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    if not user_can_access_pet(db, pet_id=pet_id, user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    return pet


def require_pet_role(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    allowed: frozenset,
) -> PetAccess:
    """Return the caller's active grant, or raise if the role is not permitted.

    Raises **404** rather than 403 for a missing or revoked grant, for the same
    enumeration reason as :func:`load_accessible_pet`. A genuine role shortfall
    on a pet the caller can see is a real **403**, because the caller already
    knows the pet exists.
    """
    access = get_active_access(db, pet_id=pet_id, user_id=user_id)
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    if access.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{access.role.value}' is not permitted to perform this action"
            ),
        )
    return access


def require_pet_write_access(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> PetAccess:
    """Assert the caller may add or edit clinical records for this pet."""
    return require_pet_role(db, pet_id=pet_id, user_id=user_id, allowed=WRITE_ROLES)


def require_pet_purge_access(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> PetAccess:
    """Assert the caller may permanently erase this pet and its history."""
    return require_pet_role(db, pet_id=pet_id, user_id=user_id, allowed=PURGE_ROLES)


def require_pet_owner_access(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> PetAccess:
    """Assert the caller is this pet's owner.

    Used for actions that affect *other people's* access rather than the
    medical history itself — soft deletion revokes every collaborator's grant,
    so only the owner may trigger it. A caregiver must not be able to remove a
    pet from its owner and lock the vet out of the record.
    """
    return require_pet_role(db, pet_id=pet_id, user_id=user_id, allowed=OWNER_ROLES)
