"""Phase 3 — cross-user authorization for pets, records and the Digital Twin.

The rule under test: a user must never learn that another user's pet exists.
That means a forbidden pet id has to be indistinguishable from a pet id that was
never created, so these tests assert on response *body* equality as well as
status codes.
"""

import uuid
from datetime import datetime, timezone

from conftest import auth_header, unique_email
from fastapi.testclient import TestClient

from app.models.access import PetAccess
from app.models.base import PetAccessRole
from app.models.pet import Pet
from app.services.authorization import grant_pet_access


def test_cannot_read_another_users_pet(
    client: TestClient, intruder_token: str, owner_pet: dict
):
    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(intruder_token)
    )
    assert response.status_code == 404


def test_forbidden_pet_is_indistinguishable_from_missing_pet(
    client: TestClient, intruder_token: str, owner_pet: dict
):
    """A 403 here would confirm the pet exists and allow id enumeration."""
    forbidden = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(intruder_token)
    )
    missing = client.get(
        f"/api/pets/{uuid.uuid4()}", headers=auth_header(intruder_token)
    )
    assert forbidden.status_code == missing.status_code == 404
    assert forbidden.json() == missing.json()


def test_cannot_update_another_users_pet(
    client: TestClient, owner_token: str, intruder_token: str, owner_pet: dict
):
    response = client.patch(
        f"/api/pets/{owner_pet['id']}",
        json={"name": "Hijacked"},
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404

    # The owner's own copy is unchanged.
    still = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    )
    assert still.json()["name"] == owner_pet["name"]


def test_cannot_delete_another_users_pet(
    client: TestClient, intruder_token: str, owner_pet: dict
):
    response = client.delete(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(intruder_token)
    )
    assert response.status_code == 404


def test_revoked_grant_loses_access(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    grant = (
        db.query(PetAccess)
        .filter(PetAccess.pet_id == uuid.UUID(owner_pet["id"]))
        .first()
    )
    grant.revoked_at = datetime.now(timezone.utc)
    db.commit()

    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    )
    assert response.status_code == 404


def test_caregiver_can_read_pet(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    caregiver_email = unique_email("caregiver")
    caregiver = client.post(
        "/api/auth/register",
        json={"email": caregiver_email, "password": "Str0ngPassw0rd!"},
    ).json()
    caregiver_id = uuid.UUID(caregiver["user"]["id"])

    grant_pet_access(
        db,
        pet_id=uuid.UUID(owner_pet["id"]),
        user_id=caregiver_id,
        role=PetAccessRole.CAREGIVER,
        granted_by_user_id=caregiver_id,
        reason="test",
    )
    db.commit()

    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(caregiver["access_token"])
    )
    assert response.status_code == 200


def test_caregiver_cannot_purge_pet(client: TestClient, owner_pet: dict, db):
    """Erasure destroys the owner's medical history, so it is owner-only."""
    caregiver = client.post(
        "/api/auth/register",
        json={"email": unique_email("caregiver-purge"), "password": "Str0ngPassw0rd!"},
    ).json()
    caregiver_id = uuid.UUID(caregiver["user"]["id"])

    grant_pet_access(
        db,
        pet_id=uuid.UUID(owner_pet["id"]),
        user_id=caregiver_id,
        role=PetAccessRole.CAREGIVER,
    )
    db.commit()

    response = client.post(
        f"/api/pets/{owner_pet['id']}/purge",
        headers=auth_header(caregiver["access_token"]),
    )
    assert response.status_code == 403


def test_caregiver_cannot_soft_delete_pet(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    """Soft deletion revokes collaborators' access, so it is owner-only.

    A caregiver must not be able to remove a pet from its owner and lock the
    veterinarian out of the record.
    """
    caregiver = client.post(
        "/api/auth/register",
        json={"email": unique_email("caregiver-soft-delete"), "password": "Str0ngPassw0rd!"},
    ).json()
    caregiver_id = uuid.UUID(caregiver["user"]["id"])

    grant_pet_access(
        db,
        pet_id=uuid.UUID(owner_pet["id"]),
        user_id=caregiver_id,
        role=PetAccessRole.CAREGIVER,
    )
    db.commit()

    response = client.delete(
        f"/api/pets/{owner_pet['id']}",
        headers=auth_header(caregiver["access_token"]),
    )
    assert response.status_code == 403

    # The pet is untouched.
    assert client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    ).status_code == 200


def test_cannot_read_another_users_health_records(
    client: TestClient, owner_token: str, intruder_token: str, owner_pet: dict,
    make_health_record,
):
    make_health_record(owner_token, owner_pet["id"])
    response = client.get(
        f"/api/pets/{owner_pet['id']}/health-records",
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404


def test_cannot_read_another_users_allergies(
    client: TestClient, owner_token: str, intruder_token: str, owner_pet: dict
):
    client.post(
        f"/api/pets/{owner_pet['id']}/allergies",
        json={"allergen": "chicken"},
        headers=auth_header(owner_token),
    )
    response = client.get(
        f"/api/pets/{owner_pet['id']}/allergies", headers=auth_header(intruder_token)
    )
    assert response.status_code == 404


def test_cannot_read_another_users_visits(
    client: TestClient, owner_token: str, intruder_token: str, owner_pet: dict
):
    client.post(
        f"/api/pets/{owner_pet['id']}/visits",
        json={"visit_at": "2024-01-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )
    response = client.get(
        f"/api/pets/{owner_pet['id']}/visits", headers=auth_header(intruder_token)
    )
    assert response.status_code == 404


def test_cannot_write_records_to_another_users_pet(
    client: TestClient, intruder_token: str, owner_pet: dict
):
    response = client.post(
        f"/api/pets/{owner_pet['id']}/health-records",
        json={"title": "Injected", "occurred_at": "2024-01-01T00:00:00+00:00"},
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404


def test_cannot_read_another_users_digital_twin(
    client: TestClient, intruder_token: str, populated_pet: dict
):
    response = client.get(
        f"/api/pets/{populated_pet['id']}/digital-twin",
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404
    # No clinical detail may leak in an error body either.
    assert "Bella" not in response.text
    assert "Meloxicam" not in response.text


def test_cannot_read_another_users_timeline(
    client: TestClient, intruder_token: str, populated_pet: dict
):
    response = client.get(
        f"/api/pets/{populated_pet['id']}/health-timeline",
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404
    assert "Patellar luxation" not in response.text


def test_child_record_cannot_attach_to_another_pets_health_record(
    client: TestClient, owner_token: str, intruder_token: str, make_pet,
    make_health_record,
):
    """The cross-pet injection guard.

    A symptom names its parent health record in the body while the pet comes
    from the path. If the service did not compare the parent's pet_id to the
    path, a user could file a record against somebody else's record and have it
    surface in their own pet's history.
    """
    my_pet = make_pet(intruder_token, name="Mine", species="cat")
    their_record = make_health_record(
        owner_token,
        make_pet(owner_token, name="Theirs")["id"],
        title="Confidential",
    )

    response = client.post(
        f"/api/pets/{my_pet['id']}/symptoms",
        json={
            "health_record_id": their_record["id"],
            "symptom_name": "injected symptom",
        },
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404

    leaked = client.get(
        f"/api/pets/{my_pet['id']}/symptoms", headers=auth_header(intruder_token)
    )
    assert leaked.json()["total"] == 0


def test_health_record_cannot_reference_another_pets_visit(
    client: TestClient, owner_token: str, intruder_token: str, make_pet
):
    their_pet = make_pet(owner_token, name="Theirs")
    their_visit = client.post(
        f"/api/pets/{their_pet['id']}/visits",
        json={"visit_at": "2024-01-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    ).json()
    my_pet = make_pet(intruder_token, name="Mine", species="cat")

    response = client.post(
        f"/api/pets/{my_pet['id']}/health-records",
        json={
            "title": "Cross-linked",
            "occurred_at": "2024-01-01T00:00:00+00:00",
            "visit_id": their_visit["id"],
        },
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404


def test_cannot_update_another_users_record_by_id(
    client: TestClient, owner_token: str, intruder_token: str, owner_pet: dict,
    make_health_record,
):
    record = make_health_record(owner_token, owner_pet["id"])
    response = client.patch(
        f"/api/pets/{owner_pet['id']}/health-records/{record['id']}",
        json={"title": "Tampered"},
        headers=auth_header(intruder_token),
    )
    assert response.status_code == 404


def test_all_endpoints_require_authentication(client: TestClient, owner_pet: dict):
    pet_id = owner_pet["id"]
    unauthenticated = [
        ("GET", f"/api/pets/{pet_id}"),
        ("PATCH", f"/api/pets/{pet_id}"),
        ("DELETE", f"/api/pets/{pet_id}"),
        ("POST", f"/api/pets/{pet_id}/purge"),
        ("GET", f"/api/pets/{pet_id}/digital-twin"),
        ("GET", f"/api/pets/{pet_id}/health-timeline"),
        ("GET", f"/api/pets/{pet_id}/health-records"),
        ("GET", f"/api/pets/{pet_id}/visits"),
        ("GET", f"/api/pets/{pet_id}/symptoms"),
        ("GET", f"/api/pets/{pet_id}/diagnoses"),
        ("GET", f"/api/pets/{pet_id}/medications"),
        ("GET", f"/api/pets/{pet_id}/vaccinations"),
        ("GET", f"/api/pets/{pet_id}/lab-reports"),
        ("GET", f"/api/pets/{pet_id}/allergies"),
    ]
    for method, path in unauthenticated:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_pet_id_ownership_is_enforced_in_the_database_not_the_router(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    """Bypassing HTTP entirely still yields a single owner grant."""
    pet = db.get(Pet, uuid.UUID(owner_pet["id"]))
    assert pet is not None
    assert pet.created_by_user_id is not None
    grants = db.query(PetAccess).filter(PetAccess.pet_id == pet.id).all()
    assert {g.role for g in grants} == {PetAccessRole.OWNER}
