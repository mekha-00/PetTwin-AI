"""Pet router — full CRUD, allergies, and the soft/hard delete distinction."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.allergy import PetAllergy
from app.schemas.access import PetAccessGrant, PetAccessRead
from app.schemas.allergy import PetAllergyCreate, PetAllergyRead, PetAllergyUpdate
from app.schemas.pet import PetCreate, PetDeleteResult, PetRead, PetSummary, PetUpdate
from app.services import access_service, pet_service
from app.services.clinical_record_service import delete_record, get_record_or_404
from app.services.authorization import WRITE_ROLES, require_pet_role

router = APIRouter(prefix="/pets", tags=["pets"])

PetPath = Annotated[uuid.UUID, Path(description="Target pet id")]


@router.post("", response_model=PetRead, status_code=status.HTTP_201_CREATED)
def create_pet(payload: PetCreate, db: DbSession, current_user: CurrentUser) -> PetRead:
    """Register a new pet. The caller becomes its owner."""
    pet = pet_service.create_pet(db, payload=payload, user_id=current_user.id)
    return PetRead.model_validate(pet).model_copy(update={"viewer_role": "owner"})


@router.get("", response_model=list[PetSummary])
def list_pets(
    db: DbSession,
    current_user: CurrentUser,
    include_deceased: bool = Query(
        default=False, description="Include pets soft-deleted or marked deceased"
    ),
) -> list[PetSummary]:
    """List every pet the caller has an active grant for."""
    return pet_service.list_pets_for_user(
        db, user_id=current_user.id, include_deceased=include_deceased
    )


@router.get("/{pet_id}", response_model=PetRead)
def get_pet(pet_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> PetRead:
    """Read one pet, including the caller's role. Returns 404 if not accessible."""
    pet, role = pet_service.get_pet_with_role(
        db, pet_id=pet_id, user_id=current_user.id
    )
    return PetRead.model_validate(pet).model_copy(update={"viewer_role": role})


@router.patch("/{pet_id}", response_model=PetRead)
def update_pet(
    pet_id: uuid.UUID, payload: PetUpdate, db: DbSession, current_user: CurrentUser
) -> PetRead:
    """Partially update pet profile fields."""
    pet = pet_service.update_pet(
        db, pet_id=pet_id, payload=payload, user_id=current_user.id
    )
    access = pet_service.get_pet_with_role(
        db, pet_id=pet_id, user_id=current_user.id
    )[1]
    return PetRead.model_validate(pet).model_copy(update={"viewer_role": access})


@router.delete("/{pet_id}", response_model=PetDeleteResult)
def delete_pet(
    pet_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> PetDeleteResult:
    """Soft-delete: mark inactive and revoke all grants, preserving history.

    Use ``POST /pets/{pet_id}/purge`` for permanent erasure.
    """
    return PetDeleteResult(
        **pet_service.soft_delete_pet(db, pet_id=pet_id, user_id=current_user.id)
    )


@router.post("/{pet_id}/purge", response_model=PetDeleteResult)
def purge_pet(
    pet_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> PetDeleteResult:
    """Permanently delete the pet and all clinical history. Owner-only, irreversible."""
    return PetDeleteResult(
        **pet_service.purge_pet(db, pet_id=pet_id, user_id=current_user.id)
    )


# ---------------------------------------------------------------------------
# Access grants (who else can see this pet)
# ---------------------------------------------------------------------------
@router.post(
    "/{pet_id}/access",
    response_model=PetAccessRead,
    status_code=status.HTTP_201_CREATED,
)
def grant_pet_access_endpoint(
    pet_id: uuid.UUID,
    payload: PetAccessGrant,
    db: DbSession,
    current_user: CurrentUser,
) -> PetAccessRead:
    """Share a pet with an existing account. Owner-only.

    Re-granting to an account that already has access replaces its role: the
    previous grant is revoked and a fresh one issued.
    """
    access, user = access_service.grant_access(
        db, pet_id=pet_id, requester_id=current_user.id, payload=payload
    )
    return PetAccessRead.from_grant(access, user)


@router.get("/{pet_id}/access", response_model=list[PetAccessRead])
def list_pet_access(
    pet_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> list[PetAccessRead]:
    """List everyone with access to this pet, including the owner. Owner-only."""
    rows = access_service.list_access(
        db, pet_id=pet_id, requester_id=current_user.id
    )
    return [PetAccessRead.from_grant(access, user) for access, user in rows]


@router.delete("/{pet_id}/access/{user_id}")
def revoke_pet_access(
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Revoke a collaborator's access. Owner-only; the owner's own grant is protected."""
    access_service.revoke_access(
        db, pet_id=pet_id, requester_id=current_user.id, target_user_id=user_id
    )
    return {
        "pet_id": str(pet_id),
        "user_id": str(user_id),
        "revoked": True,
        "message": "Access revoked. That account can no longer see this pet.",
    }


# ---------------------------------------------------------------------------
# Allergies
# ---------------------------------------------------------------------------
@router.post(
    "/{pet_id}/allergies", response_model=PetAllergyRead, status_code=status.HTTP_201_CREATED
)
def create_allergy(
    pet_id: uuid.UUID,
    payload: PetAllergyCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PetAllergyRead:
    require_pet_role(db, pet_id=pet_id, user_id=current_user.id, allowed=WRITE_ROLES)
    data = payload.model_dump()
    allergy = PetAllergy(pet_id=pet_id, **data)
    db.add(allergy)
    db.commit()
    db.refresh(allergy)
    return PetAllergyRead.model_validate(allergy)


@router.get("/{pet_id}/allergies", response_model=list[PetAllergyRead])
def list_allergies(
    pet_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    active_only: bool = Query(default=False),
) -> list[PetAllergyRead]:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    stmt = select(PetAllergy).where(PetAllergy.pet_id == pet_id)
    if active_only:
        stmt = stmt.where(PetAllergy.is_active.is_(True))
    return [
        PetAllergyRead.model_validate(a)
        for a in db.execute(stmt.order_by(PetAllergy.allergen)).scalars()
    ]


@router.get("/{pet_id}/allergies/{allergy_id}", response_model=PetAllergyRead)
def get_allergy(
    pet_id: uuid.UUID,
    allergy_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> PetAllergyRead:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    return PetAllergyRead.model_validate(
        get_record_or_404(
            db, model=PetAllergy, record_id=allergy_id, pet_id=pet_id
        )
    )


@router.patch("/{pet_id}/allergies/{allergy_id}", response_model=PetAllergyRead)
def update_allergy(
    pet_id: uuid.UUID,
    allergy_id: uuid.UUID,
    payload: PetAllergyUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> PetAllergyRead:
    require_pet_role(db, pet_id=pet_id, user_id=current_user.id, allowed=WRITE_ROLES)
    allergy = get_record_or_404(
        db, model=PetAllergy, record_id=allergy_id, pet_id=pet_id
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in ("pet_id", "id"):
            continue
        setattr(allergy, field, value)
    db.commit()
    db.refresh(allergy)
    return PetAllergyRead.model_validate(allergy)


@router.delete("/{pet_id}/allergies/{allergy_id}")
def delete_allergy(
    pet_id: uuid.UUID,
    allergy_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    require_pet_role(db, pet_id=pet_id, user_id=current_user.id, allowed=WRITE_ROLES)
    return delete_record(
        db, model=PetAllergy, record_id=allergy_id, pet_id=pet_id, user_id=current_user.id
    )
