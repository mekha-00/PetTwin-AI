"""PetTwin AI backend entry point.

Phase 7 scope: pet management, clinical records, the software-based Digital Twin,
veterinarian access sharing, retrieval-augmented generation, a minimal tool-using
agent, and similar-case retrieval over an external case table.

The Digital Twin is a **service**, not a table. It is assembled on demand by
``app.services.digital_twin_service`` from the pet's records and discarded
afterwards, so it cannot drift from the data it describes. It is software-based
and built from recorded veterinary information — it is not sensor-based, not
real-time, and connected to no device.

The ``agents`` package adds one small LangGraph agent that routes between reading
a pet's twin and searching the corpus. The ``ml`` package retrieves recorded cases
that resemble a pet. Neither is a prediction model: the agent cannot diagnose,
prescribe, or write, and the similar-case search shows recorded labels with a
resemblance score rather than a probability.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents, auth, clinical, digital_twin, ml, pets, rag, users
from app.core.config import settings
from app.core.database import create_all

DESCRIPTION = """
Backend API for PetTwin AI, a software-based digital twin for pet healthcare.

**Phase 7 — pet management, clinical records, the Digital Twin, veterinarian
access sharing, document-grounded question answering, a read-only agent, and
similar-case retrieval.**

A **Digital Twin** here means a structured representation of a pet's health
state, assembled on demand from that pet's own records and recomputed every
time it is requested. It is not a database table, not cached, and not
sensor-based: there are no wearables or real-time feeds anywhere in this
system. Adding a verified record is what updates the twin.

The `/api/rag` endpoints answer questions from an indexed corpus of veterinary
documents and cite the passages used. `POST /api/pets/{id}/ask` runs a small
agent that reads that pet's verified twin and searches the same corpus.
`GET /api/pets/{id}/similar-cases` retrieves recorded cases that resemble the
pet. All three are restrained by design: the model may only use the supplied
material, says so when it is not covered, and is never given a tool that
diagnoses or prescribes; the case search shows recorded labels, not predictions.

This API stores and serves pet records. It performs **no** disease prediction and
**no** clinical decision support. The Digital Twin output and every answer are
assistive information, not a diagnosis.

No claim of HIPAA or GDPR compliance is made. The project has not been assessed
against those regulations.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.db_auto_create:
        create_all()
    if settings.rag_warmup_on_startup:
        _warm_rag_index()
    yield


def _warm_rag_index() -> None:
    """Build the RAG index at startup so the first query is not slow.

    A failure here is logged and swallowed: a missing corpus or an unavailable
    embedding model should leave the API up with the rest of the features
    working, and ``GET /api/rag/status`` reports it as not ready. Crashing the
    whole application over an optional feature would be the wrong trade.
    """
    import logging

    logger = logging.getLogger("pettwin.startup")
    try:
        from app.rag.store import build_index, index_size

        build_index()
        logger.info("RAG index ready: %d passages indexed", index_size())
    except Exception as exc:  # pragma: no cover - depends on local corpus/model
        logger.warning("RAG index warm-up skipped: %s", exc)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=DESCRIPTION,
    lifespan=lifespan,
)

# CORS is an explicit allowlist from the environment. A wildcard origin is never
# used, because the API is authenticated with bearer tokens and credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["system"], summary="Liveness and configuration probe")
def health() -> dict:
    return {
        "status": "ok",
        "version": settings.app_version,
        "phase": 7,
        "database_configured": settings.is_database_configured,
        "digital_twin": "service_assembly_not_persisted",
        "ai_features_enabled": bool(settings.groq_api_key),
        "rag_enabled": True,
        "agent_enabled": bool(settings.groq_api_key),
        "similar_cases_enabled": True,
    }


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(pets.router, prefix=settings.api_prefix)
app.include_router(clinical.router, prefix=settings.api_prefix)
app.include_router(digital_twin.router, prefix=settings.api_prefix)
app.include_router(rag.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)
app.include_router(ml.router, prefix=settings.api_prefix)
