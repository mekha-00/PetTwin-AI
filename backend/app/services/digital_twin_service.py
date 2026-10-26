"""Digital Twin service — assembles a pet's current health state on demand.

What a Digital Twin is here
---------------------------
A **software-based Digital Twin** of a pet: a structured, continuously updated
representation of that pet's health state, assembled from the pet's own
records. When a verified record is added, the twin reflects it on the next read,
because the twin is recomputed from the records every time it is requested.

What it is **not**
-----------------
* **Not a database table.** There is no ``digital_twins`` table and no cached
  twin blob. Persisting the assembly would freeze a moving summary into a second
  source of truth that drifts from the records it was derived from. The twin
  lives only for the duration of the request that asked for it.
* **Not a sensor or IoT twin.** Nothing here reads live telemetry. There are no
  wearables, no devices, and no real-time feeds. The input is exactly what a
  user or veterinarian has entered into the database.
* **Not a diagnosis or a recommendation.** This module performs no inference.
  It does not score risk, suggest treatment, or judge whether a pet is healthy.
  It reports recorded facts, plus simple date arithmetic (age, overdue count)
  that involves no clinical judgement.

Where the facts come from
-------------------------
``pets`` holds identity. Everything health-related is derived from the clinical
record tables, so each fact has exactly one home:

* existing conditions  <- ``diagnosis_records`` with status active/chronic
* current medications  <- ``medication_records`` that are still active
* vaccination status   <- ``vaccination_records`` compared against their due date
* current symptoms     <- ``symptom_records`` that have not resolved
* timeline             <- ``timeline_service.build_health_timeline``

Passing the resulting mapping to a future agent as context is a Phase 4+
concern; this module only guarantees the shape is suitable for it.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.allergy import PetAllergy
from app.models.base import (
    DiagnosisStatus,
    SourceType,
    VerificationStatus,
)
from app.models.diagnosis import DiagnosisRecord
from app.models.health_record import HealthRecord
from app.models.lab_report import LabReport
from app.models.medication import MedicationRecord
from app.models.pet import Pet
from app.models.symptom import SymptomRecord
from app.models.vaccination import VaccinationRecord
from app.models.visit import VeterinaryVisit
from app.services.authorization import get_active_access
from app.services.timeline_service import build_health_timeline

#: Attached to every twin payload so the boundary travels with the data. A
#: future agent receiving this as context sees the limit stated in the payload
#: itself, not only in documentation.
TWIN_DISCLAIMER = (
    "Software-based Digital Twin assembled from recorded veterinary records. "
    "Not sensor-based and not real-time. It restates verified facts and derives "
    "only counts and date arithmetic; interpreting them is the veterinarian's job."
)

#: A condition that has not been marked resolved is treated as ongoing.
ONGOING_DIAGNOSIS_STATUSES = (DiagnosisStatus.ACTIVE, DiagnosisStatus.CHRONIC)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_from_dob(dob: date, today: date) -> dict:
    """Compute an age breakdown from a date of birth using calendar arithmetic."""
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    months_total = (today.year - dob.year) * 12 + (today.month - dob.month)
    if today.day < dob.day:
        months_total -= 1
    months_total = max(months_total, 0)
    return {
        "years": years,
        "months": months_total % 12,
        "total_months": months_total,
        "approximate": False,
    }


def _age_from_months(months: int) -> dict:
    return {
        "years": months // 12,
        "months": months % 12,
        "total_months": months,
        "approximate": True,
    }


def compute_age(pet: Pet, today: date) -> dict | None:
    """Derive the pet's age from whichever field the owner supplied.

    A date of birth is exact. ``estimated_age_months`` is an owner's estimate
    and is reported as approximate so a downstream consumer does not treat it
    with the same confidence.
    """
    if pet.date_of_birth is not None:
        return _age_from_dob(pet.date_of_birth, today)
    if pet.estimated_age_months is not None:
        return _age_from_months(pet.estimated_age_months)
    return None


#: Child record types carry no ``verification_status`` column of their own. Their
#: state is inherited from the parent ``health_records`` row, so verification has
#: to be counted and filtered through a join rather than read off the child. This
#: is also why ``?verified_only=true`` on a child list endpoint filters via the
#: parent.
#:
#: ``DiagnosisRecord`` belongs here too — without it, counting diagnoses would
#: fall through to :func:`_verified_clause` and raise ``AttributeError``.
#: ``VeterinaryVisit`` and ``PetAllergy`` are *not* children: they hold their own
#: provenance column, so they are filtered directly.
CHILD_TYPES = (
    SymptomRecord,
    DiagnosisRecord,
    MedicationRecord,
    VaccinationRecord,
    LabReport,
)

#: Models that carry their own ``verification_status`` column.
SELF_VERIFIED_TYPES = (HealthRecord, VeterinaryVisit, PetAllergy)


def _verified_clause(model):
    """``verification_status == verified`` for any ProvenanceMixin model."""
    return model.verification_status == VerificationStatus.VERIFIED


def build_digital_twin(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Assemble the full Digital Twin for a pet.

    The caller is expected to have already authorized access to this pet (via
    :func:`load_accessible_pet` or equivalent). This function re-reads the
    access grant only to report the caller's role in the payload.
    """
    now = _now()
    today = now.date()

    pet = db.get(Pet, pet_id)
    if pet is None:
        raise ValueError(f"Pet {pet_id} does not exist")

    access = get_active_access(db, pet_id=pet_id, user_id=user_id)

    # --- allergies (stored on their own table) ----------------------------
    # An unconfirmed sensitivity is not part of the pet's health state, so it is
    # excluded here exactly as an unverified diagnosis is. It remains readable
    # through the allergy endpoint.
    allergies = (
        db.execute(
            select(PetAllergy)
            .where(
                PetAllergy.pet_id == pet_id,
                PetAllergy.is_active.is_(True),
                _verified_clause(PetAllergy),
            )
            .order_by(PetAllergy.allergen)
        )
        .scalars()
        .all()
    )

    # --- existing conditions: derived from diagnoses ----------------------
    # Verification is inherited from the parent health record, hence the join.
    diagnoses = (
        db.execute(
            select(DiagnosisRecord)
            .join(
                HealthRecord, DiagnosisRecord.health_record_id == HealthRecord.id
            )
            .where(
                DiagnosisRecord.pet_id == pet_id,
                DiagnosisRecord.status.in_(ONGOING_DIAGNOSIS_STATUSES),
                DiagnosisRecord.resolved_at.is_(None),
                HealthRecord.verification_status == VerificationStatus.VERIFIED,
            )
            .order_by(DiagnosisRecord.diagnosed_at.desc())
        )
        .scalars()
        .all()
    )

    # --- current medications: still running --------------------------------
    medications = (
        db.execute(
            select(MedicationRecord)
            .join(
                HealthRecord, MedicationRecord.health_record_id == HealthRecord.id
            )
            .where(
                MedicationRecord.pet_id == pet_id,
                MedicationRecord.is_active.is_(True),
                HealthRecord.verification_status == VerificationStatus.VERIFIED,
                (MedicationRecord.ended_at.is_(None))
                | (MedicationRecord.ended_at > now),
            )
            .order_by(MedicationRecord.started_at.desc())
        )
        .scalars()
        .all()
    )

    # --- vaccination status: derived, never stored -------------------------
    # The status is *derived* from the latest dose of each vaccine, which makes
    # it a claim about the pet rather than a raw record. Deriving it from
    # unverified doses would let a not-yet-confirmed entry flip the pet to
    # "overdue" or "up to date", so only verified doses are considered.
    vaccinations = (
        db.execute(
            select(VaccinationRecord)
            .join(
                HealthRecord, VaccinationRecord.health_record_id == HealthRecord.id
            )
            .where(
                VaccinationRecord.pet_id == pet_id,
                HealthRecord.verification_status == VerificationStatus.VERIFIED,
            )
            .order_by(VaccinationRecord.administered_at.desc())
        )
        .scalars()
        .all()
    )
    latest_per_vaccine: dict[str, VaccinationRecord] = {}
    for vac in vaccinations:
        latest_per_vaccine.setdefault(vac.vaccine_name, vac)

    overdue = [
        v
        for v in latest_per_vaccine.values()
        if v.next_due_at is not None and v.next_due_at < now
    ]
    upcoming = [
        v
        for v in latest_per_vaccine.values()
        if v.next_due_at is not None and v.next_due_at >= now
    ]
    if not latest_per_vaccine:
        vaccination_status = "none_recorded"
    elif overdue:
        vaccination_status = "overdue"
    elif upcoming:
        vaccination_status = "up_to_date"
    else:
        vaccination_status = "recorded_no_due_date"

    # --- current symptoms: not yet resolved --------------------------------
    symptoms = (
        db.execute(
            select(SymptomRecord, HealthRecord.verification_status)
            .join(HealthRecord, SymptomRecord.health_record_id == HealthRecord.id)
            .where(
                SymptomRecord.pet_id == pet_id,
                SymptomRecord.resolved_at.is_(None),
            )
            .order_by(SymptomRecord.onset_at.desc().nullslast())
        )
        .all()
    )
    current_symptoms = [s for s, vstat in symptoms if vstat == VerificationStatus.VERIFIED]

    # --- recent history: latest verified health records --------------------
    recent_records = (
        db.execute(
            select(HealthRecord)
            .where(
                HealthRecord.pet_id == pet_id,
                _verified_clause(HealthRecord),
            )
            .order_by(HealthRecord.occurred_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    visits = (
        db.execute(
            select(VeterinaryVisit)
            .where(
                VeterinaryVisit.pet_id == pet_id,
                _verified_clause(VeterinaryVisit),
            )
            .order_by(VeterinaryVisit.visit_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    # Filtering happens in SQL rather than in Python so that ``LIMIT`` is applied
    # after verification; filtering afterwards could return fewer than ``limit``
    # rows purely because the first page was full of unverified entries.
    labs = (
        db.execute(
            select(LabReport)
            .join(HealthRecord, LabReport.health_record_id == HealthRecord.id)
            .where(
                LabReport.pet_id == pet_id,
                HealthRecord.verification_status == VerificationStatus.VERIFIED,
            )
            .order_by(LabReport.performed_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    # --- provenance: how much of this is verified --------------------------
    def count_verified(model) -> int:
        if model in CHILD_TYPES:
            # Verification lives on the parent health record.
            return db.execute(
                select(func.count())
                .select_from(model)
                .join(HealthRecord, model.health_record_id == HealthRecord.id)
                .where(
                    model.pet_id == pet_id,
                    HealthRecord.verification_status == VerificationStatus.VERIFIED,
                )
            ).scalar_one()
        return db.execute(
            select(func.count())
            .select_from(model)
            .where(model.pet_id == pet_id, _verified_clause(model))
        ).scalar_one()

    def count_total(model) -> int:
        return db.execute(
            select(func.count()).select_from(model).where(model.pet_id == pet_id)
        ).scalar_one()

    timeline = build_health_timeline(db, pet_id=pet_id, verified_only=True, limit=100)

    # The two "current" lists are built once and surfaced both under
    # current_health_status and as named top-level sections, so the two views
    # can never disagree.
    current_symptom_items = [
        {
            "id": str(s.id),
            "name": s.symptom_name,
            "severity": s.severity,
            "onset_at": s.onset_at,
            "is_chronic": s.is_chronic,
            "description": s.description,
        }
        for s in current_symptoms
    ]
    current_medication_items = [
        {
            "id": str(m.id),
            "name": m.medication_name,
            "dose": (
                f"{m.dose_amount} {m.dose_unit}".strip() if m.dose_amount else None
            ),
            "route": m.route,
            "frequency": m.frequency,
            "started_at": m.started_at,
            "instructions": m.instructions,
        }
        for m in medications
    ]

    return {
        "pet_id": str(pet.id),
        "generated_at": now,
        "disclaimer": TWIN_DISCLAIMER,
        "twin_type": "software_based_record_assembly",
        "viewer_role": access.role.value if access else None,
        "profile": {
            "id": str(pet.id),
            "name": pet.name,
            "species": pet.species.value,
            "breed": pet.breed,
            "sex": pet.sex.value,
            "is_neutered": pet.is_neutered,
            "color": pet.color,
            "microchip_id": pet.microchip_id,
            "date_of_birth": pet.date_of_birth,
            "age": compute_age(pet, today),
            "current_weight_kg": pet.current_weight_kg,
            "is_alive": pet.is_alive,
            "notes": pet.notes,
            "source_type": pet.source_type.value,
            "verification_status": pet.verification_status.value,
            "created_at": pet.created_at,
        },
        "current_health_status": {
            "existing_conditions": [
                {
                    "id": str(d.id),
                    "name": d.diagnosis_name,
                    "icd10_code": d.icd10_code,
                    "status": d.status.value,
                    "is_confirmed": d.is_confirmed,
                    "diagnosed_at": d.diagnosed_at,
                }
                for d in diagnoses
            ],
            "current_symptoms": current_symptom_items,
            "current_medications": current_medication_items,
            "allergies": [
                {
                    "id": str(a.id),
                    "allergen": a.allergen,
                    "reaction": a.reaction,
                    "severity": a.severity,
                    "onset_at": a.onset_at,
                }
                for a in allergies
            ],
            "vaccination_status": {
                "status": vaccination_status,
                "vaccines_tracked": len(latest_per_vaccine),
                "overdue_count": len(overdue),
                "overdue": [
                    {
                        "vaccine": v.vaccine_name,
                        "last_given": v.administered_at,
                        "next_due": v.next_due_at,
                    }
                    for v in sorted(overdue, key=lambda x: x.next_due_at)
                ],
                "upcoming": [
                    {
                        "vaccine": v.vaccine_name,
                        "last_given": v.administered_at,
                        "next_due": v.next_due_at,
                    }
                    for v in sorted(upcoming, key=lambda x: x.next_due_at)
                ],
            },
            "weight_kg": pet.current_weight_kg,
            "last_visit_at": visits[0].visit_at if visits else None,
        },
        "medical_history": [
            {
                "id": str(r.id),
                "record_type": r.record_type.value,
                "title": r.title,
                "occurred_at": r.occurred_at,
                "clinic_name": r.clinic_name,
                "verified_at": r.verified_at,
            }
            for r in recent_records
        ],
        "diagnoses": [
            {
                "id": str(d.id),
                "name": d.diagnosis_name,
                "status": d.status.value,
                "is_confirmed": d.is_confirmed,
                "diagnosed_at": d.diagnosed_at,
                "resolved_at": d.resolved_at,
            }
            for d in diagnoses
        ],
        "current_symptoms": current_symptom_items,
        "current_medications": current_medication_items,
        "medications": [
            {
                "id": str(m.id),
                "name": m.medication_name,
                "is_active": m.is_active,
                "started_at": m.started_at,
                "ended_at": m.ended_at,
            }
            for m in medications
        ],
        "vaccinations": [
            {
                "id": str(v.id),
                "vaccine": v.vaccine_name,
                "administered_at": v.administered_at,
                "next_due_at": v.next_due_at,
                "is_booster": v.is_booster,
                "clinic_name": v.clinic_name,
            }
            for v in vaccinations
        ],
        "laboratory_results": [
            {
                "id": str(l.id),
                "test_name": l.test_name,
                "test_category": l.test_category,
                "result": (
                    f"{l.result_value} {l.unit}".strip()
                    if l.result_value is not None
                    else l.result_text
                ),
                "reference_low": l.reference_range_low,
                "reference_high": l.reference_range_high,
                "is_abnormal": l.is_abnormal,
                "performed_at": l.performed_at,
                "lab_name": l.lab_name,
            }
            for l in labs
        ],
        "veterinary_visits": [
            {
                "id": str(v.id),
                "visit_at": v.visit_at,
                "visit_type": v.visit_type.value,
                "status": v.status.value,
                "clinic_name": v.clinic_name,
                "veterinarian_name": v.veterinarian_name,
                "reason_for_visit": v.reason_for_visit,
                "follow_up_at": v.follow_up_at,
            }
            for v in visits
        ],
        "health_timeline": timeline,
        "provenance": {
            "verified_counts": {
                "health_records": count_verified(HealthRecord),
                "diagnosis_records": count_verified(DiagnosisRecord),
                "symptom_records": count_verified(SymptomRecord),
                "medication_records": count_verified(MedicationRecord),
                "vaccination_records": count_verified(VaccinationRecord),
                "lab_reports": count_verified(LabReport),
                "veterinary_visits": count_verified(VeterinaryVisit),
                "pet_allergies": count_verified(PetAllergy),
            },
            "total_counts": {
                "health_records": count_total(HealthRecord),
                "diagnosis_records": count_total(DiagnosisRecord),
                "symptom_records": count_total(SymptomRecord),
                "medication_records": count_total(MedicationRecord),
                "vaccination_records": count_total(VaccinationRecord),
                "lab_reports": count_total(LabReport),
                "veterinary_visits": count_total(VeterinaryVisit),
                "pet_allergies": count_total(PetAllergy),
            },
            "excluded_source_types": [SourceType.AI_ANALYSIS.value],
        },
    }
