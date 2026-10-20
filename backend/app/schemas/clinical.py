"""Pydantic schemas for the seven clinical record types.

Every create schema here produces a row that belongs to a pet. The pet is taken
from the URL path, never from the body, so a client cannot file a record against
a pet it does not own.
"""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.base import (
    DiagnosisStatus,
    HealthRecordType,
    SourceType,
    VerificationStatus,
    VisitStatus,
    VisitType,
)

Severity = Annotated[int, Field(ge=1, le=5)]
PositiveInt = Annotated[int, Field(gt=0)]


class _RequireOneFieldMixin(BaseModel):
    def model_post_init(self, _context) -> None:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one field must be provided")


# ---------------------------------------------------------------------------
# Veterinary visit
# ---------------------------------------------------------------------------
class VisitCreate(BaseModel):
    visit_at: datetime
    visit_type: VisitType = VisitType.WELLNESS
    status: VisitStatus = VisitStatus.COMPLETED
    clinic_name: str | None = Field(default=None, max_length=200)
    veterinarian_name: str | None = Field(default=None, max_length=200)
    reason_for_visit: str | None = Field(default=None, max_length=500)
    chief_complaint: str | None = None
    clinical_summary: str | None = None
    follow_up_at: datetime | None = None
    #: A completed encounter at a named clinic is normally filed as verified, so
    #: the flag is settable at creation rather than requiring a follow-up PATCH.
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_type: SourceType = SourceType.MANUAL_ENTRY
    notes: str | None = None


class VisitUpdate(_RequireOneFieldMixin):
    visit_at: datetime | None = None
    visit_type: VisitType | None = None
    status: VisitStatus | None = None
    clinic_name: str | None = Field(default=None, max_length=200)
    veterinarian_name: str | None = Field(default=None, max_length=200)
    reason_for_visit: str | None = Field(default=None, max_length=500)
    chief_complaint: str | None = None
    clinical_summary: str | None = None
    follow_up_at: datetime | None = None
    verification_status: VerificationStatus | None = None
    notes: str | None = None


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pet_id: uuid.UUID
    visit_at: datetime
    visit_type: VisitType
    status: VisitStatus
    clinic_name: str | None
    veterinarian_name: str | None
    reason_for_visit: str | None
    chief_complaint: str | None
    clinical_summary: str | None
    follow_up_at: datetime | None
    source_type: SourceType
    verification_status: VerificationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Health record
# ---------------------------------------------------------------------------
class HealthRecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    record_type: HealthRecordType = HealthRecordType.OTHER
    occurred_at: datetime
    visit_id: uuid.UUID | None = None
    clinic_name: str | None = Field(default=None, max_length=200)
    external_reference: str | None = Field(default=None, max_length=120)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_type: SourceType = SourceType.MANUAL_ENTRY
    notes: str | None = None


class HealthRecordUpdate(_RequireOneFieldMixin):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    record_type: HealthRecordType | None = None
    occurred_at: datetime | None = None
    visit_id: uuid.UUID | None = None
    clinic_name: str | None = Field(default=None, max_length=200)
    external_reference: str | None = Field(default=None, max_length=120)
    verification_status: VerificationStatus | None = None
    notes: str | None = None


class HealthRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pet_id: uuid.UUID
    visit_id: uuid.UUID | None
    record_type: HealthRecordType
    title: str
    occurred_at: datetime
    clinic_name: str | None
    external_reference: str | None
    verified_at: datetime | None
    source_type: SourceType
    verification_status: VerificationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Symptom
# ---------------------------------------------------------------------------
class SymptomCreate(BaseModel):
    health_record_id: uuid.UUID
    symptom_name: str = Field(min_length=1, max_length=200)
    severity: Severity | None = None
    onset_at: datetime | None = None
    resolved_at: datetime | None = None
    is_chronic: bool = False
    observed_by: str | None = Field(default=None, max_length=120)
    description: str | None = None
    normalized_code: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _resolved_after_onset(self) -> "SymptomCreate":
        if (
            self.onset_at is not None
            and self.resolved_at is not None
            and self.resolved_at < self.onset_at
        ):
            raise ValueError("resolved_at cannot be before onset_at")
        return self


class SymptomUpdate(_RequireOneFieldMixin):
    symptom_name: str | None = Field(default=None, min_length=1, max_length=200)
    severity: Severity | None = None
    onset_at: datetime | None = None
    resolved_at: datetime | None = None
    is_chronic: bool | None = None
    observed_by: str | None = Field(default=None, max_length=120)
    description: str | None = None
    normalized_code: str | None = Field(default=None, max_length=64)


class SymptomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_record_id: uuid.UUID
    pet_id: uuid.UUID
    symptom_name: str
    severity: int | None
    onset_at: datetime | None
    resolved_at: datetime | None
    is_chronic: bool
    observed_by: str | None
    description: str | None
    normalized_code: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------
class DiagnosisCreate(BaseModel):
    health_record_id: uuid.UUID
    diagnosis_name: str = Field(min_length=1, max_length=250)
    icd10_code: str | None = Field(default=None, max_length=16)
    status: DiagnosisStatus = DiagnosisStatus.ACTIVE
    diagnosed_at: datetime
    resolved_at: datetime | None = None
    is_confirmed: bool = False
    diagnosed_by_name: str | None = Field(default=None, max_length=200)
    description: str | None = None

    @model_validator(mode="after")
    def _resolved_after_diagnosis(self) -> "DiagnosisCreate":
        if self.resolved_at is not None and self.resolved_at < self.diagnosed_at:
            raise ValueError("resolved_at cannot be before diagnosed_at")
        return self

    @model_validator(mode="after")
    def _resolved_needs_inactive_status(self) -> "DiagnosisCreate":
        if self.resolved_at is not None and self.status in (
            DiagnosisStatus.ACTIVE,
            DiagnosisStatus.CHRONIC,
        ):
            raise ValueError(
                "a resolved diagnosis must have status 'resolved' or 'ruled_out'"
            )
        return self


class DiagnosisUpdate(_RequireOneFieldMixin):
    diagnosis_name: str | None = Field(default=None, min_length=1, max_length=250)
    icd10_code: str | None = Field(default=None, max_length=16)
    status: DiagnosisStatus | None = None
    diagnosed_at: datetime | None = None
    resolved_at: datetime | None = None
    is_confirmed: bool | None = None
    diagnosed_by_name: str | None = Field(default=None, max_length=200)
    description: str | None = None


class DiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_record_id: uuid.UUID
    pet_id: uuid.UUID
    diagnosis_name: str
    icd10_code: str | None
    status: DiagnosisStatus
    diagnosed_at: datetime
    resolved_at: datetime | None
    is_confirmed: bool
    diagnosed_by_name: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Medication
# ---------------------------------------------------------------------------
class MedicationCreate(BaseModel):
    health_record_id: uuid.UUID
    medication_name: str = Field(min_length=1, max_length=250)
    dose_amount: float | None = Field(default=None, gt=0)
    dose_unit: str | None = Field(default=None, max_length=32)
    route: str | None = Field(default=None, max_length=64)
    frequency: str | None = Field(default=None, max_length=120)
    started_at: datetime
    ended_at: datetime | None = None
    is_active: bool = True
    prescribed_by_name: str | None = Field(default=None, max_length=200)
    instructions: str | None = None

    @model_validator(mode="after")
    def _ended_after_start(self) -> "MedicationCreate":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be before started_at")
        return self


class MedicationUpdate(_RequireOneFieldMixin):
    medication_name: str | None = Field(default=None, min_length=1, max_length=250)
    dose_amount: float | None = Field(default=None, gt=0)
    dose_unit: str | None = Field(default=None, max_length=32)
    route: str | None = Field(default=None, max_length=64)
    frequency: str | None = Field(default=None, max_length=120)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    is_active: bool | None = None
    prescribed_by_name: str | None = Field(default=None, max_length=200)
    instructions: str | None = None


class MedicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_record_id: uuid.UUID
    pet_id: uuid.UUID
    medication_name: str
    dose_amount: float | None
    dose_unit: str | None
    route: str | None
    frequency: str | None
    started_at: datetime
    ended_at: datetime | None
    is_active: bool
    prescribed_by_name: str | None
    instructions: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Vaccination
# ---------------------------------------------------------------------------
class VaccinationCreate(BaseModel):
    health_record_id: uuid.UUID
    vaccine_name: str = Field(min_length=1, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=200)
    batch_number: str | None = Field(default=None, max_length=120)
    administered_at: datetime
    next_due_at: datetime | None = None
    is_booster: bool = False
    route: str | None = Field(default=None, max_length=64)
    clinic_name: str | None = Field(default=None, max_length=200)
    notes: str | None = None

    @model_validator(mode="after")
    def _due_after_administered(self) -> "VaccinationCreate":
        if self.next_due_at is not None and self.next_due_at < self.administered_at:
            raise ValueError("next_due_at cannot be before administered_at")
        return self


class VaccinationUpdate(_RequireOneFieldMixin):
    vaccine_name: str | None = Field(default=None, min_length=1, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=200)
    batch_number: str | None = Field(default=None, max_length=120)
    administered_at: datetime | None = None
    next_due_at: datetime | None = None
    is_booster: bool | None = None
    route: str | None = Field(default=None, max_length=64)
    clinic_name: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class VaccinationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_record_id: uuid.UUID
    pet_id: uuid.UUID
    vaccine_name: str
    manufacturer: str | None
    batch_number: str | None
    administered_at: datetime
    next_due_at: datetime | None
    is_booster: bool
    route: str | None
    clinic_name: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Lab report
# ---------------------------------------------------------------------------
class LabReportCreate(BaseModel):
    health_record_id: uuid.UUID
    test_name: str = Field(min_length=1, max_length=200)
    test_category: str | None = Field(default=None, max_length=120)
    result_value: float | None = None
    result_text: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=64)
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    performed_at: datetime
    lab_name: str | None = Field(default=None, max_length=200)
    interpretation: str | None = None

    @model_validator(mode="after")
    def _range_is_ordered(self) -> "LabReportCreate":
        low, high = self.reference_range_low, self.reference_range_high
        if low is not None and high is not None and low > high:
            raise ValueError("reference_range_low cannot exceed reference_range_high")
        return self

    @model_validator(mode="after")
    def _has_a_result(self) -> "LabReportCreate":
        if self.result_value is None and self.result_text is None:
            raise ValueError("supply result_value or result_text")
        return self


class LabReportUpdate(_RequireOneFieldMixin):
    test_name: str | None = Field(default=None, min_length=1, max_length=200)
    test_category: str | None = Field(default=None, max_length=120)
    result_value: float | None = None
    result_text: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=64)
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    performed_at: datetime | None = None
    lab_name: str | None = Field(default=None, max_length=200)
    interpretation: str | None = None


class LabReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_record_id: uuid.UUID
    pet_id: uuid.UUID
    test_name: str
    test_category: str | None
    result_value: float | None
    result_text: str | None
    unit: str | None
    reference_range_low: float | None
    reference_range_high: float | None
    is_abnormal: bool | None
    performed_at: datetime
    lab_name: str | None
    interpretation: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedRecords(BaseModel):
    """Uniform list envelope so the frontend can paginate every record type."""

    items: list[dict]
    total: int
    limit: int
    offset: int
