"""Answer a clinical question using retrieved passages and the LLM.

The prompt is built so the model can only answer from the supplied passages: it
is told to say it does not know when they do not cover the question, and must
cite the passage numbers it used. The resulting :class:`AnswerResult` carries the
sources separately, so the caller can display exactly which documents supported
the answer regardless of what the model wrote.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.rag.store import RetrievedChunk, search


SYSTEM_PROMPT = (
    "You are a veterinary literature assistant. Answer ONLY from the numbered "
    "passages provided. If they do not contain the answer, say clearly that the "
    "indexed documents do not cover it. Do not invent drug doses, diagnoses, or "
    "facts that are not in the passages. Cite the passages you used as [1], [2], "
    "and so on. Keep the answer concise and factual."
)


class LlmUnavailableError(RuntimeError):
    """Raised when no LLM is configured or the call fails."""


@dataclass(frozen=True)
class SourcePassage:
    """A passage that was retrieved and offered to the model."""

    index: int
    source: str
    page: int
    score: float
    excerpt: str


@dataclass(frozen=True)
class AnswerResult:
    """An answer plus the passages it was allowed to use."""

    answer: str
    sources: list[SourcePassage] = field(default_factory=list)
    grounded: bool = True
    model: str | None = None


def _format_passages(passages: list[RetrievedChunk]) -> str:
    blocks = []
    for i, passage in enumerate(passages, start=1):
        blocks.append(
            f"[{i}] (source: {passage.source}, page {passage.page})\n{passage.text}"
        )
    return "\n\n".join(blocks)


def _to_sources(passages: list[RetrievedChunk]) -> list[SourcePassage]:
    return [
        SourcePassage(
            index=i,
            source=p.source,
            page=p.page,
            score=round(p.score, 4),
            excerpt=p.text[:280],
        )
        for i, p in enumerate(passages, start=1)
    ]


def _generate(prompt: str) -> str:
    """Call the configured LLM. Raises :class:`LlmUnavailableError` on failure."""
    if not settings.groq_api_key:
        raise LlmUnavailableError(
            "No GROQ_API_KEY is configured, so the model cannot be called."
        )
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key, timeout=60.0)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=700,
        )
        return (completion.choices[0].message.content or "").strip()
    except LlmUnavailableError:
        raise
    except Exception as exc:
        raise LlmUnavailableError(
            f"LLM call failed: {type(exc).__name__}: {exc}"
        ) from exc


def answer_question(
    question: str, *, top_k: int = 4, min_score: float = 0.25
) -> AnswerResult:
    """Retrieve passages for ``question`` and answer from them.

    When retrieval finds nothing above ``min_score`` the model is never called:
    an answer with no sources would be exactly the unsupported claim this design
    is meant to prevent.
    """
    passages = search(question, top_k=top_k, min_score=min_score)
    sources = _to_sources(passages)

    if not passages:
        return AnswerResult(
            answer=(
                "The indexed documents do not appear to cover that question. "
                "Try rephrasing, or consult a veterinarian directly."
            ),
            sources=[],
            grounded=False,
            model=None,
        )

    prompt = (
        f"Question: {question}\n\n"
        f"Passages:\n{_format_passages(passages)}\n\n"
        "Answer using only the passages above, with citations."
    )
    return AnswerResult(
        answer=_generate(prompt),
        sources=sources,
        grounded=True,
        model=settings.groq_model,
    )
