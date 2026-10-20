"""Shared pytest fixtures.

The tests run against a real PostgreSQL database, specifically ``pettwin_test``.
SQLite is not used anywhere: the point of these tests is to prove the production
stack works. The application's own engine still points at the configured
database from ``.env``; the test engine replaces only the request-scoped session
via the ``get_db`` dependency override, so no production setting is mutated.
"""

import os
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("POSTGRES_DB", "pettwin_test")

# Disable the RAG warm-up before the settings singleton is constructed below.
# The ``client`` fixture enters the app's lifespan once per test, so warming the
# index there would rebuild it repeatedly and dominate the suite runtime. Set
# with ``setdefault`` so an explicit override still wins.
os.environ.setdefault("RAG_WARMUP_ON_STARTUP", "false")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app import models as _models  # noqa: F401,E402  (registers models)


def _test_database_url() -> str:
    if not settings.postgres_user or not settings.postgres_db:
        pytest.skip(
            "PostgreSQL is not configured. Set POSTGRES_USER / POSTGRES_DB in .env."
        )
    return settings.database_url


@pytest.fixture(scope="session")
def engine() -> Generator:
    """Engine bound to a throwaway schema inside the test database.

    Each pytest session gets its own PostgreSQL schema, so two sessions running
    at the same time cannot collide while creating the native enum types. The
    schema is dropped on teardown.
    """
    url = _test_database_url()
    schema = f"test_{uuid.uuid4().hex[:12]}"

    bootstrap = create_engine(url, future=True, isolation_level="AUTOCOMMIT")
    with bootstrap.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    bootstrap.dispose()

    test_engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )

    try:
        Base.metadata.create_all(bind=test_engine)
    except Exception:
        test_engine.dispose()
        cleanup = create_engine(url, future=True, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        cleanup.dispose()
        raise

    yield test_engine

    test_engine.dispose()
    cleanup = create_engine(url, future=True, isolation_level="AUTOCOMMIT")
    with cleanup.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    cleanup.dispose()


@pytest.fixture()
def db(engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSession()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def register_user(
    client: TestClient, email: str | None = None, password: str = "Str0ngPassw0rd!"
) -> dict:
    """Register a user through the API and return the parsed response body."""
    email = email or unique_email()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Phase 3 fixtures — pet management, clinical records, Digital Twin
#
# Built on the helpers above so both phases share one registration path.
# ---------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def owner_token(client: TestClient) -> str:
    return register_user(client, unique_email("owner-twin"))["access_token"]


@pytest.fixture()
def intruder_token(client: TestClient) -> str:
    return register_user(client, unique_email("intruder-twin"))["access_token"]


def register_veterinarian(
    client: TestClient,
    email: str | None = None,
    password: str = "Str0ngPassw0rd!",
    clinic_name: str | None = "Test Veterinary Clinic",
) -> dict:
    """Register an account with the veterinarian role through the API."""
    email = email or unique_email("vet")
    body = {
        "email": email,
        "password": password,
        "full_name": "Dr Test Vet",
        "role": "veterinarian",
    }
    if clinic_name is not None:
        body["clinic_name"] = clinic_name
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def vet_token(client: TestClient) -> str:
    """A registered veterinarian account, with no pet access yet."""
    return register_veterinarian(client)["access_token"]


@pytest.fixture()
def vet_email_vet(client: TestClient) -> tuple[str, str]:
    """A veterinarian's (email, token), so an owner can invite them by address."""
    email = unique_email("vet-invite")
    body = register_veterinarian(client, email=email)
    return email, body["access_token"]


@pytest.fixture()
def make_pet(client: TestClient):
    """Factory creating a pet owned by the given token."""

    def _make(token: str, **overrides) -> dict:
        payload = {
            "name": "Rex",
            "species": "dog",
            "breed": "Beagle",
            "sex": "male",
            "date_of_birth": "2020-06-15",
            "current_weight_kg": 12.4,
        }
        payload.update(overrides)
        response = client.post("/api/pets", json=payload, headers=auth_header(token))
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def owner_pet(client: TestClient, owner_token: str, make_pet) -> dict:
    """A pet owned by the owner fixture, with no clinical records."""
    return make_pet(owner_token)


@pytest.fixture()
def intruder_pet(client: TestClient, intruder_token: str, make_pet) -> dict:
    """A pet owned by a different user, used to probe cross-user isolation."""
    return make_pet(intruder_token, name="Secret", species="cat")


@pytest.fixture()
def make_health_record(client: TestClient):
    """Factory creating a verified health record for a pet."""

    def _make(token: str, pet_id: str, **overrides) -> dict:
        payload = {
            "title": "Consultation",
            "record_type": "consultation",
            "occurred_at": now_utc().isoformat(),
            "verification_status": "verified",
            "source_type": "veterinary_record",
        }
        payload.update(overrides)
        response = client.post(
            f"/api/pets/{pet_id}/health-records",
            json=payload,
            headers=auth_header(token),
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_child(client: TestClient):
    """Factory posting one of the five child record types under a health record."""

    def _make(token: str, pet_id: str, record_id: str, path: str, **payload) -> dict:
        body = {"health_record_id": record_id, **payload}
        response = client.post(
            f"/api/pets/{pet_id}/{path}", json=body, headers=auth_header(token)
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def populated_pet(
    client: TestClient,
    owner_token: str,
    make_pet: callable,
    make_health_record: callable,
    make_child: callable,
) -> dict:
    """A pet carrying a full, verified clinical history.

    Exercises every record type so the Digital Twin assembly has something real
    to combine. Ordering matters: children cannot be created before the health
    record they hang from.
    """
    pet = make_pet(
        owner_token,
        name="Bella",
        breed="Labrador",
        sex="female",
        date_of_birth="2019-03-10",
        current_weight_kg=28.5,
        notes="Friendly but nervous around nail trims.",
    )
    pet_id = pet["id"]
    token = owner_token
    headers = auth_header(token)

    for allergen, reaction, severity in (
        ("chicken", "itching", 3),
        ("penicillin", "vomiting", 4),
    ):
        response = client.post(
            f"/api/pets/{pet_id}/allergies",
            json={
                "allergen": allergen,
                "reaction": reaction,
                "severity": severity,
                # Allergies default to unverified, and the Digital Twin reports
                # only verified health state. This fixture represents a fully
                # verified history, so they are filed as verified explicitly.
                "verification_status": "verified",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text

    past = now_utc() - timedelta(days=30)
    visit = client.post(
        f"/api/pets/{pet_id}/visits",
        json={
            "visit_at": past.isoformat(),
            "visit_type": "sick",
            "status": "completed",
            "clinic_name": "Test Veterinary Clinic",
            "reason_for_visit": "Limping on left hind leg",
            # A completed encounter at a named clinic, verified like the record
            # it produced. Without this the visit would be excluded from the
            # verified timeline while its own health record was included.
            "verification_status": "verified",
            "source_type": "veterinary_record",
        },
        headers=headers,
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["id"]

    record = make_health_record(
        token,
        pet_id,
        title="Lameness assessment",
        occurred_at=past.isoformat(),
        visit_id=visit_id,
    )
    record_id = record["id"]

    make_child(
        token,
        pet_id,
        record_id,
        "symptoms",
        symptom_name="favouring left hind leg",
        severity=3,
        onset_at=(past - timedelta(days=2)).isoformat(),
    )
    make_child(
        token,
        pet_id,
        record_id,
        "diagnoses",
        diagnosis_name="Patellar luxation",
        status="active",
        is_confirmed=True,
        diagnosed_at=past.isoformat(),
    )
    make_child(
        token,
        pet_id,
        record_id,
        "medications",
        medication_name="Meloxicam",
        dose_amount=1.5,
        dose_unit="mg",
        frequency="once daily",
        started_at=past.isoformat(),
        is_active=True,
    )
    make_child(
        token,
        pet_id,
        record_id,
        "vaccinations",
        vaccine_name="Rabies",
        administered_at=past.isoformat(),
        next_due_at=(now_utc() + timedelta(days=300)).isoformat(),
    )
    make_child(
        token,
        pet_id,
        record_id,
        "vaccinations",
        vaccine_name="DHPP",
        administered_at=past.isoformat(),
        next_due_at=(now_utc() - timedelta(days=5)).isoformat(),
    )
    make_child(
        token,
        pet_id,
        record_id,
        "lab-reports",
        test_name="Complete Blood Count",
        result_value=5.2,
        unit="10^9/L",
        reference_range_low=4.5,
        reference_range_high=8.5,
        performed_at=past.isoformat(),
        lab_name="Test Lab",
    )
    return pet
