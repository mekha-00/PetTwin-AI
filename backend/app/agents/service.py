"""High-level entry point for the Phase 6 agent.

Keeps the FastAPI layer thin: the router hands over a pet id, a question and the
already-authenticated user; this module assembles the twin, builds the model from
settings, and runs the graph. Splitting it out means the API file has no LangGraph
or Groq imports, and this module can be exercised without HTTP.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.graph import AgentRun, AgentUnavailableError, run_agent
from app.agents.tools import AgentContext
from app.core.config import settings
from app.ml.service import predict_conditions_for_pet
from app.services.authorization import load_accessible_pet
from app.services.digital_twin_service import build_digital_twin

__all__ = ["AgentUnavailableError", "AgentRun", "answer_pet_question"]


def _build_model() -> Any:
    """Create the chat model. Raises if no key is configured."""
    if not settings.groq_api_key:
        raise AgentUnavailableError(
            "No GROQ_API_KEY is configured, so the assistant cannot run."
        )
    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.1,
        max_tokens=800,
    )


def answer_pet_question(
    db: Session,
    *,
    pet_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    model: Any = None,
    retrieve: Any = None,
) -> AgentRun:
    """Answer ``question`` about a pet the user is allowed to access.

    Access is enforced here, before the twin is assembled, by
    :func:`load_accessible_pet`. A pet the user cannot see raises the same 404
    the rest of the API raises and never reaches the model.

    ``model`` and ``retrieve`` are injectable so tests can run the full path with
    a fake LLM and no network.
    """
    load_accessible_pet(db, pet_id=pet_id, user_id=user_id)
    twin_snapshot = build_digital_twin(db, pet_id=pet_id, user_id=user_id)

    context_kwargs: dict[str, Any] = {"twin_snapshot": twin_snapshot}
    if retrieve is not None:
        context_kwargs["retrieve"] = retrieve

    def _predict() -> list[dict[str, Any]]:
        result = predict_conditions_for_pet(db, pet_id=pet_id, user_id=user_id)
        return [
            {
                "disease": c.disease,
                "case_count": c.case_count,
                "avg_similarity": c.avg_similarity,
                "shared_symptoms": c.shared_symptoms,
            }
            for c in result.candidates
        ]

    context_kwargs["predict"] = _predict
    context = AgentContext(**context_kwargs)

    chat_model = model if model is not None else _build_model()
    return run_agent(
        chat_model,
        context,
        question,
        model_name=settings.groq_model,
    )
