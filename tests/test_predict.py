"""Tests for the evidence-based candidate-condition ranking (Phase 7 extension).

These are offline: the embedding model is never loaded and the similar-case
search is stubbed. They cover the aggregation maths, the "not a probability"
contract, the service prefill/override behaviour, and the API surface.
"""

from __future__ import annotations

import pytest

from app.ml import predict as predict_module
from app.ml import service as service_module
from app.ml.dataset import symptom_vocabulary
from app.ml.features import features_for_symptoms
from app.ml.predict import Candidate, aggregate_candidates, predict_conditions
from app.ml.similar import SimilarCase


def _case(disease: str, similarity: float, symptoms=("Vomiting",)) -> SimilarCase:
    return SimilarCase(
        disease=disease,
        animal_type="Dog",
        breed="Beagle",
        age_years=2.0,
        gender="Male",
        weight_kg=12.0,
        symptoms=list(symptoms),
        duration="3 days",
        body_temperature_c=39.5,
        heart_rate_bpm=120.0,
        similarity=similarity,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_aggregate_groups_by_disease_and_counts() -> None:
    cases = [
        _case("Parvovirus", 0.9),
        _case("Parvovirus", 0.8),
        _case("Distemper", 0.7),
    ]
    candidates = aggregate_candidates(cases, top_k=5)
    by_name = {c.disease: c for c in candidates}
    assert by_name["Parvovirus"].case_count == 2
    assert by_name["Distemper"].case_count == 1


def test_aggregate_averages_similarity() -> None:
    candidates = aggregate_candidates(
        [_case("Parvovirus", 0.9), _case("Parvovirus", 0.7)], top_k=5
    )
    assert candidates[0].avg_similarity == pytest.approx(0.8)
    assert candidates[0].top_similarity == pytest.approx(0.9)


def test_aggregate_orders_by_evidence_not_raw_similarity() -> None:
    # Two solid cases should outrank one marginally closer case.
    cases = [
        _case("Many", 0.80),
        _case("Many", 0.80),
        _case("One", 0.85),
    ]
    candidates = aggregate_candidates(cases, top_k=5)
    assert candidates[0].disease == "Many"


def test_aggregate_respects_top_k() -> None:
    cases = [_case("A", 0.9), _case("B", 0.8), _case("C", 0.7)]
    assert len(aggregate_candidates(cases, top_k=2)) == 2


def test_evidence_score_is_documented_as_not_a_probability() -> None:
    """The score must never be presented as a confidence."""
    assert "not a probability" in predict_module.__doc__.lower()


def test_supporting_symptoms_are_deduplicated() -> None:
    candidates = aggregate_candidates(
        [_case("P", 0.9, ("Vomiting", "Vomiting", "Lethargy"))], top_k=5
    )
    assert candidates[0].supporting_symptoms == ["Vomiting", "Lethargy"]


def test_predict_conditions_empty_query_returns_nothing() -> None:
    assert predict_conditions("   ") == []


# ---------------------------------------------------------------------------
# Features / vocabulary
# ---------------------------------------------------------------------------
def test_features_for_symptoms_matches_pet_shape() -> None:
    text = features_for_symptoms(
        species="dog",
        breed="Beagle",
        sex="male",
        age_months=24,
        weight_kg=12.0,
        symptoms=["Vomiting", "Lethargy"],
    )
    assert "species dog" in text
    assert "symptom vomiting" in text
    assert "symptom lethargy" in text


def test_symptom_vocabulary_is_non_empty_and_sorted() -> None:
    vocab = symptom_vocabulary()
    assert len(vocab) >= 20
    assert vocab == sorted(vocab, key=str.lower)


# ---------------------------------------------------------------------------
# Service: prefill vs override
# ---------------------------------------------------------------------------
def test_service_prefills_from_twin(client, owner_pet, owner_token, monkeypatch) -> None:
    captured: dict = {}

    def fake_predict(features, *, gather=25, top_k=5):
        captured["features"] = features
        return [Candidate("Parvovirus", 2, 0.9, 0.95, 1.8, ["Vomiting"])]

    monkeypatch.setattr(service_module, "predict_conditions", fake_predict)
    monkeypatch.setattr(service_module, "index_size_safe", lambda: 431)

    response = client.post(
        f"/api/pets/{owner_pet['id']}/predict-conditions",
        json={},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symptoms_overridden"] is False
    assert body["candidates"][0]["disease"] == "Parvovirus"
    assert body["corpus_size"] == 431
    assert "not a probability" in body["disclaimer"].lower()


def test_service_override_uses_supplied_symptoms(
    client, owner_pet, owner_token, monkeypatch
) -> None:
    captured: dict = {}

    def fake_predict(features, *, gather=25, top_k=5):
        captured["features"] = features
        return []

    monkeypatch.setattr(service_module, "predict_conditions", fake_predict)

    response = client.post(
        f"/api/pets/{owner_pet['id']}/predict-conditions",
        json={"symptoms": ["Coughing", "Fever"]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symptoms_overridden"] is True
    assert body["used_symptoms"] == ["Coughing", "Fever"]
    assert "symptom coughing" in captured["features"]


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------
def test_symptom_options_requires_auth(client, owner_pet) -> None:
    assert client.get(f"/api/pets/{owner_pet['id']}/symptom-options").status_code == 401


def test_symptom_options_returns_vocabulary(client, owner_pet, owner_token) -> None:
    response = client.get(
        f"/api/pets/{owner_pet['id']}/symptom-options",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["vocabulary"]) >= 20
    assert "default_species" in body


def test_predict_conditions_requires_auth(client, owner_pet) -> None:
    assert (
        client.post(f"/api/pets/{owner_pet['id']}/predict-conditions", json={}).status_code
        == 401
    )


def test_predict_conditions_rejects_bad_top_k(client, owner_pet, owner_token) -> None:
    response = client.post(
        f"/api/pets/{owner_pet['id']}/predict-conditions?top_k=99",
        json={},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 422


def test_predict_conditions_rejects_too_many_symptoms(
    client, owner_pet, owner_token
) -> None:
    response = client.post(
        f"/api/pets/{owner_pet['id']}/predict-conditions",
        json={"symptoms": [f"s{i}" for i in range(60)]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 422


def test_predict_conditions_hides_another_users_pet(
    client, intruder_pet, owner_token
) -> None:
    response = client.post(
        f"/api/pets/{intruder_pet['id']}/predict-conditions",
        json={},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 404
