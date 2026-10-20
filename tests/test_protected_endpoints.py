"""Protected endpoint access and cross-user isolation tests.

The central rule under test: a user must never be able to read another user's
private pet records.
"""

import uuid

from fastapi.testclient import TestClient

from app.core.jwt import create_access_token
from tests.conftest import auth_header, register_user


def make_pet(client: TestClient, token: str, name: str = "Rex") -> dict:
    response = client.post(
        "/api/pets",
        headers=auth_header(token),
        json={"name": name, "species": "dog", "breed": "Beagle", "sex": "male"},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ── Unauthenticated access ───────────────────────────────────────────────


def test_protected_route_without_token_is_401(client: TestClient) -> None:
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get(f"/api/pets/{uuid.uuid4()}").status_code == 401


def test_garbage_token_is_401(client: TestClient) -> None:
    response = client.get("/api/users/me", headers=auth_header("not-a-jwt"))
    assert response.status_code == 401


def test_malformed_bearer_header_is_401(client: TestClient) -> None:
    response = client.get("/api/users/me", headers={"Authorization": "Bearer"})
    assert response.status_code == 401


def test_wrong_scheme_is_401(client: TestClient) -> None:
    response = client.get(
        "/api/users/me", headers={"Authorization": "Basic YWJjOmRlZg=="}
    )
    assert response.status_code == 401


def test_token_signed_with_foreign_key_is_401(client: TestClient) -> None:
    import jwt

    from app.core.config import settings

    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        },
        key="an-attacker-controlled-signing-key-here",
        algorithm="HS256",
    )
    response = client.get("/api/users/me", headers=auth_header(forged))
    assert response.status_code == 401


def test_token_with_unknown_subject_is_401(client: TestClient) -> None:
    forged = create_access_token(subject=str(uuid.uuid4()))
    response = client.get("/api/users/me", headers=auth_header(forged))
    assert response.status_code == 401


# ── Authenticated access ─────────────────────────────────────────────────


def test_authenticated_user_can_read_profile(client: TestClient) -> None:
    body = register_user(client)
    response = client.get("/api/users/me", headers=auth_header(body["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == body["user"]["email"]


def test_user_can_update_own_profile(client: TestClient) -> None:
    body = register_user(client)
    response = client.patch(
        "/api/users/me",
        headers=auth_header(body["access_token"]),
        json={"full_name": "Renamed Person", "phone": "9999999999"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed Person"


def test_owner_can_read_own_pet(client: TestClient) -> None:
    body = register_user(client)
    pet = make_pet(client, body["access_token"])
    response = client.get(
        f"/api/pets/{pet['id']}", headers=auth_header(body["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["name"] == pet["name"]


# ── Cross-user isolation ─────────────────────────────────────────────────


def test_user_cannot_read_another_users_pet(client: TestClient) -> None:
    owner = register_user(client)
    pet = make_pet(client, owner["access_token"])

    intruder = register_user(client)
    response = client.get(
        f"/api/pets/{pet['id']}", headers=auth_header(intruder["access_token"])
    )
    assert response.status_code == 404


def test_missing_pet_and_forbidden_pet_both_return_404(
    client: TestClient,
) -> None:
    """A 404 for both, so a caller cannot probe for which pet ids exist."""
    owner = register_user(client)
    pet = make_pet(client, owner["access_token"])

    intruder = register_user(client)
    forbidden = client.get(
        f"/api/pets/{pet['id']}", headers=auth_header(intruder["access_token"])
    )
    nonexistent = client.get(
        f"/api/pets/{uuid.uuid4()}", headers=auth_header(intruder["access_token"])
    )
    assert forbidden.status_code == 404
    assert nonexistent.status_code == 404
    assert forbidden.json() == nonexistent.json()


def test_creating_a_pet_requires_a_token(client: TestClient) -> None:
    response = client.post("/api/pets", json={"name": "Ghost", "species": "dog"})
    assert response.status_code == 401


def test_pet_creation_grants_owner_access_row(client: TestClient, db) -> None:
    from sqlalchemy import select

    from app.models.access import PetAccess
    from app.models.pet import Pet

    body = register_user(client)
    pet = make_pet(client, body["access_token"])

    stored = db.execute(select(Pet).where(Pet.id == uuid.UUID(pet["id"]))).scalar_one()
    access = db.execute(
        select(PetAccess).where(
            PetAccess.pet_id == stored.id,
            PetAccess.user_id == stored.created_by_user_id,
        )
    ).scalars().first()
    assert access is not None
    assert access.role.value == "owner"
    assert access.revoked_at is None


def test_pet_species_is_validated(client: TestClient) -> None:
    body = register_user(client)
    response = client.post(
        "/api/pets",
        headers=auth_header(body["access_token"]),
        json={"name": "Martian", "species": "alien"},
    )
    assert response.status_code == 422


def test_pet_requires_a_name(client: TestClient) -> None:
    body = register_user(client)
    response = client.post(
        "/api/pets",
        headers=auth_header(body["access_token"]),
        json={"species": "dog"},
    )
    assert response.status_code == 422


def test_non_positive_weight_is_rejected(client: TestClient) -> None:
    body = register_user(client)
    response = client.post(
        "/api/pets",
        headers=auth_header(body["access_token"]),
        json={"name": "Rex", "species": "dog", "current_weight_kg": -4},
    )
    assert response.status_code == 422
