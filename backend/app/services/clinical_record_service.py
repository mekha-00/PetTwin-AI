"""Clinical record service — shared CRUD for the seven record types.

Every function in this module performs the same three checks in the same order:

1. the caller holds an active grant on the **pet in the URL path**;
2. the record being touched is actually attached to **that** pet;
3. the caller is permitted to write to it.

Check 2 is the one that is easy to miss and matters most. A client supplies
``health_record_id`` in the body of a symptom, while the pet comes from the
path. Without an explicit cross-check, a user could post a symptom referencing
a health record belonging to somebody else's pet and have it appear in their own
pet's history. Every child write therefore resolves the parent record and
compares its ``pet_id`` to the path value before inserting.
"""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import VerificationStatus
from app.models.diagnosis import DiagnosisRecord
from app.models.health_record import HealthRecord
from app.models.lab_report import LabReport
from app.models.medication import MedicationRecord
from app.models.symptom import SymptomRecord
from app.models.vaccination import VaccinationRecord
from app.models.visit import VeterinaryVisit
from app.services.authorization import require_pet_write_access

#: Child record types that hang off a health record rather than a visit.
CHILD_MODELS = (
    SymptomRecord,
    DiagnosisRecord,
    MedicationRecord,
    VaccinationRecord,
    LabReport,
)

#: Each child type's request field that identifies its parent health record.
CHILD_PARENT_FIELD = "health_record_id"


def require_pet_readable(db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Assert the caller may read this pet's records. 404 if not."""
    from app.models.pet import Pet  # local import avoids a circular dependency
    from app.services.authorization import get_active_access

    if db.get(Pet, pet_id) is None or (
        get_active_access(db, pet_id=pet_id, user_id=user_id) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found"
        )


def _assert_parent_belongs_to_pet(
    db: Session, *, health_record_id: uuid.UUID, pet_id: uuid.UUID
) -> HealthRecord:
    """Verify the referenced health record belongs to the pet in the path.

    Returns the parent so callers can reuse it. Raises 404 — not 400 — so that a
    probe cannot use the error code to discover which health records exist
    outside the caller's pets.
    """
    parent = db.get(HealthRecord, health_record_id)
    if parent is None or parent.pet_id != pet_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health record not found for this pet",
        )
    return parent


def _assert_visit_belongs_to_pet(
    db: Session, *, visit_id: uuid.UUID | None, pet_id: uuid.UUID
) -> None:
    if visit_id is None:
        return
    visit = db.get(VeterinaryVisit, visit_id)
    if visit is None or visit.pet_id != pet_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinary visit not found for this pet",
        )


def list_records(
    db: Session,
    *,
    model,
    pet_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    verified_only: bool = False,
) -> tuple[list[Any], int]:
    """Paginated list of a record type for one pet, newest first.

    ``verified_only`` filters on the record's own ``verification_status`` where
    it has one; for child types the flag lives on the parent health record, so
    the join is made explicitly.
    """
    order_col = _order_column(model)

    if model in CHILD_MODELS:
        stmt = (
            select(model)
            .join(HealthRecord, model.health_record_id == HealthRecord.id)
            .where(model.pet_id == pet_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(model)
            .join(HealthRecord, model.health_record_id == HealthRecord.id)
            .where(model.pet_id == pet_id)
        )
        if verified_only:
            stmt = stmt.where(
                HealthRecord.verification_status == VerificationStatus.VERIFIED
            )
            count_stmt = count_stmt.where(
                HealthRecord.verification_status == VerificationStatus.VERIFIED
            )
    else:
        has_verification = hasattr(model, "verification_status")
        stmt = select(model).where(model.pet_id == pet_id)
        count_stmt = select(func.count()).select_from(model).where(
            model.pet_id == pet_id
        )
        if verified_only and has_verification:
            stmt = stmt.where(
                model.verification_status == VerificationStatus.VERIFIED
            )
            count_stmt = count_stmt.where(
                model.verification_status == VerificationStatus.VERIFIED
            )

    stmt = stmt.order_by(order_col.desc()).limit(limit).offset(offset)
    total = db.execute(count_stmt).scalar_one()
    return list(db.execute(stmt).scalars().all()), total


def _order_column(model):
    """The column that defines chronological order for a record type."""
    return {
        HealthRecord: HealthRecord.occurred_at,
        SymptomRecord: SymptomRecord.onset_at,
        DiagnosisRecord: DiagnosisRecord.diagnosed_at,
        MedicationRecord: MedicationRecord.started_at,
        VaccinationRecord: VaccinationRecord.administered_at,
        LabReport: LabReport.performed_at,
        VeterinaryVisit: VeterinaryVisit.visit_at,
    }[model]


def create_visit(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID, data: dict
) -> VeterinaryVisit:
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    visit = VeterinaryVisit(pet_id=pet_id, **data)
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def create_health_record(
    db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID, data: dict
) -> HealthRecord:
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    visit_id = data.get("visit_id")
    _assert_visit_belongs_to_pet(db, visit_id=visit_id, pet_id=pet_id)
    record = HealthRecord(pet_id=pet_id, **data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_child(
    db: Session,
    *,
    model,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    data: dict,
) -> Any:
    """Create a symptom/diagnosis/medication/vaccination/lab report.

    The parent health record is verified against the path pet before insert.
    ``pet_id`` is always taken from the path, never from the payload, so the two
    cannot disagree.
    """
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    parent_id = data.pop(CHILD_PARENT_FIELD)
    _assert_parent_belongs_to_pet(
        db, health_record_id=parent_id, pet_id=pet_id
    )
    record = model(pet_id=pet_id, health_record_id=parent_id, **data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_record_or_404(
    db: Session, *, model, record_id: uuid.UUID, pet_id: uuid.UUID
) -> Any:
    """Load one record, confirming it belongs to the pet in the path."""
    record = db.get(model, record_id)
    if record is None or record.pet_id != pet_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record


def update_record(
    db: Session,
    *,
    model,
    record_id: uuid.UUID,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    data: dict,
) -> Any:
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    record = get_record_or_404(db, model=model, record_id=record_id, pet_id=pet_id)

    for field, value in data.items():
        # A child must not be re-parented through an update, and neither a pet
        # id nor a parent id may be overwritten.
        if field in (CHILD_PARENT_FIELD, "pet_id", "id"):
            continue
        setattr(record, field, value)

    # A diagnosis marked resolved without a status change would still read as
    # an active condition in the Digital Twin, so keep the two consistent.
    if model is DiagnosisRecord:
        if record.resolved_at is not None and record.status in (
            record.status.ACTIVE,
            record.status.CHRONIC,
        ):
            record.status = record.status.RESOLVED
        elif record.resolved_at is None and record.status in (
            record.status.RESOLVED,
            record.status.RULED_OUT,
        ):
            record.status = record.status.ACTIVE

    db.commit()
    db.refresh(record)
    return record


def delete_record(
    db: Session, *, model, record_id: uuid.UUID, pet_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    """Delete a clinical record.

    Hard delete is intentional here and differs from pet deletion: a mistyped
    symptom is a data-entry error in a record the owner just created, whereas
    losing a pet's entire medical history is not recoverable. The Digital Twin
    recomputes on read, so a deleted record disappears from it immediately.
    """
    require_pet_write_access(db, pet_id=pet_id, user_id=user_id)
    record = get_record_or_404(db, model=model, record_id=record_id, pet_id=pet_id)
    db.delete(record)
    db.commit()
    return {
        "id": str(record_id),
        "deleted": True,
        "message": f"{model.__name__} deleted",
    }
