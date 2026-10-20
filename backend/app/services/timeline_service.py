"""Health timeline assembly.

The timeline is a *derived view*, not a stored one. It is produced by merging
two independent sources and sorting the result:

1. **Structured clinical records** — visits, diagnoses, symptoms, medications,
   vaccinations and lab results, each of which already carries its own
   ``occurred_at``.
2. **Narrative log entries** — rows in ``health_timeline_events``, which capture
   things that do not correspond to a typed record (a weight change, an owner
   note).

Why derive rather than auto-insert on write
-------------------------------------------
An earlier option was to have every record-creation endpoint also insert a
``health_timeline_events`` row. That was rejected: the inserted row would be a
second copy of a fact that already exists in the record table. The two could
then disagree — a record edited or deleted would leave a stale timeline entry
behind, which is exactly the drift problem the schema docstrings warn against.

Because the timeline is computed per request from the records themselves, it is
current by construction. Adding a record and reloading the page is all that is
required for the timeline to include it; there is no cache to invalidate and no
synchronisation step to forget.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.base import VerificationStatus
from app.models.diagnosis import DiagnosisRecord
from app.models.lab_report import LabReport
from app.models.medication import MedicationRecord
from app.models.symptom import SymptomRecord
from app.models.timeline import HealthTimelineEvent
from app.models.vaccination import VaccinationRecord
from app.models.visit import VeterinaryVisit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sort_key(item: dict) -> datetime:
    return item["occurred_at"]


def build_health_timeline(
    db: Session,
    *,
    pet_id: uuid.UUID,
    verified_only: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Merge every recorded clinical event for a pet into one reverse-chronological list.

    ``verified_only`` restricts the result to records whose
    ``verification_status`` is ``verified``. Unverified records are still real
    records the user entered, so they remain retrievable — they are simply
    labelled and can be filtered out.

    Two consequences of the schema are worth stating explicitly, because both
    would otherwise let unconfirmed input masquerade as established history:

    * **Narrative entries are excluded when ``verified_only`` is set.**
      ``health_timeline_events`` has no ``verification_status`` column, so a
      narrative entry can never satisfy a "verified only" request. Including it
      would present an owner's note as clinician-confirmed history. Because a
      silent drop would be confusing, the frontend exposes a toggle that turns
      ``verified_only`` off; nothing becomes unreachable.
    * **Diagnoses, medications and vaccinations inherit verification** from the
      parent ``health_records`` row, so they are filtered through that
      relationship rather than a column of their own.
    """
    events: list[dict] = []
    vfilter = VerificationStatus.VERIFIED if verified_only else None

    def keep(status_value: VerificationStatus) -> bool:
        return vfilter is None or status_value == vfilter

    # --- narrative log entries -------------------------------------------
    if vfilter is None:
        narrative = db.execute(
            select(HealthTimelineEvent)
            .where(HealthTimelineEvent.pet_id == pet_id)
            .order_by(HealthTimelineEvent.occurred_at.desc())
        ).scalars()
        for row in narrative:
            events.append(
                {
                    "event_type": row.event_type.value,
                    "occurred_at": row.occurred_at,
                    "title": row.title,
                    "description": row.description,
                    "severity": row.severity,
                    "source_table": row.source_table or "health_timeline_events",
                    "source_id": row.id,
                }
            )

    # --- veterinary visits ------------------------------------------------
    visits = db.execute(
        select(VeterinaryVisit).where(VeterinaryVisit.pet_id == pet_id)
    ).scalars()
    for v in visits:
        if not keep(v.verification_status):
            continue
        events.append(
            {
                "event_type": "visit",
                "occurred_at": v.visit_at,
                "title": f"{v.visit_type.value.replace('_', ' ').title()} visit",
                "description": v.reason_for_visit or v.clinical_summary,
                "severity": None,
                "source_table": "veterinary_visits",
                "source_id": v.id,
            }
        )

    # --- diagnoses --------------------------------------------------------
    diagnoses = db.execute(
        select(DiagnosisRecord)
        .where(DiagnosisRecord.pet_id == pet_id)
        .options(selectinload(DiagnosisRecord.health_record))
    ).scalars()
    for d in diagnoses:
        if not keep(d.health_record.verification_status):
            continue
        events.append(
            {
                "event_type": "diagnosis",
                "occurred_at": d.diagnosed_at,
                "title": d.diagnosis_name,
                "description": (
                    f"{d.status.value}{' (confirmed)' if d.is_confirmed else ''}"
                ),
                "severity": None,
                "source_table": "diagnosis_records",
                "source_id": d.id,
            }
        )

    # --- symptoms ---------------------------------------------------------
    symptoms = db.execute(
        select(SymptomRecord)
        .where(SymptomRecord.pet_id == pet_id)
        .options(selectinload(SymptomRecord.health_record))
    ).scalars()
    for s in symptoms:
        if not keep(s.health_record.verification_status):
            continue
        events.append(
            {
                "event_type": "symptom",
                "occurred_at": s.onset_at or s.created_at,
                "title": s.symptom_name,
                "description": s.description,
                "severity": s.severity,
                "source_table": "symptom_records",
                "source_id": s.id,
            }
        )

    # --- medications ------------------------------------------------------
    meds = db.execute(
        select(MedicationRecord)
        .where(MedicationRecord.pet_id == pet_id)
        .options(selectinload(MedicationRecord.health_record))
    ).scalars()
    for m in meds:
        if not keep(m.health_record.verification_status):
            continue
        # A stop is its own event so the timeline shows the course end, not
        # just the start.
        events.append(
            {
                "event_type": "medication_started",
                "occurred_at": m.started_at,
                "title": m.medication_name,
                "description": (
                    f"{m.dose_amount or ''} {m.dose_unit or ''} {m.frequency or ''}"
                ).strip()
                or None,
                "severity": None,
                "source_table": "medication_records",
                "source_id": m.id,
            }
        )
        if m.ended_at is not None:
            events.append(
                {
                    "event_type": "medication_stopped",
                    "occurred_at": m.ended_at,
                    "title": f"{m.medication_name} stopped",
                    "description": m.instructions,
                    "severity": None,
                    "source_table": "medication_records",
                    "source_id": m.id,
                }
            )

    # --- vaccinations -----------------------------------------------------
    vacs = db.execute(
        select(VaccinationRecord)
        .where(VaccinationRecord.pet_id == pet_id)
        .options(selectinload(VaccinationRecord.health_record))
    ).scalars()
    for vac in vacs:
        if not keep(vac.health_record.verification_status):
            continue
        events.append(
            {
                "event_type": "vaccination",
                "occurred_at": vac.administered_at,
                "title": vac.vaccine_name,
                "description": (
                    f"next due {vac.next_due_at.date().isoformat()}"
                    if vac.next_due_at
                    else vac.notes
                ),
                "severity": None,
                "source_table": "vaccination_records",
                "source_id": vac.id,
            }
        )

    # --- lab results ------------------------------------------------------
    labs = db.execute(
        select(LabReport)
        .where(LabReport.pet_id == pet_id)
        .options(selectinload(LabReport.health_record))
    ).scalars()
    for lab in labs:
        if not keep(lab.health_record.verification_status):
            continue
        value = (
            f"{lab.result_value} {lab.unit}".strip()
            if lab.result_value is not None
            else lab.result_text
        )
        events.append(
            {
                "event_type": "lab_result",
                "occurred_at": lab.performed_at,
                "title": lab.test_name,
                "description": value,
                "severity": None,
                "source_table": "lab_reports",
                "source_id": lab.id,
            }
        )

    events.sort(key=_sort_key, reverse=True)
    if limit is not None:
        events = events[:limit]
    # Ids are stringified here so the timeline serialises identically whether it
    # is returned inside the twin or on its own.
    for event in events:
        if event["source_id"] is not None:
            event["source_id"] = str(event["source_id"])
    return events
