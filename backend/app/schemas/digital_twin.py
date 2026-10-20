"""Pydantic schemas for the Digital Twin and health timeline responses.

The twin is returned as an explicitly typed structure rather than a loose dict so
that (a) the shape is documented in OpenAPI, and (b) a typo in the service
fails at import time instead of silently omitting a section.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class TwinAge(BaseModel):
    years: int
    months: int
    total_months: int
    approximate: bool = Field(
        description="True when derived from an owner estimate, not a birth date"
    )


class TwinProfile(BaseModel):
    id: str
    name: str
    species: str
    breed: str | None = None
    sex: str
    is_neutered: bool
    color: str | None = None
    microchip_id: str | None = None
    date_of_birth: date | None = None
    age: TwinAge | None = None
    current_weight_kg: float | None = None
    is_alive: bool
    notes: str | None = None
    source_type: str
    verification_status: str
    created_at: datetime


class TwinCondition(BaseModel):
    id: str
    name: str
    icd10_code: str | None = None
    status: str
    is_confirmed: bool
    diagnosed_at: datetime


class TwinSymptom(BaseModel):
    id: str
    name: str
    severity: int | None = None
    onset_at: datetime | None = None
    is_chronic: bool
    description: str | None = None


class TwinMedication(BaseModel):
    id: str
    name: str
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    started_at: datetime
    instructions: str | None = None


class TwinAllergy(BaseModel):
    id: str
    allergen: str
    reaction: str | None = None
    severity: int | None = None
    onset_at: datetime | None = None


class TwinVaccineDue(BaseModel):
    vaccine: str
    last_given: datetime
    next_due: datetime


class TwinVaccinationStatus(BaseModel):
    status: str = Field(
        description=(
            "Derived by comparing the latest dose of each vaccine against its "
            "stored next_due_at. One of: none_recorded, up_to_date, overdue, "
            "recorded_no_due_date. Not a clinical judgement."
        )
    )
    vaccines_tracked: int
    overdue_count: int
    overdue: list[TwinVaccineDue]
    upcoming: list[TwinVaccineDue]


class TwinCurrentHealthStatus(BaseModel):
    existing_conditions: list[TwinCondition]
    current_symptoms: list[TwinSymptom]
    current_medications: list[TwinMedication]
    allergies: list[TwinAllergy]
    vaccination_status: TwinVaccinationStatus
    weight_kg: float | None = None
    last_visit_at: datetime | None = None


class TwinMedicalHistoryEntry(BaseModel):
    id: str
    record_type: str
    title: str
    occurred_at: datetime
    clinic_name: str | None = None
    verified_at: datetime | None = None


class TwinDiagnosis(BaseModel):
    id: str
    name: str
    status: str
    is_confirmed: bool
    diagnosed_at: datetime
    resolved_at: datetime | None = None


class TwinMedicationHistory(BaseModel):
    id: str
    name: str
    is_active: bool
    started_at: datetime
    ended_at: datetime | None = None


class TwinVaccination(BaseModel):
    id: str
    vaccine: str
    administered_at: datetime
    next_due_at: datetime | None = None
    is_booster: bool
    clinic_name: str | None = None


class TwinLabResult(BaseModel):
    id: str
    test_name: str
    test_category: str | None = None
    result: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    is_abnormal: bool | None = None
    performed_at: datetime
    lab_name: str | None = None


class TwinVisit(BaseModel):
    id: str
    visit_at: datetime
    visit_type: str
    status: str
    clinic_name: str | None = None
    veterinarian_name: str | None = None
    reason_for_visit: str | None = None
    follow_up_at: datetime | None = None


class TimelineEvent(BaseModel):
    event_type: str
    occurred_at: datetime
    title: str
    description: str | None = None
    severity: int | None = None
    source_table: str
    source_id: str | None = None


class TwinProvenance(BaseModel):
    verified_counts: dict[str, int]
    total_counts: dict[str, int]
    excluded_source_types: list[str]


class DigitalTwinResponse(BaseModel):
    """Assembled health state for one pet.

    Recomputed from the database on every request. Nothing here is cached or
    persisted, so it cannot go stale relative to the records it summarises.
    """

    pet_id: str
    generated_at: datetime
    twin_type: str = Field(
        description="Always 'software_based_record_assembly' for this project"
    )
    disclaimer: str
    viewer_role: str | None = None
    profile: TwinProfile
    current_health_status: TwinCurrentHealthStatus
    medical_history: list[TwinMedicalHistoryEntry]
    diagnoses: list[TwinDiagnosis]
    #: Unresolved symptoms. The same list appears under
    #: ``current_health_status.current_symptoms``; it is repeated at the top
    #: level because it is one of the twin's named sections.
    current_symptoms: list[TwinSymptom] = Field(default_factory=list)
    #: Still-active medications. ``medications`` below is the full history.
    current_medications: list[TwinMedication] = Field(default_factory=list)
    medications: list[TwinMedicationHistory]
    vaccinations: list[TwinVaccination]
    laboratory_results: list[TwinLabResult]
    veterinary_visits: list[TwinVisit]
    health_timeline: list[TimelineEvent]
    provenance: TwinProvenance


class HealthTimelineResponse(BaseModel):
    pet_id: str
    generated_at: datetime
    verified_only: bool
    total: int
    items: list[TimelineEvent]
