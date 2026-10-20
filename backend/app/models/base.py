"""Shared model foundations: base class, audit columns and vocabulary enums.

Digital Twin boundary
---------------------
This database stores **verified facts about a pet**: who the pet is, what was
recorded about it, when, and by whom. That is the substrate.

The **Digital Twin is not a table and is not this database.** The Digital Twin
is a service (Phase 3+) that reads these verified records and assembles the pet's
*current* health state on demand, then keeps it current as new records arrive.
Nothing here precomputes or caches that state, and no ``digital_twin`` table
exists. Adding one would freeze a moving summary into a second source of truth
that could drift from the clinical records it is derived from.

Consequently ``health_timeline_events`` is an append-only chronological *event
log* of verified facts, not a twin. It records that something happened; it does
not interpret, summarise, or reason about it.

Original records vs AI output
-----------------------------
Clinical records are the source of truth and are never overwritten by anything
a model produces. ``SourceType.AI_ANALYSIS`` exists so that machine-generated
output, when it arrives in Phase 3+, is stored in a separate ``ai_*`` table
namespace that references — but never mutates — the source record. No AI tables
are created in Phase 2.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class UserRole(str, enum.Enum):
    PET_OWNER = "pet_owner"
    VETERINARIAN = "veterinarian"
    CLINIC_STAFF = "clinic_staff"
    ADMIN = "admin"


class PetAccessRole(str, enum.Enum):
    """What a user is allowed to do with a specific pet."""

    OWNER = "owner"
    CAREGIVER = "caregiver"
    VETERINARIAN = "veterinarian"
    CLINIC = "clinic"


class Species(str, enum.Enum):
    DOG = "dog"
    CAT = "cat"
    HORSE = "horse"
    RABBIT = "rabbit"
    BIRD = "bird"
    REPTILE = "reptile"
    SMALL_MAMMAL = "small_mammal"
    OTHER = "other"


class Sex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class SourceType(str, enum.Enum):
    """Where a record came from. Distinguishes clinical fact from other origins."""

    VETERINARY_RECORD = "veterinary_record"
    OWNER_REPORT = "owner_report"
    MANUAL_ENTRY = "manual_entry"
    DATASET_IMPORT = "dataset_import"
    AI_ANALYSIS = "ai_analysis"


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class HealthRecordType(str, enum.Enum):
    CONSULTATION = "consultation"
    VACCINATION = "vaccination"
    LAB_WORK = "lab_work"
    TREATMENT = "treatment"
    TELEHEALTH = "telehealth"
    SURGERY = "surgery"
    WELLNESS_EXAM = "wellness_exam"
    OTHER = "other"


class VisitType(str, enum.Enum):
    WELLNESS = "wellness"
    SICK = "sick"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"
    VACCINATION = "vaccination"
    SURGERY = "surgery"


class VisitStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DiagnosisStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    CHRONIC = "chronic"
    RULED_OUT = "ruled_out"


class TimelineEventType(str, enum.Enum):
    PET_REGISTERED = "pet_registered"
    VISIT = "visit"
    DIAGNOSIS = "diagnosis"
    SYMPTOM = "symptom"
    MEDICATION_STARTED = "medication_started"
    MEDICATION_STOPPED = "medication_stopped"
    VACCINATION = "vaccination"
    LAB_RESULT = "lab_result"
    WEIGHT_CHANGE = "weight_change"
    NOTE = "note"


def enum_column(enum_cls: type[enum.Enum], name: str) -> Mapped:
    """Build a reusable named native-enum column."""
    return mapped_column(
        SAEnum(
            enum_cls,
            name=name,
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        )
    )


class TimestampMixin:
    """Audit timestamps applied to every table."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )


class ProvenanceMixin:
    """Provenance and verification state shared by every clinical record.

    This is what keeps original medical data separable from anything a model
    later produces: an original record always carries a human or dataset origin
    and its own verification state, so derived output can be told apart from the
    fact it was derived from.
    """

    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(
            SourceType,
            name="source_type",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SourceType.MANUAL_ENTRY,
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(
            VerificationStatus,
            name="verification_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(nullable=True)
