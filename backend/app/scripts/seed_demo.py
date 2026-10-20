"""Seed a demo owner, pet and verified history for a hosted demo.

Idempotent: running it twice does not duplicate anything. It is intended for the
public demo only, where an examiner should land on a populated Digital Twin
rather than an empty account. It uses the normal service layer and API-independent
model writes so the data is exactly what the app would create itself.

Run from the backend directory after the schema exists:

    .venv\\Scripts\\python -m app.scripts.seed_demo

Credentials (override with env vars if you like):

    DEMO_EMAIL     default demo@pettwin.example
    DEMO_PASSWORD  default Demo12345!
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, create_all
from app.core.security import hash_password
from app.models.access import PetAccess
from app.models.allergy import PetAllergy
from app.models.base import (
    HealthRecordType,
    PetAccessRole,
    SourceType,
    VerificationStatus,
)
from app.models.health_record import HealthRecord
from app.models.pet import Pet
from app.models.symptom import SymptomRecord
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_user(db: Session, *, email: str, password: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(
        email=email,
        full_name="Demo Owner",
        hashed_password=hash_password(password),
        role="pet_owner",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_pet(db: Session, *, owner: User) -> Pet:
    pet = db.execute(select(Pet).where(Pet.name == "Bella")).scalar_one_or_none()
    if pet is not None:
        return pet
    pet = Pet(
        name="Bella",
        species="dog",
        breed="Labrador",
        sex="female",
        date_of_birth=datetime(2019, 3, 10, tzinfo=timezone.utc),
        current_weight_kg=28.5,
        color="Golden",
        notes="Seed data for the hosted demo.",
    )
    db.add(pet)
    db.flush()
    return pet


def seed() -> None:
    if SessionLocal is None:
        raise SystemExit("Database is not configured; set POSTGRES_* first.")
    create_all()

    email = os.environ.get("DEMO_EMAIL", "demo@pettwin.example")
    password = os.environ.get("DEMO_PASSWORD", "Demo12345!")

    db = SessionLocal()
    try:
        owner = _get_or_create_user(db, email=email, password=password)
        pet = _get_or_create_pet(db, owner=owner)

        # Access grant (owner) if missing.
        grant = db.execute(
            select(PetAccess).where(
                PetAccess.pet_id == pet.id,
                PetAccess.user_id == owner.id,
                PetAccess.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if grant is None:
            db.add(
                PetAccess(
                    pet_id=pet.id,
                    user_id=owner.id,
                    role=PetAccessRole.OWNER,
                    granted_by_user_id=owner.id,
                    reason="seed",
                )
            )

        # A verified consultation carrying current symptoms, if none exists.
        record = db.execute(
            select(HealthRecord).where(HealthRecord.pet_id == pet.id)
        ).scalar_one_or_none()
        if record is None:
            past = _now() - timedelta(days=2)
            record = HealthRecord(
                pet_id=pet.id,
                title="Sick visit — vomiting and lethargy",
                record_type=HealthRecordType.CONSULTATION,
                occurred_at=past,
                clinic_name="Demo Veterinary Clinic",
                verification_status=VerificationStatus.VERIFIED,
                source_type=SourceType.VETERINARY_RECORD,
            )
            db.add(record)
            db.flush()

            for name, severity in (
                ("Fever", 4),
                ("Lethargy", 2),
                ("Vomiting", 3),
                ("Appetite Loss", 2),
            ):
                db.add(
                    SymptomRecord(
                        pet_id=pet.id,
                        health_record_id=record.id,
                        symptom_name=name,
                        severity=severity,
                        onset_at=past,
                        is_chronic=False,
                    )
                )

            db.add(
                PetAllergy(
                    pet_id=pet.id,
                    allergen="Chicken",
                    reaction="itching",
                    severity=2,
                    is_active=True,
                    verification_status=VerificationStatus.VERIFIED,
                )
            )

        db.commit()
        print(f"Seeded demo owner {email!r} with pet {pet.name!r} (id {pet.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
