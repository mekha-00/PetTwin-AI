"""Phase 3 — clinical record CRUD across all seven record types."""

from conftest import auth_header
from fastapi.testclient import TestClient


def test_create_and_read_visit(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    created = client.post(
        f"/api/pets/{pet_id}/visits",
        json={
            "visit_at": "2024-03-15T10:00:00+00:00",
            "visit_type": "sick",
            "status": "completed",
            "clinic_name": "City Vet",
            "veterinarian_name": "Dr. Rao",
            "reason_for_visit": "Coughing",
        },
        headers=auth_header(owner_token),
    )
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]

    fetched = client.get(
        f"/api/pets/{pet_id}/visits/{visit_id}", headers=auth_header(owner_token)
    )
    assert fetched.status_code == 200
    assert fetched.json()["veterinarian_name"] == "Dr. Rao"

    updated = client.patch(
        f"/api/pets/{pet_id}/visits/{visit_id}",
        json={"status": "cancelled"},
        headers=auth_header(owner_token),
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "cancelled"

    deleted = client.delete(
        f"/api/pets/{pet_id}/visits/{visit_id}", headers=auth_header(owner_token)
    )
    assert deleted.status_code == 200
    assert client.get(
        f"/api/pets/{pet_id}/visits/{visit_id}", headers=auth_header(owner_token)
    ).status_code == 404


def test_health_record_crud(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    created = client.post(
        f"/api/pets/{pet_id}/health-records",
        json={
            "title": "Bloodwork panel",
            "record_type": "lab_work",
            "occurred_at": "2024-04-01T09:00:00+00:00",
            "verification_status": "verified",
        },
        headers=auth_header(owner_token),
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert created.json()["verification_status"] == "verified"

    updated = client.patch(
        f"/api/pets/{pet_id}/health-records/{record_id}",
        json={"title": "Full bloodwork panel"},
        headers=auth_header(owner_token),
    )
    assert updated.json()["title"] == "Full bloodwork panel"

    assert client.delete(
        f"/api/pets/{pet_id}/health-records/{record_id}",
        headers=auth_header(owner_token),
    ).status_code == 200


def test_deleting_health_record_cascades_to_children(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    make_child(
        owner_token, pet_id, record["id"], "symptoms", symptom_name="lethargy"
    )
    make_child(
        owner_token,
        pet_id,
        record["id"],
        "diagnoses",
        diagnosis_name="Anemia",
        diagnosed_at="2024-01-01T00:00:00+00:00",
    )

    assert client.get(
        f"/api/pets/{pet_id}/symptoms", headers=auth_header(owner_token)
    ).json()["total"] == 1

    client.delete(
        f"/api/pets/{pet_id}/health-records/{record['id']}",
        headers=auth_header(owner_token),
    )

    assert client.get(
        f"/api/pets/{pet_id}/symptoms", headers=auth_header(owner_token)
    ).json()["total"] == 0
    assert client.get(
        f"/api/pets/{pet_id}/diagnoses", headers=auth_header(owner_token)
    ).json()["total"] == 0


def test_symptom_crud_and_resolution(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    symptom = make_child(
        owner_token,
        pet_id,
        record["id"],
        "symptoms",
        symptom_name="vomiting",
        severity=2,
        onset_at="2024-01-01T00:00:00+00:00",
    )
    assert symptom["is_chronic"] is False

    updated = client.patch(
        f"/api/pets/{pet_id}/symptoms/{symptom['id']}",
        json={"resolved_at": "2024-01-05T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )
    assert updated.status_code == 200
    assert updated.json()["resolved_at"] is not None

    assert client.delete(
        f"/api/pets/{pet_id}/symptoms/{symptom['id']}",
        headers=auth_header(owner_token),
    ).status_code == 200


def test_diagnosis_crud_and_status_transition(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    diagnosis = make_child(
        owner_token,
        pet_id,
        record["id"],
        "diagnoses",
        diagnosis_name="Otitis externa",
        status="active",
        diagnosed_at="2024-02-01T00:00:00+00:00",
    )
    assert diagnosis["status"] == "active"

    updated = client.patch(
        f"/api/pets/{pet_id}/diagnoses/{diagnosis['id']}",
        json={"resolved_at": "2024-02-20T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )
    assert updated.status_code == 200
    # Marking a diagnosis resolved must also flip the status, or the Digital
    # Twin would keep listing it as an ongoing condition.
    assert updated.json()["status"] == "resolved"


def test_creating_diagnosis_with_resolved_date_requires_inactive_status(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/diagnoses",
        json={
            "health_record_id": record["id"],
            "diagnosis_name": "Contradiction",
            "status": "active",
            "diagnosed_at": "2024-01-01T00:00:00+00:00",
            "resolved_at": "2024-02-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_medication_crud(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    medication = make_child(
        owner_token,
        pet_id,
        record["id"],
        "medications",
        medication_name="Amoxicillin",
        dose_amount=250,
        dose_unit="mg",
        frequency="twice daily",
        started_at="2024-01-01T00:00:00+00:00",
    )
    assert medication["is_active"] is True

    stopped = client.patch(
        f"/api/pets/{pet_id}/medications/{medication['id']}",
        json={"ended_at": "2024-01-10T00:00:00+00:00", "is_active": False},
        headers=auth_header(owner_token),
    )
    assert stopped.status_code == 200
    assert stopped.json()["is_active"] is False


def test_medication_cannot_end_before_it_starts(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/medications",
        json={
            "health_record_id": record["id"],
            "medication_name": "Impossible",
            "started_at": "2024-03-01T00:00:00+00:00",
            "ended_at": "2024-01-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_vaccination_crud(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    vaccination = make_child(
        owner_token,
        pet_id,
        record["id"],
        "vaccinations",
        vaccine_name="Rabies",
        administered_at="2024-01-10T00:00:00+00:00",
        next_due_at="2027-01-10T00:00:00+00:00",
        batch_number="BATCH-1",
    )
    assert vaccination["vaccine_name"] == "Rabies"

    updated = client.patch(
        f"/api/pets/{pet_id}/vaccinations/{vaccination['id']}",
        json={"is_booster": True},
        headers=auth_header(owner_token),
    )
    assert updated.json()["is_booster"] is True


def test_vaccination_due_date_cannot_precede_administration(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/vaccinations",
        json={
            "health_record_id": record["id"],
            "vaccine_name": "Impossible",
            "administered_at": "2024-06-01T00:00:00+00:00",
            "next_due_at": "2024-01-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_lab_report_crud(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    lab = make_child(
        owner_token,
        pet_id,
        record["id"],
        "lab-reports",
        test_name="Haematocrit",
        result_value=45,
        unit="%",
        reference_range_low=38,
        reference_range_high=55,
        performed_at="2024-02-01T00:00:00+00:00",
    )
    assert lab["result_value"] == 45

    updated = client.patch(
        f"/api/pets/{pet_id}/lab-reports/{lab['id']}",
        json={"interpretation": "Within normal range"},
        headers=auth_header(owner_token),
    )
    assert updated.json()["interpretation"] == "Within normal range"


def test_lab_report_requires_a_result(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/lab-reports",
        json={
            "health_record_id": record["id"],
            "test_name": "Empty",
            "performed_at": "2024-02-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_lab_report_rejects_inverted_reference_range(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/lab-reports",
        json={
            "health_record_id": record["id"],
            "test_name": "Inverted",
            "result_value": 5,
            "reference_range_low": 10,
            "reference_range_high": 2,
            "performed_at": "2024-02-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_symptom_severity_must_be_within_range(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    record = make_health_record(owner_token, pet_id)
    response = client.post(
        f"/api/pets/{pet_id}/symptoms",
        json={
            "health_record_id": record["id"],
            "symptom_name": "Impossible",
            "severity": 11,
        },
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_list_records_is_paginated(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    pet_id = owner_pet["id"]
    for index in range(5):
        make_health_record(owner_token, pet_id, title=f"Record {index}")

    page = client.get(
        f"/api/pets/{pet_id}/health-records?limit=2&offset=1",
        headers=auth_header(owner_token),
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 1


def test_list_records_rejects_oversized_limit(
    client: TestClient, owner_token: str, owner_pet: dict
):
    response = client.get(
        f"/api/pets/{owner_pet['id']}/health-records?limit=5000",
        headers=auth_header(owner_token),
    )
    assert response.status_code == 422


def test_verified_only_filter_excludes_unverified_records(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    client.post(
        f"/api/pets/{pet_id}/health-records",
        json={
            "title": "Verified one",
            "occurred_at": "2024-01-01T00:00:00+00:00",
            "verification_status": "verified",
        },
        headers=auth_header(owner_token),
    )
    client.post(
        f"/api/pets/{pet_id}/health-records",
        json={
            "title": "Unverified one",
            "occurred_at": "2024-01-02T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )

    verified = client.get(
        f"/api/pets/{pet_id}/health-records?verified_only=true",
        headers=auth_header(owner_token),
    ).json()
    assert verified["total"] == 1
    assert verified["items"][0]["title"] == "Verified one"

    everything = client.get(
        f"/api/pets/{pet_id}/health-records", headers=auth_header(owner_token)
    ).json()
    assert everything["total"] == 2


def test_symptoms_inherit_verification_from_parent_health_record(
    client: TestClient, owner_token: str, owner_pet: dict
):
    """A child has no verification column of its own; the parent's decides."""
    pet_id = owner_pet["id"]
    unverified = client.post(
        f"/api/pets/{pet_id}/health-records",
        json={"title": "Draft", "occurred_at": "2024-01-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    ).json()
    client.post(
        f"/api/pets/{pet_id}/symptoms",
        json={
            "health_record_id": unverified["id"],
            "symptom_name": "Draft symptom",
        },
        headers=auth_header(owner_token),
    )

    verified_only = client.get(
        f"/api/pets/{pet_id}/symptoms?verified_only=true",
        headers=auth_header(owner_token),
    ).json()
    assert verified_only["total"] == 0

    everything = client.get(
        f"/api/pets/{pet_id}/symptoms", headers=auth_header(owner_token)
    ).json()
    assert everything["total"] == 1


def test_update_body_cannot_reparent_a_child_record(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record,
    make_child,
):
    pet_id = owner_pet["id"]
    first = make_health_record(owner_token, pet_id, title="First")
    second = make_health_record(owner_token, pet_id, title="Second")
    symptom = make_child(
        owner_token, pet_id, first["id"], "symptoms", symptom_name="coughing"
    )

    client.patch(
        f"/api/pets/{pet_id}/symptoms/{symptom['id']}",
        json={"health_record_id": second["id"], "symptom_name": "sneezing"},
        headers=auth_header(owner_token),
    )

    body = client.get(
        f"/api/pets/{pet_id}/symptoms/{symptom['id']}", headers=auth_header(owner_token)
    ).json()
    assert body["health_record_id"] == first["id"]
    assert body["symptom_name"] == "sneezing"


def test_record_from_another_pet_is_404_by_id(
    client: TestClient, owner_token: str, owner_pet: dict, make_pet,
    make_health_record,
):
    """A record id that exists but belongs to a different pet must 404."""
    other_pet = make_pet(owner_token, name="Other")
    record = make_health_record(owner_token, other_pet["id"])

    response = client.get(
        f"/api/pets/{owner_pet['id']}/health-records/{record['id']}",
        headers=auth_header(owner_token),
    )
    assert response.status_code == 404
