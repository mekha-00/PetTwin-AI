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
from app.rag.store import diagnostics as index_diagnostics
from app.rag.store import index_size, is_loaded

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


class RagStatus(BaseModel):
    documents_indexed: int
    ready: bool
    index_loaded: bool | None = None
    memory_mb: float | None = None
    diagnostics: dict | None = None


def _memory_mb() -> float | None:
    """Resident set size of this process, when the platform exposes it."""
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
        return round(pages * 4096 / (1024 * 1024), 1)
    except Exception:
        return None


@router.get("/status", response_model=RagStatus, summary="RAG index status")
def rag_status(current_user: CurrentUser) -> RagStatus:
    """Report how many passages are indexed, or 0 if the corpus is missing."""
    try:
        count = index_size()
    except EmbeddingUnavailableError:
        count = 0
    try:
        diag = index_diagnostics()
    except Exception as exc:  # pragma: no cover - environment dependent
        diag = {"error": str(exc)}
    return RagStatus(
        documents_indexed=count,
        ready=count > 0,
        index_loaded=is_loaded(),
        memory_mb=_memory_mb(),
        diagnostics=diag,
    )


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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The assistant is temporarily unavailable: {exc}",
        ) from exc

    return RagAnswer(
        question=payload.question,
        answer=result.answer,
        sources=[RagSource(**s.__dict__) for s in result.sources],
        grounded=result.grounded,
        model=result.model,
    )


@router.get("/llm-check", summary="Diagnose outbound LLM connectivity")
def rag_llm_check(current_user: CurrentUser) -> dict:
    """Probe DNS, TLS and the Groq API from inside the running instance.

    Only exercised during deployment troubleshooting; it reports exception
    types and environment proxy settings, never the API key itself.
    """
    import os
    import socket

    from app.core.config import settings

    result: dict = {
        "key_present": bool(settings.groq_api_key),
        "key_length": len(settings.groq_api_key or ""),
        "model": settings.groq_model,
        "proxy_env": {
            name: os.environ.get(name)
            for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
        },
    }

    try:
        infos = socket.getaddrinfo("api.groq.com", 443, proto=socket.IPPROTO_TCP)
        result["dns"] = sorted({info[4][0] for info in infos})
    except Exception as exc:
        result["dns_error"] = f"{type(exc).__name__}: {exc}"

    try:
        import httpx

        with httpx.Client(timeout=20.0) as client:
            response = client.get("https://api.groq.com/openai/v1/models")
        result["models_status"] = response.status_code
    except Exception as exc:
        result["models_error"] = f"{type(exc).__name__}: {exc}"

    if settings.groq_api_key:
        try:
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key, timeout=25.0)
            completion = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_tokens=8,
            )
            result["completion"] = completion.choices[0].message.content
        except Exception as exc:
            result["completion_error"] = f"{type(exc).__name__}: {exc}"

    return result
