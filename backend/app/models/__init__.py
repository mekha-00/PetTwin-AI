"""SQLAlchemy ORM models for the PetTwin AI backend.

Importing this package registers every model on ``Base.metadata``, which is what
``create_all()`` depends on.

The 12 entities are:

1.  ``User``                   — account and credentials
2.  ``Pet``                    — the subject of a Digital Twin
3.  ``PetAccess``              — ownership / authorization relationship
4.  ``HealthRecord``           — canonical verified record header
5.  ``SymptomRecord``          — observed clinical sign
6.  ``DiagnosisRecord``        — conclusion reached
7.  ``MedicationRecord``       — prescribed medication
8.  ``VaccinationRecord``      — vaccine administration
9.  ``LabReport``              — single test result
10. ``VeterinaryVisit``        — one clinical encounter
11. ``HealthTimelineEvent``    — append-only chronological event log
12. ``PetAllergy``             — substance the pet reacts to

There is deliberately no ``DigitalTwin`` model. See ``base.py`` for why.

Note that ``pets`` stores **identity only**. Existing conditions, current
medications and vaccination status are not columns on ``pets``; they are derived
from the record tables above by the Digital Twin service, so each fact lives in
exactly one place.
"""

from app.models.access import PetAccess
from app.models.allergy import PetAllergy
from app.models.base import (
    Base,
    DiagnosisStatus,
    HealthRecordType,
    PetAccessRole,
    Sex,
    SourceType,
    Species,
    TimelineEventType,
    TimestampMixin,
    UserRole,
    VerificationStatus,
    VisitStatus,
    VisitType,
)
from app.models.diagnosis import DiagnosisRecord
from app.models.health_record import HealthRecord
from app.models.lab_report import LabReport
from app.models.medication import MedicationRecord
from app.models.pet import Pet
from app.models.symptom import SymptomRecord
from app.models.timeline import HealthTimelineEvent
from app.models.user import User
from app.models.vaccination import VaccinationRecord
from app.models.visit import VeterinaryVisit

__all__ = [
    "Base",
    "User",
    "Pet",
    "PetAccess",
    "HealthRecord",
    "SymptomRecord",
    "DiagnosisRecord",
    "MedicationRecord",
    "VaccinationRecord",
    "LabReport",
    "VeterinaryVisit",
    "HealthTimelineEvent",
    "PetAllergy",
    "UserRole",
    "PetAccessRole",
    "Species",
    "Sex",
    "SourceType",
    "VerificationStatus",
    "HealthRecordType",
    "VisitType",
    "VisitStatus",
    "DiagnosisStatus",
    "TimelineEventType",
    "TimestampMixin",
]
