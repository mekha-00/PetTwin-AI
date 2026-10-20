"""Assemble a pet's query and run the similar-case search.

Builds the feature text from the pet's verified Digital Twin — species, breed,
sex, age, weight, and current symptom names — then asks
:mod:`app.ml.similar` for the closest recorded cases. Access is enforced the same
way as everywhere else, via ``load_accessible_pet``, so a pet the caller cannot
see returns the usual 404.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.ml.dataset import symptom_vocabulary
from app.ml.features import features_for_pet, features_for_symptoms
from app.ml.predict import Candidate, predict_conditions
from app.ml.similar import SimilarCase, find_similar
from app.services.authorization import load_accessible_pet
from app.services.digital_twin_service import build_digital_twin

#: Shown with every result set. The cases are records, not predictions.
DISCLAIMER = (
    "These are recorded cases that resemble this pet, from a small external "
    "dataset. They are shown for reference only and are not a diagnosis. Similar "
    "symptoms do not mean the same disease. A veterinarian must assess the pet."
)

#: Shown with candidate conditions. Explicit that the ordering is evidence, not
#: a probability, because the dataset cannot support a probability.
PREDICTION_DISCLAIMER = (
    "These conditions are ranked by how many recorded cases with similar "
    "symptoms carried each diagnosis. This is evidence from a small external "
    "dataset, not a probability and not a diagnosis. Many diseases share the "
    "same symptoms, so this cannot tell you what is wrong with the pet. A "
    "veterinarian must assess the pet."
)


@dataclass(frozen=True)
class SimilarCasesResult:
    pet_id: str
    pet_name: str
    query_symptoms: list[str]
    cases: list[SimilarCase] = field(default_factory=list)
    corpus_size: int = 0
    disclaimer: str = DISCLAIMER


def build_query_features(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (feature_text, symptom_names) from a twin snapshot."""
    profile = snapshot.get("profile", {})
    status = snapshot.get("current_health_status", {})
    age = profile.get("age")
    age_months = None
    if isinstance(age, dict):
        age_months = age.get("total_months")

    symptom_names = [
        s.get("name", "") for s in (status.get("current_symptoms") or []) if s.get("name")
    ]

    features = features_for_pet(
        species=profile.get("species"),
        breed=profile.get("breed"),
        sex=profile.get("sex"),
        age_months=age_months,
        weight_kg=profile.get("current_weight_kg") or status.get("weight_kg"),
        symptom_names=symptom_names,
    )
    return features, symptom_names


def find_similar_cases(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    top_k: int = 5,
) -> SimilarCasesResult:
    """Return cases similar to this pet, after checking the caller may see it."""
    load_accessible_pet(db, pet_id=pet_id, user_id=user_id)
    snapshot = build_digital_twin(db, pet_id=pet_id, user_id=user_id)

    features, symptom_names = build_query_features(snapshot)
    cases = find_similar(features, top_k=top_k) if features.strip() else []

    return SimilarCasesResult(
        pet_id=str(pet_id),
        pet_name=snapshot.get("profile", {}).get("name", "this pet"),
        query_symptoms=symptom_names,
        cases=cases,
        corpus_size=index_size_safe(),
    )


def index_size_safe() -> int:
    """Case count, or 0 if the corpus is missing or the model is unavailable."""
    try:
        from app.ml.similar import index_size

        return index_size()
    except Exception:  # pragma: no cover - depends on local corpus/model
        return 0


@dataclass(frozen=True)
class PredictionResult:
    pet_id: str
    pet_name: str
    species: str | None
    used_symptoms: list[str] = field(default_factory=list)
    symptoms_overridden: bool = False
    candidates: list[Candidate] = field(default_factory=list)
    corpus_size: int = 0
    disclaimer: str = PREDICTION_DISCLAIMER


def prediction_options(db: Session, *, pet_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Everything the picker needs: the full vocabulary and this pet's defaults.

    The defaults come from the pet's verified twin, so the UI can prefill the
    form with the symptoms already recorded and let the user edit from there.
    """
    load_accessible_pet(db, pet_id=pet_id, user_id=user_id)
    snapshot = build_digital_twin(db, pet_id=pet_id, user_id=user_id)
    _, symptom_names = build_query_features(snapshot)
    profile = snapshot.get("profile", {})
    return {
        "vocabulary": symptom_vocabulary(),
        "default_symptoms": symptom_names,
        "default_species": profile.get("species"),
    }


def predict_conditions_for_pet(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    symptoms: list[str] | None = None,
    species: str | None = None,
    top_k: int = 5,
) -> PredictionResult:
    """Rank candidate conditions for a pet from similar recorded cases.

    When ``symptoms`` is omitted the pet's verified twin supplies them (the
    prefill case). When provided, the user's selection is used instead and the
    pet's breed/sex/age/weight still come from the twin so the query stays
    grounded in the pet's own profile.
    """
    load_accessible_pet(db, pet_id=pet_id, user_id=user_id)
    snapshot = build_digital_twin(db, pet_id=pet_id, user_id=user_id)
    profile = snapshot.get("profile", {})

    twin_features, twin_symptoms = build_query_features(snapshot)
    age = profile.get("age")
    age_months = age.get("total_months") if isinstance(age, dict) else None

    overridden = symptoms is not None
    used_symptoms = list(symptoms) if overridden else twin_symptoms
    used_species = species or profile.get("species")

    if overridden:
        features = features_for_symptoms(
            species=used_species,
            breed=profile.get("breed"),
            sex=profile.get("sex"),
            age_months=age_months,
            weight_kg=profile.get("current_weight_kg"),
            symptoms=used_symptoms,
        )
    else:
        features = twin_features

    candidates = predict_conditions(features, top_k=top_k) if features.strip() else []

    return PredictionResult(
        pet_id=str(pet_id),
        pet_name=profile.get("name", "this pet"),
        species=used_species,
        used_symptoms=used_symptoms,
        symptoms_overridden=overridden,
        candidates=candidates,
        corpus_size=index_size_safe(),
    )

