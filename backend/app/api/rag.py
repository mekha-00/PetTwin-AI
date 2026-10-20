"""RAG API — ask a question against the indexed veterinary documents.

The endpoint is available to any signed-in user rather than being gated to pet
access: it answers from public literature and never touches a pet's records, so
there is nothing per-pet to authorize.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.rag.answer import LlmUnavailableError, answer_question
from app.rag.embeddings import EmbeddingUnavailableError
from app.rag.store import index_size

router = APIRouter(prefix="/rag", tags=["rag"])


class RagQuery(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=4, ge=1, le=8)


class RagSource(BaseModel):
    index: int
    source: str
    page: int
    score: float
    excerpt: str


class RagAnswer(BaseModel):
    question: str
    answer: str
    sources: list[RagSource] = []
    grounded: bool
    model: str | None = None
    disclaimer: str


class RagStatus(BaseModel):
    documents_indexed: int
    ready: bool


@router.get("/status", response_model=RagStatus, summary="RAG index status")
def rag_status(current_user: CurrentUser) -> RagStatus:
    """Report how many passages are indexed, or 0 if the corpus is missing."""
    try:
        count = index_size()
    except EmbeddingUnavailableError:
        count = 0
    return RagStatus(documents_indexed=count, ready=count > 0)


@router.post("/query", response_model=RagAnswer, summary="Ask the veterinary corpus")
def rag_query(payload: RagQuery, current_user: CurrentUser) -> RagAnswer:
    """Retrieve passages for a question and answer strictly from them."""
    try:
        result = answer_question(payload.question, top_k=payload.top_k)
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The document index is unavailable: {exc}",
        ) from exc
    except LlmUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return RagAnswer(
        question=payload.question,
        answer=result.answer,
        sources=[RagSource(**s.__dict__) for s in result.sources],
        grounded=result.grounded,
        model=result.model,
        disclaimer=result.disclaimer,
    )
