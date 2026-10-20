"""Pet service — create, list, read, update, soft-delete and purge pets.

Deletion is two-phase by design:

* :func:`soft_delete_pet` is the default. It clears ``is_alive`` so the pet drops
  out of the default listing and revokes every *collaborator's* grant, while
  keeping the owner's. The clinical history therefore stays readable by the only
  party entitled to purge it.
* :func:`purge_pet` permanently erases the pet and cascades away its records.
  It is owner-only, because erasure destroys the owner's medical history and a
  caregiver must not be able to trigger it.

Both are owner-only: each either destroys history or revokes someone else's
access to it.

Known modelling limitation: ``Pet.is_alive`` predates Phase 3 and carries both
"the animal is alive" and "the pet is in the owner's active list". A removed pet
is therefore reported as ``is_alive=false`` even though it has not died. Splitting
the two would need either a new column on ``pets`` or a separate removal table,
both outside the additive Phase 3 scope; it is recorded here rather than papered
over.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.access import PetAccess
from app.models.allergy import PetAllergy
from app.models.base import PetAccessRole
from app.models.health_record import HealthRecord
from app.models.pet import Pet
from app.models.visit import VeterinaryVisit
from app.schemas.pet import PetCreate, PetSummary, PetUpdate
from app.services.authorization import (
    get_active_access,
    grant_pet_access,
    require_pet_owner_access,
    require_pet_purge_access,
    require_pet_write_access,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_pet(db: Session, *, payload: PetCreate, user_id: uuid.UUID) -> Pet:
    """Create a pet and make the creating user its owner.

    The owner grant is written here and never accepted from the request body, so
    a user cannot create a pet that belongs to someone else.
    """
    data = payload.model_dump()
    source_type = data.pop("source_type")
    pet = Pet(created_by_user_id=user_id, source_type=source_type, **data)
    db.add(pet)
    db.flush()

    grant_pet_access(
        db,
        pet_id=pet.id,
        user_id=user_id,
        role=PetAccessRole.OWNER,
        granted_by_user_id=user_id,
        reason="pet owner",
    )
    db.commit()
    db.refresh(pet)
    return pet


def list_pets_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    include_deceased: bool = False,
) -> list[PetSummary]:
    """List every pet the caller currently has an active grant for.

    The join is on ``pet_access`` rather than a column on ``users``, so a pet
    shared with the caller as a caregiver or veterinarian is listed alongside
    their own pets, annotated with the role that granted it.
    """
    stmt = (
        select(Pet, PetAccess.role)
        .join(PetAccess, PetAccess.pet_id == Pet.id)
        .where(PetAccess.user_id == user_id, PetAccess.revoked_at.is_(None))
        .order_by(Pet.name)
    )
    if not include_deceased:
        stmt = stmt.where(Pet.is_alive.is_(True))

    results: list[PetSummary] = []
    for pet, role in db.execute(stmt).all():
        results.append(
            PetSummary(
                **{
                    field: getattr(pet, field)
                    for field in PET_SUMMARY_FIELDS
                },
                health_record_count=_count(db, HealthRecord, pet.id),
                visit_count=_count(db, VeterinaryVisit, pet.id),
                allergy_count=_count(db, PetAllergy, pet.id),
                viewer_role=role.value,
            )
        )
    return results


#: The columns a ``PetSummary`` inherits from ``PetRead``. Kept as a module
#: constant so adding a field to ``PetRead`` cannot silently drop it from the
#: list endpoint.
PET_SUMMARY_FIELDS = (
        "id",
        "name",
        "species",
        "breed",
        "sex",
        "is_neutered",
        "date_of_birth",
        "estimated_age_months",
        "microchip_id",
        "color",
        "current_weight_kg",
        "is_alive",
        "source_type",
        "verification_status",
        "notes",
        "created_at",
        "updated_at",
    )


def _count(db: Session, model, pet_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(model).where(model.pet_id == pet_id)
    ).scalar_one()


def update_pet(
    db: Session, *, pet_id: uuid.UUID, payload: PetUpdate, user_id: uuid.UUID
) -> Pet:
    """Apply a partial update. Any active role may edit profile fields."""
    pet = _load_writable_pet(db, pet_id=pet_id, user_id=user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None or field in payload.model_fields_set:
            setattr(pet, field, value)
    db.commit()
    db.refresh(pet)
    return pet


def soft_delete_pet(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    """Remove a pet from the owner's active list, preserving its records.

    The pet row and every clinical record stay in the database. Two deliberate
    choices make the preservation actually useful:

    * **The owner's grant survives.** A soft delete that revoked the owner's
      access too would leave the retained history unreachable — the owner could
      never read it, never restore the pet, and never reach ``purge`` again. The
      pet simply stops appearing in the default listing, and comes back when
      ``include_deceased=true`` is passed.
    * **Every collaborator's grant is revoked.** A caregiver, veterinarian or
      clinic no longer has any business reading a pet that has been removed.

    Only the owner may do this, because it revokes other people's access.
    """
    require_pet_owner_access(db, pet_id=pet_id, user_id=user_id)
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    pet.is_alive = False

    grants = db.execute(
        select(PetAccess).where(
            PetAccess.pet_id == pet_id, PetAccess.revoked_at.is_(None)
        )
    ).scalars()
    for grant in grants:
        if grant.user_id == user_id:
            # Keep the owner's access so the preserved history stays reachable.
            continue
        grant.revoked_at = _now()

    db.commit()
    return {
        "id": str(pet_id),
        "deleted": True,
        "hard": False,
        "message": (
            "Pet removed from your active list and all other access revoked. "
            "Clinical history was preserved and remains available to you."
        ),
    }


def purge_pet(db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Permanently erase a pet and all of its clinical history. Owner-only.

    This cascades to allergies, access grants, visits, health records (and thus
    symptoms, diagnoses, medications, vaccinations and lab reports) and timeline
    events. It cannot be undone.
    """
    require_pet_purge_access(db, pet_id=pet_id, user_id=user_id)
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    db.delete(pet)
    db.commit()
    return {
        "id": str(pet_id),
        "deleted": True,
        "hard": True,
        "message": "Pet and all associated clinical records were permanently deleted.",
    }


def _load_writable_pet(db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID) -> Pet:
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    return pet


def get_pet_or_404(db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID) -> Pet:
    """Load a pet the caller may read, plus their role. Raises 404 otherwise."""
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    access = get_active_access(db, pet_id=pet_id, user_id=user_id)
    if access is None:
        # Same 404 as a missing pet: never confirm that someone else's pet id
        # exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )
    return pet


def get_pet_with_role(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Pet, str]:
    """Load a pet and the caller's role for it, or raise 404.

    The read endpoints attach the role to the response so a client no longer has
    to call ``GET /pets`` purely to discover whether it is the owner.
    """
    pet = get_pet_or_404(db, pet_id=pet_id, user_id=user_id)
    access = get_active_access(db, pet_id=pet_id, user_id=user_id)
    return pet, access.role.value
