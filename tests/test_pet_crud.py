"""Phase 3 — pet management CRUD."""

import uuid

from conftest import auth_header, register_user, unique_email
from fastapi.testclient import TestClient

from app.models.base import PetAccessRole


def test_create_pet_returns_201_with_fields(client: TestClient, owner_token: str):
    response = client.post(
        "/api/pets",
        json={
            "name": "Milo",
            "species": "cat",
            "breed": "Domestic Shorthair",
            "sex": "female",
            "date_of_birth": "2021-02-01",
            "current_weight_kg": 4.2,
            "is_neutered": True,
            "notes": "Shy with strangers.",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Milo"
    assert body["species"] == "cat"
    assert body["is_neutered"] is True
    assert body["is_alive"] is True
    assert uuid.UUID(body["id"])


def test_creating_a_pet_grants_the_caller_ownership(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    from app.models.access import PetAccess

    rows = (
        db.query(PetAccess)
        .filter(PetAccess.pet_id == uuid.UUID(owner_pet["id"]))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].role == PetAccessRole.OWNER
    assert rows[0].revoked_at is None


def test_create_pet_requires_authentication(client: TestClient):
    response = client.post("/api/pets", json={"name": "Ghost", "species": "dog"})
    assert response.status_code == 401


def test_create_pet_rejects_blank_name(client: TestClient, owner_token: str):
    response = client.post(
        "/api/pets",
        json={"name": "   ", "species": "dog"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_create_pet_rejects_future_date_of_birth(client: TestClient, owner_token: str):
    response = client.post(
        "/api/pets",
        json={"name": "Future", "species": "dog", "date_of_birth": "2099-01-01"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422
    assert "future" in response.text.lower()


def test_create_pet_rejects_non_positive_weight(client: TestClient, owner_token: str):
    response = client.post(
        "/api/pets",
        json={"name": "Ghost", "species": "dog", "current_weight_kg": -3},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_list_pets_returns_only_own_pets(
    client: TestClient, owner_token: str, make_pet
):
    make_pet(owner_token, name="Alpha")
    make_pet(owner_token, name="Bravo")

    intruder_token = client.post(
        "/api/auth/register",
        json={"email": unique_email("list-intruder"), "password": "Str0ngPassw0rd!"},
    ).json()["access_token"]
    make_pet(intruder_token, name="NotMine")

    response = client.get("/api/pets", headers=auth_header(owner_token))
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"Alpha", "Bravo"}
    assert "NotMine" not in names


def test_list_pets_includes_record_counts(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record: callable
):
    make_health_record(owner_token, owner_pet["id"])
    response = client.get("/api/pets", headers=auth_header(owner_token))
    summary = next(
        p for p in response.json() if p["id"] == owner_pet["id"]
    )
    assert summary["health_record_count"] == 1
    assert summary["viewer_role"] == "owner"


def test_list_pets_empty_for_new_account(client: TestClient):
    token = client.post(
        "/api/auth/register",
        json={"email": unique_email("empty"), "password": "Str0ngPassw0rd!"},
    ).json()["access_token"]
    response = client.get("/api/pets", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == []


def test_get_pet_returns_own_pet(client: TestClient, owner_token: str, owner_pet: dict):
    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    )
    assert response.status_code == 200
    assert response.json()["name"] == owner_pet["name"]


def test_get_pet_requires_authentication(client: TestClient, owner_pet: dict):
    assert client.get(f"/api/pets/{owner_pet['id']}").status_code == 401


def test_update_pet_changes_fields(
    client: TestClient, owner_token: str, owner_pet: dict
):
    response = client.patch(
        f"/api/pets/{owner_pet['id']}",
        json={"name": "Rexy", "current_weight_kg": 13.1, "is_neutered": True},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Rexy"
    assert body["current_weight_kg"] == 13.1
    assert body["is_neutered"] is True
    # untouched fields survive a partial update
    assert body["breed"] == owner_pet["breed"]


def test_update_pet_rejects_empty_body(
    client: TestClient, owner_token: str, owner_pet: dict
):
    response = client.patch(
        f"/api/pets/{owner_pet['id']}", json={}, headers=auth_header(owner_token)
    )
    assert response.status_code == 422


def test_update_pet_rejects_invalid_species(
    client: TestClient, owner_token: str, owner_pet: dict
):
    response = client.patch(
        f"/api/pets/{owner_pet['id']}",
        json={"species": "dragon"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_soft_delete_removes_pet_from_list_but_keeps_history(
    client: TestClient, owner_token: str, populated_pet: dict, make_health_record, db
):
    """A soft-deleted pet leaves the default list but stays readable by its owner.

    Preserving history is only meaningful if the owner can still reach it, so
    the owner's grant deliberately survives: the pet reappears under
    ``include_deceased=true`` and can still be purged later.
    """
    from app.models.health_record import HealthRecord
    from app.models.pet import Pet

    pet_id = populated_pet["id"]
    pet_uuid = uuid.UUID(pet_id)
    assert make_health_record(owner_token, pet_id, title="Later record")

    response = client.delete(f"/api/pets/{pet_id}", headers=auth_header(owner_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted"] is True
    assert body["hard"] is False

    listed = client.get("/api/pets", headers=auth_header(owner_token)).json()
    assert pet_id not in {p["id"] for p in listed}

    # It comes back when the caller explicitly asks for removed pets.
    listed_with_removed = client.get(
        "/api/pets", params={"include_deceased": True}, headers=auth_header(owner_token)
    ).json()
    assert pet_id in {p["id"] for p in listed_with_removed}

    # The preserved history is still reachable by the owner.
    records = client.get(
        f"/api/pets/{pet_id}/health-records", headers=auth_header(owner_token)
    )
    assert records.status_code == 200
    assert records.json()["total"] >= 1

    # The rows are still in the database.
    assert db.get(Pet, pet_uuid) is not None
    assert db.get(Pet, pet_uuid).is_alive is False
    assert (
        db.query(HealthRecord).filter(HealthRecord.pet_id == pet_uuid).count() >= 1
    )


def test_soft_delete_revokes_collaborators_but_keeps_owner(
    client: TestClient, owner_token: str, owner_pet: dict, db
):
    """Collaborators lose access; the owner does not.

    Revoking the owner's grant as well would strand the preserved history with
    no one able to read it or to purge it. Phase 3 has no access-granting
    endpoint, so the caregiver's grant is written through the service.
    """
    import uuid as _uuid

    from app.models.access import PetAccess
    from app.models.base import PetAccessRole
    from app.services.authorization import grant_pet_access

    pet_id = _uuid.UUID(owner_pet["id"])
    caregiver = register_user(client, unique_email("caregiver-soft-delete"))
    caregiver_user_id = _uuid.UUID(caregiver["user"]["id"])
    caregiver_token = caregiver["access_token"]

    grant_pet_access(
        db,
        pet_id=pet_id,
        user_id=caregiver_user_id,
        role=PetAccessRole.CAREGIVER,
    )
    db.commit()

    # The caregiver can read the pet before the deletion.
    assert client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(caregiver_token)
    ).status_code == 200

    assert client.delete(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    ).status_code == 200

    grants = db.query(PetAccess).filter(PetAccess.pet_id == pet_id).all()
    owner_grant = next(g for g in grants if g.role == PetAccessRole.OWNER)
    caregiver_grants = [g for g in grants if g.user_id == caregiver_user_id]

    assert owner_grant.revoked_at is None, "owner lost access to their own pet"
    assert caregiver_grants
    assert all(g.revoked_at is not None for g in caregiver_grants)

    # The caregiver is now locked out; the owner is not.
    assert client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(caregiver_token)
    ).status_code == 404
    assert client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    ).status_code == 200


def test_purge_permanently_deletes_pet_and_records(
    client: TestClient, owner_token: str, populated_pet: dict
):
    pet_id = populated_pet["id"]
    response = client.post(
        f"/api/pets/{pet_id}/purge", headers=auth_header(owner_token)
    )
    assert response.status_code == 200, response.text
    assert response.json()["hard"] is True

    assert client.get(
        f"/api/pets/{pet_id}", headers=auth_header(owner_token)
    ).status_code == 404


def test_purge_requires_ownership(client: TestClient, intruder_token: str, owner_pet: dict):
    response = client.post(
        f"/api/pets/{owner_pet['id']}/purge", headers=auth_header(intruder_token)
    )
    assert response.status_code == 404


def test_purge_requires_authentication(client: TestClient, owner_pet: dict):
    assert client.post(f"/api/pets/{owner_pet['id']}/purge").status_code == 401


def test_allergy_crud_cycle(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    created = client.post(
        f"/api/pets/{pet_id}/allergies",
        json={"allergen": "bee venom", "reaction": "swelling", "severity": 5},
        headers=auth_header(owner_token),
    )
    assert created.status_code == 201, created.text
    allergy_id = created.json()["id"]
    assert created.json()["allergen"] == "bee venom"

    listed = client.get(
        f"/api/pets/{pet_id}/allergies", headers=auth_header(owner_token)
    )
    assert listed.status_code == 200
    assert [a["id"] for a in listed.json()] == [allergy_id]

    updated = client.patch(
        f"/api/pets/{pet_id}/allergies/{allergy_id}",
        json={"severity": 2},
        headers=auth_header(owner_token),
    )
    assert updated.status_code == 200
    assert updated.json()["severity"] == 2

    deleted = client.delete(
        f"/api/pets/{pet_id}/allergies/{allergy_id}", headers=auth_header(owner_token)
    )
    assert deleted.status_code == 200
    assert (
        client.get(
            f"/api/pets/{pet_id}/allergies", headers=auth_header(owner_token)
        ).json()
        == []
    )


def test_allergy_severity_out_of_range_rejected(
    client: TestClient, owner_token: str, owner_pet: dict
):
    response = client.post(
        f"/api/pets/{owner_pet['id']}/allergies",
        json={"allergen": "peanuts", "severity": 9},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422
