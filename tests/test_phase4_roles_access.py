"""Phase 4 tests — role selection at signup, and the vet access-grant flow.

Covers three separate concerns:

* **Signup roles** — a visitor may choose pet_owner or veterinarian, and nothing
  privileged, so nobody can self-issue an admin account.
* **Grant lifecycle** — an owner invites a veterinarian by email, the vet can
  then reach the pet, and revocation takes that access away again.
* **Capability boundaries** — a veterinarian may write clinical records but may
  not purge a pet, grant access, or reach a pet it was never shared.
"""

from tests.conftest import (
    auth_header,
    register_user,
    register_veterinarian,
    unique_email,
)


# ---------------------------------------------------------------------------
# Signup roles
# ---------------------------------------------------------------------------
def test_default_registration_is_pet_owner(client):
    body = register_user(client)
    assert body["user"]["role"] == "pet_owner"
    assert body["user"]["clinic_name"] is None


def test_can_register_as_veterinarian_with_clinic(client):
    body = register_veterinarian(client, clinic_name="Bright Paws Clinic")
    assert body["user"]["role"] == "veterinarian"
    assert body["user"]["clinic_name"] == "Bright Paws Clinic"


def test_veterinarian_without_clinic_is_allowed(client):
    body = register_veterinarian(client, clinic_name=None)
    assert body["user"]["role"] == "veterinarian"
    assert body["user"]["clinic_name"] is None


def test_cannot_self_register_as_admin(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email("wannabe-admin"),
            "password": "Str0ngPassw0rd!",
            "role": "admin",
        },
    )
    assert response.status_code == 422
    assert "admin" not in response.text.lower() or "role" in response.text.lower()


def test_cannot_self_register_as_clinic_staff(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email("wannabe-staff"),
            "password": "Str0ngPassw0rd!",
            "role": "clinic_staff",
        },
    )
    assert response.status_code == 422


def test_me_endpoint_reports_the_chosen_role(client):
    body = register_veterinarian(client)
    token = body["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "veterinarian"


def test_blank_clinic_name_is_stored_as_none(client):
    body = register_veterinarian(client, clinic_name="   ")
    assert body["user"]["clinic_name"] is None


# ---------------------------------------------------------------------------
# Grant lifecycle
# ---------------------------------------------------------------------------
def test_owner_can_invite_a_vet_by_email(client, owner_token, owner_pet, vet_email_vet):
    vet_email, _ = vet_email_vet
    response = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == vet_email
    assert body["role"] == "veterinarian"


def test_invited_vet_can_now_read_the_pet(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(vet_token)
    )
    assert response.status_code == 200
    assert response.json()["viewer_role"] == "veterinarian"


def test_vet_is_not_shown_the_pet_before_being_invited(client, owner_pet, vet_token):
    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(vet_token)
    )
    assert response.status_code == 404


def test_invited_pet_appears_in_the_vet_list(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    listing = client.get("/api/pets", headers=auth_header(vet_token)).json()
    ids = [p["id"] for p in listing]
    assert owner_pet["id"] in ids
    shared = next(p for p in listing if p["id"] == owner_pet["id"])
    assert shared["viewer_role"] == "veterinarian"


def test_owner_can_list_access_and_sees_both_grants(
    client, owner_token, owner_pet, vet_email_vet
):
    vet_email, _ = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    response = client.get(
        f"/api/pets/{owner_pet['id']}/access", headers=auth_header(owner_token)
    )
    assert response.status_code == 200
    roles = {row["role"] for row in response.json()}
    assert roles == {"owner", "veterinarian"}


def test_owner_can_revoke_a_vet(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    granted = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    ).json()

    revoke = client.delete(
        f"/api/pets/{owner_pet['id']}/access/{granted['user_id']}",
        headers=auth_header(owner_token),
    )
    assert revoke.status_code == 200

    after = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(vet_token)
    )
    assert after.status_code == 404


# ---------------------------------------------------------------------------
# Capability boundaries
# ---------------------------------------------------------------------------
def test_vet_can_add_a_clinical_record(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    response = client.post(
        f"/api/pets/{owner_pet['id']}/health-records",
        json={
            "title": "Vet consultation",
            "record_type": "consultation",
            "occurred_at": "2025-01-15T10:00:00Z",
        },
        headers=auth_header(vet_token),
    )
    assert response.status_code == 201, response.text


def test_vet_cannot_purge_the_pet(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    response = client.post(
        f"/api/pets/{owner_pet['id']}/purge", headers=auth_header(vet_token)
    )
    assert response.status_code == 403


def test_vet_cannot_grant_access_to_another_user(
    client, owner_token, owner_pet, vet_email_vet
):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    response = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": unique_email("another-vet"), "role": "veterinarian"},
        headers=auth_header(vet_token),
    )
    assert response.status_code == 403


def test_non_owner_cannot_revoke_access(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    granted = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    ).json()
    response = client.delete(
        f"/api/pets/{owner_pet['id']}/access/{granted['user_id']}",
        headers=auth_header(vet_token),
    )
    assert response.status_code == 403


def test_cannot_invite_an_email_with_no_account(client, owner_token, owner_pet):
    response = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": unique_email("ghost"), "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 404


def test_cannot_grant_owner_role_through_the_api(client, owner_token, owner_pet, vet_email_vet):
    vet_email, _ = vet_email_vet
    response = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "owner"},
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_owner_grant_cannot_be_revoked(client, owner_token, owner_pet):
    me = client.get("/api/auth/me", headers=auth_header(owner_token)).json()
    response = client.delete(
        f"/api/pets/{owner_pet['id']}/access/{me['id']}",
        headers=auth_header(owner_token),
    )
    assert response.status_code == 400


def test_regranting_replaces_the_previous_role(client, owner_token, owner_pet, vet_email_vet):
    vet_email, vet_token = vet_email_vet
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "veterinarian"},
        headers=auth_header(owner_token),
    )
    client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": vet_email, "role": "caregiver"},
        headers=auth_header(owner_token),
    )
    listing = client.get(
        f"/api/pets/{owner_pet['id']}/access", headers=auth_header(owner_token)
    ).json()
    vet_rows = [row for row in listing if row["email"] == vet_email]
    assert len(vet_rows) == 1
    assert vet_rows[0]["role"] == "caregiver"


def test_get_pet_now_reports_viewer_role_for_the_owner(client, owner_token, owner_pet):
    response = client.get(
        f"/api/pets/{owner_pet['id']}", headers=auth_header(owner_token)
    )
    assert response.status_code == 200
    assert response.json()["viewer_role"] == "owner"


def test_access_endpoints_are_404_for_an_unrelated_user(client, owner_pet, intruder_token):
    get_response = client.get(
        f"/api/pets/{owner_pet['id']}/access", headers=auth_header(intruder_token)
    )
    post_response = client.post(
        f"/api/pets/{owner_pet['id']}/access",
        json={"email": unique_email("x"), "role": "veterinarian"},
        headers=auth_header(intruder_token),
    )
    assert get_response.status_code == 404
    assert post_response.status_code == 404
