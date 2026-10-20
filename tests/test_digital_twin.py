"""Phase 3 — Digital Twin assembly and health timeline generation.

These tests pin down what the twin is allowed to be. The recurring theme is
that the twin **derives** profile-level facts from the record tables rather than
reading them from a column, and that it never invents a clinical judgement.
"""

from conftest import auth_header
from fastapi.testclient import TestClient


def twin(client: TestClient, token: str, pet_id: str) -> dict:
    response = client.get(
        f"/api/pets/{pet_id}/digital-twin", headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
def test_twin_has_all_documented_sections(
    client: TestClient, owner_token: str, populated_pet: dict
):
    body = twin(client, owner_token, populated_pet["id"])
    for section in (
        "profile",
        "current_health_status",
        "medical_history",
        "current_symptoms",
        "diagnoses",
        "medications",
        "vaccinations",
        "laboratory_results",
        "veterinary_visits",
        "health_timeline",
        "provenance",
    ):
        assert section in body, f"missing section: {section}"


def test_twin_profile_carries_identity(
    client: TestClient, owner_token: str, populated_pet: dict
):
    profile = twin(client, owner_token, populated_pet["id"])["profile"]
    assert profile["name"] == "Bella"
    assert profile["species"] == "dog"
    assert profile["breed"] == "Labrador"
    assert profile["sex"] == "female"
    assert profile["current_weight_kg"] == 28.5
    assert profile["notes"] == "Friendly but nervous around nail trims."


def test_twin_states_it_is_software_based_and_not_ai(
    client: TestClient, owner_token: str, populated_pet: dict
):
    body = twin(client, owner_token, populated_pet["id"])
    assert body["twin_type"] == "software_based_record_assembly"
    disclaimer = body["disclaimer"].lower()
    assert "not sensor-based" in disclaimer
    assert "no ai analysis" in disclaimer
    assert "not a diagnosis" in disclaimer


def _all_keys(node) -> set[str]:
    """Every mapping key anywhere in a nested JSON structure."""
    keys: set[str] = set()
    if isinstance(node, dict):
        keys.update(node.keys())
        for value in node.values():
            keys.update(_all_keys(value))
    elif isinstance(node, list):
        for item in node:
            keys.update(_all_keys(item))
    return keys


def test_twin_contains_no_prediction_or_recommendation_fields(
    client: TestClient, owner_token: str, populated_pet: dict
):
    """A future agent needs a stable shape; Phase 3 must not pre-empt one.

    Keys are inspected rather than raw text, because the disclaimer legitimately
    contains the words "recommendation" and "diagnosis" while *asserting their
    absence*. Only field names matter here.
    """
    keys = _all_keys(twin(client, owner_token, populated_pet["id"]))
    for forbidden in (
        "risk_score",
        "risk_level",
        "risk",
        "recommendation",
        "recommendations",
        "suggested_treatment",
        "treatment",
        "predicted_disease",
        "diagnosis_probability",
        "probability",
        "prescription",
        "advice",
        "severity_score",
    ):
        assert forbidden not in keys, f"twin leaked a {forbidden} field"


def test_empty_pet_yields_empty_sections_not_errors(
    client: TestClient, owner_token: str, owner_pet: dict
):
    body = twin(client, owner_token, owner_pet["id"])
    status = body["current_health_status"]
    assert status["existing_conditions"] == []
    assert status["current_symptoms"] == []
    assert status["current_medications"] == []
    assert status["allergies"] == []
    assert body["medical_history"] == []
    assert body["health_timeline"] == []
    assert status["vaccination_status"]["status"] == "none_recorded"


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------
def test_existing_conditions_derived_from_active_diagnoses(
    client: TestClient, owner_token: str, populated_pet: dict
):
    conditions = twin(client, owner_token, populated_pet["id"])["current_health_status"][
        "existing_conditions"
    ]
    assert [c["name"] for c in conditions] == ["Patellar luxation"]
    assert conditions[0]["is_confirmed"] is True


def test_resolved_diagnosis_leaves_existing_conditions(
    client: TestClient, owner_token: str, populated_pet: dict, make_health_record
):
    pet_id = populated_pet["id"]
    conditions = twin(client, owner_token, pet_id)["current_health_status"][
        "existing_conditions"
    ]
    diagnosis_id = conditions[0]["id"]

    client.patch(
        f"/api/pets/{pet_id}/diagnoses/{diagnosis_id}",
        json={"status": "resolved", "resolved_at": "2024-06-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )

    after = twin(client, owner_token, pet_id)["current_health_status"][
        "existing_conditions"
    ]
    assert after == []


def test_current_medications_derived_from_active_medication_records(
    client: TestClient, owner_token: str, populated_pet: dict
):
    medications = twin(client, owner_token, populated_pet["id"])["current_health_status"][
        "current_medications"
    ]
    assert [m["name"] for m in medications] == ["Meloxicam"]
    assert medications[0]["dose"] == "1.5 mg"
    assert medications[0]["frequency"] == "once daily"


def test_ended_medication_drops_out_of_current_medications(
    client: TestClient, owner_token: str, populated_pet: dict
):
    pet_id = populated_pet["id"]
    medication = twin(client, owner_token, pet_id)["current_health_status"][
        "current_medications"
    ][0]

    client.patch(
        f"/api/pets/{pet_id}/medications/{medication['id']}",
        json={"is_active": False, "ended_at": "2024-05-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )

    after = twin(client, owner_token, pet_id)["current_health_status"][
        "current_medications"
    ]
    assert after == []


def test_allergies_come_from_the_allergy_table(
    client: TestClient, owner_token: str, populated_pet: dict
):
    allergies = twin(client, owner_token, populated_pet["id"])["current_health_status"][
        "allergies"
    ]
    assert {a["allergen"] for a in allergies} == {"chicken", "penicillin"}
    penicillin = next(a for a in allergies if a["allergen"] == "penicillin")
    assert penicillin["severity"] == 4
    assert penicillin["reaction"] == "vomiting"


def test_vaccination_status_is_derived_not_stored(
    client: TestClient, owner_token: str, populated_pet: dict
):
    """Rabies is future-dated, DHPP is overdue, so overall is 'overdue'."""
    status = twin(client, owner_token, populated_pet["id"])["current_health_status"][
        "vaccination_status"
    ]
    assert status["status"] == "overdue"
    assert status["vaccines_tracked"] == 2
    assert status["overdue_count"] == 1
    assert status["overdue"][0]["vaccine"] == "DHPP"
    assert status["upcoming"][0]["vaccine"] == "Rabies"


def test_vaccination_status_becomes_up_to_date_when_nothing_overdue(
    client: TestClient, owner_token: str, populated_pet: dict
):
    pet_id = populated_pet["id"]
    for vaccination in twin(client, owner_token, pet_id)["vaccinations"]:
        client.patch(
            f"/api/pets/{pet_id}/vaccinations/{vaccination['id']}",
            json={"next_due_at": "2030-01-01T00:00:00+00:00"},
            headers=auth_header(owner_token),
        )

    status = twin(client, owner_token, pet_id)["current_health_status"][
        "vaccination_status"
    ]
    assert status["status"] == "up_to_date"
    assert status["overdue_count"] == 0


def test_resolved_symptom_leaves_current_symptoms(
    client: TestClient, owner_token: str, populated_pet: dict
):
    pet_id = populated_pet["id"]
    symptom = twin(client, owner_token, pet_id)["current_health_status"][
        "current_symptoms"
    ][0]
    assert symptom["name"] == "favouring left hind leg"

    client.patch(
        f"/api/pets/{pet_id}/symptoms/{symptom['id']}",
        json={"resolved_at": "2024-04-01T00:00:00+00:00"},
        headers=auth_header(owner_token),
    )

    after = twin(client, owner_token, pet_id)["current_health_status"][
        "current_symptoms"
    ]
    assert after == []


def test_lab_results_included_with_reference_range(
    client: TestClient, owner_token: str, populated_pet: dict
):
    results = twin(client, owner_token, populated_pet["id"])["laboratory_results"]
    assert len(results) == 1
    assert results[0]["test_name"] == "Complete Blood Count"
    assert results[0]["result"] == "5.2 10^9/L"
    assert results[0]["reference_low"] == 4.5
    assert results[0]["reference_high"] == 8.5


def test_medical_history_contains_verified_records(
    client: TestClient, owner_token: str, populated_pet: dict
):
    history = twin(client, owner_token, populated_pet["id"])["medical_history"]
    assert [h["title"] for h in history] == ["Lameness assessment"]
    assert history[0]["record_type"] == "consultation"


def test_unverified_records_excluded_from_current_state(
    client: TestClient, owner_token: str, owner_pet: dict
):
    """An unverified draft must not be reported as a known condition."""
    pet_id = owner_pet["id"]
    record = client.post(
        f"/api/pets/{pet_id}/health-records",
        json={
            "title": "Draft note",
            "occurred_at": "2024-01-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    ).json()
    client.post(
        f"/api/pets/{pet_id}/diagnoses",
        json={
            "health_record_id": record["id"],
            "diagnosis_name": "Unconfirmed lump",
            "status": "active",
            "diagnosed_at": "2024-01-01T00:00:00+00:00",
        },
        headers=auth_header(owner_token),
    )

    body = twin(client, owner_token, pet_id)
    # The diagnosis still appears in provenance totals, proving the row exists…
    assert body["provenance"]["total_counts"]["health_records"] == 1
    assert body["provenance"]["verified_counts"]["health_records"] == 0
    # …but is not presented as an established condition.
    assert body["medical_history"] == []


def test_age_computed_from_date_of_birth(
    client: TestClient, owner_token: str, make_pet
):
    pet = make_pet(owner_token, name="Puppy", date_of_birth="2021-05-20")
    age = twin(client, owner_token, pet["id"])["profile"]["age"]
    assert age is not None
    assert age["approximate"] is False
    assert age["total_months"] > 0


def test_age_from_estimate_is_marked_approximate(
    client: TestClient, owner_token: str, make_pet
):
    pet = make_pet(
        owner_token, name="Rescue", date_of_birth=None, estimated_age_months=30
    )
    age = twin(client, owner_token, pet["id"])["profile"]["age"]
    assert age["approximate"] is True
    assert age["years"] == 2
    assert age["months"] == 6


def test_pet_with_no_age_information(
    client: TestClient, owner_token: str, make_pet
):
    pet = make_pet(
        owner_token, name="Unknown", date_of_birth=None, estimated_age_months=None
    )
    assert twin(client, owner_token, pet["id"])["profile"]["age"] is None


# ---------------------------------------------------------------------------
# The twin is not a table
# ---------------------------------------------------------------------------
def test_digital_twin_is_not_a_database_table(engine):
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    assert "digital_twin" not in tables
    assert "digital_twins" not in tables
    assert "pet_digital_twins" not in tables


def test_twin_reflects_new_records_without_any_persist_step(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record
):
    """The 'updates automatically' guarantee: read again, state is current."""
    pet_id = owner_pet["id"]
    assert twin(client, owner_token, pet_id)["medical_history"] == []

    record = make_health_record(owner_token, pet_id, title="New consultation")
    assert [h["id"] for h in twin(client, owner_token, pet_id)["medical_history"]] == [
        record["id"]
    ]


def test_provenance_reports_verified_and_total_counts(
    client: TestClient, owner_token: str, populated_pet: dict
):
    provenance = twin(client, owner_token, populated_pet["id"])["provenance"]
    assert provenance["verified_counts"]["health_records"] == 1
    assert provenance["verified_counts"]["lab_reports"] == 1
    assert provenance["excluded_source_types"] == ["ai_analysis"]


def test_twin_requires_authentication(client: TestClient, populated_pet: dict):
    assert client.get(
        f"/api/pets/{populated_pet['id']}/digital-twin"
    ).status_code == 401


# ---------------------------------------------------------------------------
# Health timeline
# ---------------------------------------------------------------------------
def timeline(client: TestClient, token: str, pet_id: str, **params) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    suffix = f"?{query}" if query else ""
    response = client.get(
        f"/api/pets/{pet_id}/health-timeline{suffix}", headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_timeline_merges_every_record_type(
    client: TestClient, owner_token: str, populated_pet: dict
):
    body = timeline(client, owner_token, populated_pet["id"])
    kinds = {item["event_type"] for item in body["items"]}
    assert "visit" in kinds
    assert "symptom" in kinds
    assert "diagnosis" in kinds
    assert "medication_started" in kinds
    assert "vaccination" in kinds
    assert "lab_result" in kinds
    assert body["total"] == len(body["items"])


def test_timeline_is_reverse_chronological(
    client: TestClient, owner_token: str, populated_pet: dict
):
    items = timeline(client, owner_token, populated_pet["id"])["items"]
    timestamps = [item["occurred_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)


def test_timeline_entries_carry_source_provenance(
    client: TestClient, owner_token: str, populated_pet: dict
):
    for item in timeline(client, owner_token, populated_pet["id"])["items"]:
        assert item["source_table"]
        assert item["title"]


def test_timeline_pagination_window(
    client: TestClient, owner_token: str, populated_pet: dict
):
    full = timeline(client, owner_token, populated_pet["id"])
    page = timeline(client, owner_token, populated_pet["id"], limit=2, offset=0)
    assert len(page["items"]) == 2
    assert page["items"][0]["source_id"] == full["items"][0]["source_id"]
    assert page["items"][1]["source_id"] == full["items"][1]["source_id"]


def test_timeline_excludes_unverified_by_default(
    client: TestClient, owner_token: str, owner_pet: dict
):
    """A draft record's events are hidden by default but still retrievable."""
    pet_id = owner_pet["id"]
    for title, status, when in (
        ("Draft", "unverified", "2024-01-01T00:00:00+00:00"),
        ("Confirmed", "verified", "2024-01-02T00:00:00+00:00"),
    ):
        record = client.post(
            f"/api/pets/{pet_id}/health-records",
            json={"title": title, "occurred_at": when, "verification_status": status},
            headers=auth_header(owner_token),
        ).json()
        # A health record with no children emits no timeline event of its own,
        # so each draft needs a symptom to be observable on the timeline.
        client.post(
            f"/api/pets/{pet_id}/symptoms",
            json={
                "health_record_id": record["id"],
                "symptom_name": f"{title} symptom",
                "onset_at": when,
            },
            headers=auth_header(owner_token),
        )

    verified = timeline(client, owner_token, pet_id, verified_only="true")
    verified_titles = {item["title"] for item in verified["items"]}
    assert "Draft symptom" not in verified_titles
    assert "Confirmed symptom" in verified_titles

    everything = timeline(client, owner_token, pet_id, verified_only="false")
    titles = {item["title"] for item in everything["items"]}
    assert "Draft symptom" in titles
    assert "Confirmed symptom" in titles


def test_empty_timeline_for_pet_with_no_records(
    client: TestClient, owner_token: str, owner_pet: dict
):
    body = timeline(client, owner_token, owner_pet["id"])
    assert body["items"] == []
    assert body["total"] == 0


def test_timeline_requires_authentication(client: TestClient, populated_pet: dict):
    assert client.get(
        f"/api/pets/{populated_pet['id']}/health-timeline"
    ).status_code == 401


def test_timeline_and_twin_agree_on_event_count(
    client: TestClient, owner_token: str, populated_pet: dict
):
    """The twin embeds the timeline, so the two endpoints cannot diverge."""
    pet_id = populated_pet["id"]
    twin_items = twin(client, owner_token, pet_id)["health_timeline"]
    timeline_items = timeline(client, owner_token, pet_id)["items"]
    assert len(twin_items) == len(timeline_items)
    assert [i["source_id"] for i in twin_items] == [
        i["source_id"] for i in timeline_items
    ]

# ---------------------------------------------------------------------------
# Verification gating
#
# An unverified entry is something the owner typed but no veterinarian has
# confirmed. It must stay retrievable through the record endpoints, but it must
# not be presented as established health state, because the twin's
# current_conditions / current_medications / vaccination_status sections are
# stated as facts about the pet.
# ---------------------------------------------------------------------------
def test_unverified_diagnosis_is_not_an_existing_condition(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record, make_child
):
    pet_id = owner_pet["id"]
    record = make_health_record(
        owner_token, pet_id, title="Draft", verification_status="unverified"
    )
    make_child(
        owner_token, pet_id, record["id"], "diagnoses",
        diagnosis_name="Suspected arthritis",
        diagnosed_at="2024-01-01T00:00:00+00:00",
        status="active",
        is_confirmed=False,
    )

    status = twin(client, owner_token, pet_id)["current_health_status"]
    assert [c["name"] for c in status["existing_conditions"]] == []
    assert [d["name"] for d in twin(client, owner_token, pet_id)["diagnoses"]] == []


def test_unverified_medication_is_not_a_current_medication(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record, make_child
):
    pet_id = owner_pet["id"]
    record = make_health_record(
        owner_token, pet_id, title="Draft", verification_status="unverified"
    )
    make_child(
        owner_token, pet_id, record["id"], "medications",
        medication_name="Unconfirmed antibiotic",
        started_at="2024-01-01T00:00:00+00:00",
        is_active=True,
    )

    body = twin(client, owner_token, pet_id)
    assert body["current_health_status"]["current_medications"] == []
    assert body["current_medications"] == []


def test_unverified_vaccine_does_not_set_vaccination_status(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record, make_child
):
    """Vaccination status is *derived*, so an unverified dose would assert a fact."""
    pet_id = owner_pet["id"]
    record = make_health_record(
        owner_token, pet_id, title="Draft", verification_status="unverified"
    )
    make_child(
        owner_token, pet_id, record["id"], "vaccinations",
        vaccine_name="Rabies",
        administered_at="2024-01-01T00:00:00+00:00",
    )

    status = twin(client, owner_token, pet_id)["current_health_status"]["vaccination_status"]
    assert status["status"] == "none_recorded"
    assert status["vaccines_tracked"] == 0
    assert twin(client, owner_token, pet_id)["vaccinations"] == []


def test_unverified_visit_is_not_treated_as_a_visit(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    client.post(
        f"/api/pets/{pet_id}/visits",
        json={
            "visit_at": "2024-05-01T10:00:00+00:00",
            "visit_type": "wellness",
            "status": "completed",
            "verification_status": "unverified",
        },
        headers=auth_header(owner_token),
    )

    body = twin(client, owner_token, pet_id)
    assert body["veterinary_visits"] == []
    assert body["current_health_status"]["last_visit_at"] is None


def test_unverified_allergy_is_not_in_health_status(
    client: TestClient, owner_token: str, owner_pet: dict
):
    pet_id = owner_pet["id"]
    created = client.post(
        f"/api/pets/{pet_id}/allergies",
        json={"allergen": "Peanuts", "verification_status": "unverified"},
        headers=auth_header(owner_token),
    )
    assert created.status_code == 201, created.text

    assert twin(client, owner_token, pet_id)["current_health_status"]["allergies"] == []


def test_timeline_excludes_unverified_diagnosis_medication_and_vaccine(
    client: TestClient, owner_token: str, owner_pet: dict, make_health_record, make_child
):
    """The three sections that previously ignored verification entirely."""
    pet_id = owner_pet["id"]
    record = make_health_record(
        owner_token, pet_id, title="Draft", verification_status="unverified"
    )
    make_child(
        owner_token, pet_id, record["id"], "diagnoses",
        diagnosis_name="UnconfirmedDx", diagnosed_at="2024-01-01T00:00:00+00:00",
    )
    make_child(
        owner_token, pet_id, record["id"], "medications",
        medication_name="UnconfirmedMed", started_at="2024-01-02T00:00:00+00:00",
    )
    make_child(
        owner_token, pet_id, record["id"], "vaccinations",
        vaccine_name="UnconfirmedVac", administered_at="2024-01-03T00:00:00+00:00",
    )

    verified = timeline(client, owner_token, pet_id, verified_only="true")
    titles = {item["title"] for item in verified["items"]}
    assert not {"UnconfirmedDx", "UnconfirmedMed", "UnconfirmedVac"} & titles

    everything = timeline(client, owner_token, pet_id, verified_only="false")
    all_titles = {item["title"] for item in everything["items"]}
    assert "UnconfirmedDx" in all_titles
    assert "UnconfirmedMed" in all_titles
    assert "UnconfirmedVac" in all_titles


def test_timeline_total_is_the_full_count_not_the_page_size(
    client: TestClient, owner_token: str, owner_pet: dict
):
    """Regression: `total` used to be the length of the truncated window."""
    pet_id = owner_pet["id"]
    for month in range(1, 7):
        client.post(
            f"/api/pets/{pet_id}/visits",
            json={
                "visit_at": f"2024-{month:02d}-01T10:00:00+00:00",
                "visit_type": "wellness",
                "status": "completed",
                "verification_status": "verified",
            },
            headers=auth_header(owner_token),
        )

    first_page = timeline(client, owner_token, pet_id, limit="2", offset="0")
    assert len(first_page["items"]) == 2
    assert first_page["total"] == 6

    second_page = timeline(client, owner_token, pet_id, limit="2", offset="2")
    assert len(second_page["items"]) == 2
    # The reported total must not shrink just because the caller paged further.
    assert second_page["total"] == first_page["total"]

    last_page = timeline(client, owner_token, pet_id, limit="2", offset="4")
    assert len(last_page["items"]) == 2

    past_the_end = timeline(client, owner_token, pet_id, limit="2", offset="6")
    assert past_the_end["items"] == []
    assert past_the_end["total"] == 6


def test_provenance_counts_include_every_record_type(
    client: TestClient, owner_token: str, populated_pet: dict
):
    """Regression: diagnoses, visits and allergies were missing from provenance."""
    provenance = twin(client, owner_token, populated_pet["id"])["provenance"]
    for key in (
        "health_records",
        "diagnosis_records",
        "symptom_records",
        "medication_records",
        "vaccination_records",
        "lab_reports",
        "veterinary_visits",
        "pet_allergies",
    ):
        assert key in provenance["verified_counts"], key
        assert key in provenance["total_counts"], key
