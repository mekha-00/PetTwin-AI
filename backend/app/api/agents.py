"""Agent API — ask a question about one pet.

``POST /pets/{pet_id}/ask`` runs the Phase 6 agent over that pet's verified
Digital Twin and the indexed veterinary corpus, then returns the answer, the
literature sources it used, and which tools the agent chose.

Access is enforced inside the service before the twin is assembled, so an
inaccessible pet returns 404 exactly as elsewhere in the API. The agent is
read-only: there is no endpoint it can reach that the caller could not.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field

from app.agents.service import AgentUnavailableError, answer_pet_question
from app.api.deps import CurrentUser, DbSession
from app.rag.embeddings import EmbeddingUnavailableError

router = APIRouter(prefix="/pets", tags=["agent"])

PetPath = Annotated[uuid.UUID, Path(description="Target pet id")]


class AgentAsk(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AgentAnswer(BaseModel):
    pet_id: str
    question: str
    answer: str
    tools_used: list[str] = []
    model: str | None = None
    disclaimer: str
    read_only: bool = True


@router.post(
    "/{pet_id}/ask",
    response_model=AgentAnswer,
    summary="Ask the assistant about this pet",
)
def ask_about_pet(
    pet_id: PetPath,
    payload: AgentAsk,
    db: DbSession,
    current_user: CurrentUser,
) -> AgentAnswer:
    """Answer a question using this pet's verified records and the literature.

    The assistant cannot diagnose, prescribe, or write. It summarizes what the
    records and the indexed documents show and cites its sources.
    """
    try:
        run = answer_pet_question(
            db,
            pet_id=pet_id,
            user_id=current_user.id,
            question=payload.question,
        )
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The document index is unavailable: {exc}",
        ) from exc
    except AgentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AgentAnswer(
        pet_id=str(pet_id),
        question=payload.question,
        answer=run.answer,
        tools_used=run.tools_used,
        model=run.model,
        disclaimer=run.disclaimer,
    )
