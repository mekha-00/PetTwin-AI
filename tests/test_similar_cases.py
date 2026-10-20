"""Phase 7 tests — similar-case retrieval over the external case table.

The embedding model is stubbed so these run in milliseconds: the tests cover the
CSV parsing, the feature construction for both sides, the ranking and filtering,
the service wiring, and the API contract. They do not depend on the real ONNX
model or the external file being present.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml import similar as similar_module
from app.ml import service as service_module
from app.ml.dataset import CaseRecord, load_cases, parse_row
from app.ml.features import features_for_case, features_for_pet


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def test_parse_row_extracts_fields() -> None:
    row = {
        "Animal_Type": "Dog",
        "Breed": "Labrador",
        "Age": "4",
        "Gender": "Male",
        "Weight": "25.0",
        "Symptom_1": "Fever",
        "Symptom_2": "Lethargy",
        "Symptom_3": "",
        "Symptom_4": "",
        "Duration": "3 days",
        "Appetite_Loss": "Yes",
        "Vomiting": "Yes",
        "Diarrhea": "No",
        "Coughing": "No",
        "Labored_Breathing": "No",
        "Lameness": "No",
        "Skin_Lesions": "No",
        "Nasal_Discharge": "No",
        "Eye_Discharge": "No",
        "Body_Temperature": "39.5\u00b0C",
        "Heart_Rate": "120",
        "Disease_Prediction": "Parvovirus",
    }
    case = parse_row(row, 0)
    assert case is not None
    assert case.animal_type == "Dog"
    assert case.age_years == 4.0
    assert case.weight_kg == 25.0
    assert case.symptoms == ["Fever", "Lethargy"]
    assert "appetite loss" in case.flags
    assert "vomiting" in case.flags
    assert case.body_temperature_c == 39.5
    assert case.heart_rate_bpm == 120.0
    assert case.disease == "Parvovirus"


def test_parse_row_drops_rows_without_label() -> None:
    assert parse_row({"Animal_Type": "Dog", "Disease_Prediction": ""}, 0) is None
    assert parse_row({"Animal_Type": "", "Disease_Prediction": "X"}, 0) is None


def test_parse_row_tolerates_missing_numbers() -> None:
    row = {"Animal_Type": "Cat", "Disease_Prediction": "Flu", "Age": "", "Body_Temperature": "n/a"}
    case = parse_row(row, 0)
    assert case is not None
    assert case.age_years is None
    assert case.body_temperature_c is None


def test_load_cases_handles_missing_file(tmp_path) -> None:
    assert load_cases(tmp_path / "nope.csv") == []


def test_load_cases_reads_the_real_file() -> None:
    """The shipped dataset must parse, and every case must carry a label."""
    cases = load_cases()
    assert len(cases) >= 400
    assert all(c.disease for c in cases)


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------
def test_case_features_include_species_and_symptoms() -> None:
    case = CaseRecord(
        index=0,
        animal_type="Dog",
        breed="Labrador",
        age_years=4.0,
        gender="Male",
        weight_kg=25.0,
        symptoms=["Fever", "Vomiting"],
        flags=["vomiting"],
        duration="3 days",
        body_temperature_c=39.5,
        heart_rate_bpm=120.0,
        disease="Parvovirus",
    )
    text = features_for_case(case)
    assert "species dog" in text
    assert "breed labrador" in text
    assert "symptom fever" in text
    # "Vomiting" and the vomiting flag must not both appear.
    assert text.count("symptom vomiting") == 1


def test_pet_features_match_case_shape() -> None:
    text = features_for_pet(
        species="dog",
        breed="Labrador",
        sex="male",
        age_months=48,
        weight_kg=25.0,
        symptom_names=["Fever", "Vomiting"],
    )
    assert "species dog" in text
    assert "breed labrador" in text
    assert "age adult" in text
    assert "size medium" in text
    assert "symptom fever" in text


def test_pet_features_dedupe_repeated_symptoms() -> None:
    text = features_for_pet(
        species="cat",
        breed=None,
        sex=None,
        age_months=12,
        weight_kg=4.0,
        symptom_names=["Coughing", "coughing", "Coughing"],
    )
    assert text.count("symptom coughing") == 1


def test_pet_features_without_symptoms_still_has_species() -> None:
    text = features_for_pet(
        species="dog", breed=None, sex=None, age_months=None, weight_kg=None, symptom_names=[]
    )
    assert text == "species dog"


# ---------------------------------------------------------------------------
# Ranking (embedder stubbed)
# ---------------------------------------------------------------------------
@pytest.fixture()
def fake_index(monkeypatch):
    """Install a tiny case index whose scores are controlled by the query text."""
    cases = [
        CaseRecord(0, "Dog", "Labrador", 4.0, "Male", 25.0, ["Fever"], [], "3 days", 39.5, 120.0, "Parvovirus"),
        CaseRecord(1, "Cat", "Siamese", 2.0, "Female", 4.5, ["Coughing"], [], "1 week", 38.9, 150.0, "URI"),
        CaseRecord(2, "Cow", "Holstein", 3.0, "Female", 600.0, ["Fever"], [], "5 days", 40.1, 90.0, "FMD"),
    ]
    matrix = np.eye(3, dtype=np.float32)
    similar_module.reset_index()
    monkeypatch.setattr(similar_module, "build_index", lambda: similar_module._CaseIndex(cases, matrix))
    monkeypatch.setattr(
        similar_module,
        "embed_query",
        lambda q: np.array(
            {"dog": [1.0, 0.0, 0.0], "cat": [0.0, 1.0, 0.0]}.get(q, [0.0, 0.0, 1.0]),
            dtype=np.float32,
        ),
    )
    yield
    similar_module.reset_index()


def test_find_similar_returns_best_match_first(fake_index) -> None:
    results = similar_module.find_similar("dog")
    assert results[0].disease == "Parvovirus"
    assert results[0].similarity == pytest.approx(1.0, abs=1e-6)


def test_find_similar_respects_top_k(fake_index) -> None:
    assert len(similar_module.find_similar("dog", top_k=1)) == 1


def test_find_similar_min_score_filters(fake_index) -> None:
    results = similar_module.find_similar("dog", top_k=3, min_score=0.5)
    assert [r.disease for r in results] == ["Parvovirus"]


def test_find_similar_empty_query_returns_nothing(fake_index) -> None:
    assert similar_module.find_similar("   ") == []


# ---------------------------------------------------------------------------
# Service query assembly
# ---------------------------------------------------------------------------
def test_build_query_features_reads_the_twin() -> None:
    snapshot = {
        "profile": {
            "name": "Rex",
            "species": "dog",
            "breed": "Beagle",
            "sex": "male",
            "age": {"total_months": 26},
            "current_weight_kg": 12.4,
        },
        "current_health_status": {
            "current_symptoms": [{"name": "Vomiting"}, {"name": "Lethargy"}],
        },
    }
    features, symptoms = service_module.build_query_features(snapshot)
    assert "species dog" in features
    assert "symptom vomiting" in features
    assert symptoms == ["Vomiting", "Lethargy"]


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------
def test_similar_cases_requires_authentication(client, owner_pet) -> None:
    assert client.get(f"/api/pets/{owner_pet['id']}/similar-cases").status_code == 401


def test_similar_cases_rejects_bad_top_k(client, owner_pet, owner_token) -> None:
    response = client.get(
        f"/api/pets/{owner_pet['id']}/similar-cases?top_k=99",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 422


def test_similar_cases_hides_another_users_pet(client, intruder_pet, owner_token) -> None:
    response = client.get(
        f"/api/pets/{intruder_pet['id']}/similar-cases",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 404


def test_similar_cases_happy_path(client, owner_pet, owner_token, monkeypatch) -> None:
    from app.ml.similar import SimilarCase

    def fake_find(features, top_k=5, min_score=0.0):
        return [
            SimilarCase(
                disease="Parvovirus",
                animal_type="Dog",
                breed="Beagle",
                age_years=2.0,
                gender="Male",
                weight_kg=12.0,
                symptoms=["Vomiting"],
                duration="3 days",
                body_temperature_c=39.5,
                heart_rate_bpm=120.0,
                similarity=0.91,
            )
        ][:top_k]

    monkeypatch.setattr(service_module, "find_similar", fake_find)
    monkeypatch.setattr(service_module, "index_size_safe", lambda: 431)

    response = client.get(
        f"/api/pets/{owner_pet['id']}/similar-cases",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pet_id"] == owner_pet["id"]
    assert body["cases"][0]["disease"] == "Parvovirus"
    assert body["corpus_size"] == 431
    assert body["disclaimer"]
