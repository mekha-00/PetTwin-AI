"""Application startup, configuration and schema tests."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import Base


def test_health_endpoint_reports_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == 7
    assert body["database_configured"] is True
    # The Digital Twin is still a service, assembled on demand and not persisted.
    assert body["digital_twin"] == "service_assembly_not_persisted"
    # Phase 7 ships retrieval-augmented generation, a read-only agent, and
    # similar-case retrieval. The LLM-backed flags mirror whether a Groq key is
    # configured. No key is still a valid setup: the rest of the app runs and the
    # AI endpoints return 503.
    assert body["rag_enabled"] is True
    assert body["similar_cases_enabled"] is True
    assert body["agent_enabled"] == bool(settings.groq_api_key)
    assert body["ai_features_enabled"] == bool(settings.groq_api_key)


def test_all_expected_routes_are_registered(client: TestClient) -> None:
    paths = {route.path for route in app.routes}
    for expected in [
        "/health",
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/me",
        "/api/users/me",
        "/api/pets",
        "/api/pets/{pet_id}",
        "/api/pets/{pet_id}/purge",
        "/api/pets/{pet_id}/allergies",
        "/api/pets/{pet_id}/health-records",
        "/api/pets/{pet_id}/visits",
        "/api/pets/{pet_id}/symptoms",
        "/api/pets/{pet_id}/diagnoses",
        "/api/pets/{pet_id}/medications",
        "/api/pets/{pet_id}/vaccinations",
        "/api/pets/{pet_id}/lab-reports",
        "/api/pets/{pet_id}/digital-twin",
        "/api/pets/{pet_id}/health-timeline",
        # Phase 4 — access sharing.
        "/api/pets/{pet_id}/access",
        "/api/pets/{pet_id}/access/{user_id}",
        # Phase 5 — retrieval-augmented generation.
        "/api/rag/query",
        "/api/rag/status",
        # Phase 6 — the read-only agent.
        "/api/pets/{pet_id}/ask",
        # Phase 7 — similar-case retrieval.
        "/api/pets/{pet_id}/similar-cases",
        # Phase 7 — evidence-based candidate conditions.
        "/api/pets/{pet_id}/symptom-options",
        "/api/pets/{pet_id}/predict-conditions",
    ]:
        assert expected in paths, f"missing route: {expected}"


def test_openapi_schema_is_generated(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == settings.app_name


def test_database_is_configured_for_postgres() -> None:
    assert settings.database_url.startswith("postgresql+psycopg2://")
    assert settings.is_database_configured is True


def test_secret_key_is_loaded_and_strong() -> None:
    assert len(settings.secret_key) >= 32


def test_jwt_algorithm_is_pinned_to_hs256() -> None:
    assert settings.jwt_algorithm == "HS256"


def test_cors_origins_are_an_explicit_allowlist() -> None:
    assert settings.cors_origins
    assert "*" not in settings.cors_origins


def test_all_twelve_tables_are_mapped() -> None:
    assert len(Base.metadata.tables) == 12
    for table in [
        "users",
        "pets",
        "pet_access",
        "health_records",
        "symptom_records",
        "diagnosis_records",
        "medication_records",
        "vaccination_records",
        "lab_reports",
        "veterinary_visits",
        "health_timeline_events",
        "pet_allergies",
    ]:
        assert table in Base.metadata.tables, f"missing table: {table}"


def test_pets_table_stores_identity_only() -> None:
    """Health state must not be duplicated onto ``pets``.

    Existing conditions, current medications and vaccination status are derived
    from the record tables, so none of them may exist as a column — that is what
    keeps the twin from having a second, drifting copy of the truth.
    """
    columns = {c.name for c in Base.metadata.tables["pets"].columns}
    for forbidden in (
        "existing_conditions",
        "known_conditions",
        "current_medications",
        "vaccination_status",
    ):
        assert forbidden not in columns, f"pets.{forbidden} duplicates record data"


def test_allergies_have_their_own_table_not_a_pet_column() -> None:
    pet_columns = {c.name for c in Base.metadata.tables["pets"].columns}
    assert "allergies" not in pet_columns
    allergy_columns = {c.name for c in Base.metadata.tables["pet_allergies"].columns}
    for expected in ("allergen", "reaction", "severity", "is_active"):
        assert expected in allergy_columns


def test_no_digital_twin_table_exists() -> None:
    """The Digital Twin is a service, not a persisted table."""
    assert "digital_twin" not in Base.metadata.tables
    assert "digital_twins" not in Base.metadata.tables
