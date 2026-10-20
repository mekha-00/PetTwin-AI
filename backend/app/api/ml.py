"""Similar-case API — retrieval over the external labelled case table.

``GET /pets/{pet_id}/similar-cases`` returns recorded cases that resemble this
pet, ranked by feature similarity. It is retrieval, not prediction: each case
carries the diagnosis that was recorded for it and the resemblance the search
found, and the response says plainly that this is not a diagnosis.

``POST /pets/{pet_id}/predict-conditions`` ranks *candidate conditions* by how
many of those similar cases carried each recorded diagnosis. It is evidence
aggregation from a small external dataset, **not** a trained classifier and
**not** a probability. ``GET /pets/{pet_id}/symptom-options`` supplies the
symptom vocabulary and the pet's twin-derived defaults for the picker.

Access is enforced in the service before the twin is read, so an inaccessible pet
returns 404 exactly as elsewhere in the API. Every endpoint here is read-only.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.ml.service import (
    find_similar_cases,
    predict_conditions_for_pet,
    prediction_options,
)
from app.rag.embeddings import EmbeddingUnavailableError

router = APIRouter(prefix="/pets", tags=["similar cases"])

PetPath = Annotated[uuid.UUID, Path(description="Target pet id")]


class SimilarCaseRead(BaseModel):
    disease: str
    animal_type: str
    breed: str | None = None
    age_years: float | None = None
    gender: str | None = None
    weight_kg: float | None = None
    symptoms: list[str] = []
    duration: str | None = None
    body_temperature_c: float | None = None
    heart_rate_bpm: float | None = None
    similarity: float


class SimilarCasesResponse(BaseModel):
    pet_id: str
    pet_name: str
    query_symptoms: list[str] = []
    cases: list[SimilarCaseRead] = []
    corpus_size: int = 0
    disclaimer: str


@router.get(
    "/{pet_id}/similar-cases",
    response_model=SimilarCasesResponse,
    summary="Recorded cases that resemble this pet",
)
def get_similar_cases(
    pet_id: PetPath,
    db: DbSession,
    current_user: CurrentUser,
    top_k: Annotated[int, Query(ge=1, le=10)] = 5,
) -> SimilarCasesResponse:
    """Return recorded cases similar to this pet, most similar first.

    This is retrieval over a small external dataset, not a prediction model. The
    resemblance score orders the results; it is not a probability of disease.
    """
    try:
        result = find_similar_cases(
            db, pet_id=pet_id, user_id=current_user.id, top_k=top_k
        )
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The case index is unavailable: {exc}",
        ) from exc

    return SimilarCasesResponse(
        pet_id=result.pet_id,
        pet_name=result.pet_name,
        query_symptoms=result.query_symptoms,
        cases=[SimilarCaseRead(**case.__dict__) for case in result.cases],
        corpus_size=result.corpus_size,
        disclaimer=result.disclaimer,
    )


# ---------------------------------------------------------------------------
# Candidate conditions (evidence aggregation)
# ---------------------------------------------------------------------------
class SymptomOptionsResponse(BaseModel):
    vocabulary: list[str] = []
    default_symptoms: list[str] = []
    default_species: str | None = None


class CandidateRead(BaseModel):
    disease: str
    case_count: int
    avg_similarity: float
    top_similarity: float
    #: Relative ranking weight. NOT a probability — the dataset cannot support one.
    evidence_score: float
    supporting_symptoms: list[str] = []


class PredictConditionsRequest(BaseModel):
    #: Omit to use the pet's twin symptoms. Provide (possibly empty) to override.
    symptoms: list[str] | None = Field(default=None, max_length=50)
    species: str | None = Field(default=None, max_length=50)


class PredictConditionsResponse(BaseModel):
    pet_id: str
    pet_name: str
    species: str | None = None
    used_symptoms: list[str] = []
    symptoms_overridden: bool = False
    candidates: list[CandidateRead] = []
    corpus_size: int = 0
    disclaimer: str


@router.get(
    "/{pet_id}/symptom-options",
    response_model=SymptomOptionsResponse,
    summary="Symptom vocabulary and this pet's defaults for the picker",
)
def get_symptom_options(
    pet_id: PetPath,
    db: DbSession,
    current_user: CurrentUser,
) -> SymptomOptionsResponse:
    """Return the symptom vocabulary and this pet's twin-derived defaults."""
    try:
        options = prediction_options(db, pet_id=pet_id, user_id=current_user.id)
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The case index is unavailable: {exc}",
        ) from exc
    return SymptomOptionsResponse(**options)


@router.post(
    "/{pet_id}/predict-conditions",
    response_model=PredictConditionsResponse,
    summary="Rank candidate conditions from similar recorded cases",
)
def post_predict_conditions(
    pet_id: PetPath,
    payload: PredictConditionsRequest,
    db: DbSession,
    current_user: CurrentUser,
    top_k: Annotated[int, Query(ge=1, le=10)] = 5,
) -> PredictConditionsResponse:
    """Rank candidate conditions using similar recorded cases as evidence.

    This is **not** a trained classifier and **not** a probability. Each
    candidate is ordered by how many retrieved cases carried that recorded
    diagnosis and how closely they resembled the pet. The response states this.
    """
    try:
        result = predict_conditions_for_pet(
            db,
            pet_id=pet_id,
            user_id=current_user.id,
            symptoms=payload.symptoms,
            species=payload.species,
            top_k=top_k,
        )
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The case index is unavailable: {exc}",
        ) from exc

    return PredictConditionsResponse(
        pet_id=result.pet_id,
        pet_name=result.pet_name,
        species=result.species,
        used_symptoms=result.used_symptoms,
        symptoms_overridden=result.symptoms_overridden,
        candidates=[CandidateRead(**c.__dict__) for c in result.candidates],
        corpus_size=result.corpus_size,
        disclaimer=result.disclaimer,
    )
