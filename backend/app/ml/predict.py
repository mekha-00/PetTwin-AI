"""Turn retrieved similar cases into ranked candidate conditions.

This is **evidence aggregation, not classification**. There is no trained model
and no probability. The module takes the cases returned by
:func:`app.ml.similar.find_similar`, groups them by the diagnosis that was
recorded for each case, and reports how many of the retrieved cases carried that
diagnosis and how closely they resembled the query.

The ``evidence_score`` is a **relative ranking weight**, and it is explicitly
**not a probability** of disease. It is documented as such and surfaced to
callers that way, because presenting a resemblance as a probability would be a
fabricated claim the data cannot support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ml.similar import SimilarCase, find_similar

#: How many neighbouring cases to gather before aggregating. Larger than the
#: returned ``top_k`` so that a disease supported by several neighbouring cases
#: is not missed just because its members sit a little further down the list.
DEFAULT_GATHER = 25


@dataclass(frozen=True)
class Candidate:
    """One disease suggested by the retrieved cases.

    ``case_count`` and the similarities are **observed facts** about the
    retrieved cases. ``evidence_score`` is a relative ordering weight; it is not
    a probability and must never be shown as one.
    """

    disease: str
    case_count: int
    avg_similarity: float
    top_similarity: float
    evidence_score: float
    supporting_symptoms: list[str] = field(default_factory=list)
    example_case_count: int = 0


def _evidence_score(case_count: int, avg_similarity: float) -> float:
    """A relative ranking weight: how many cases support a disease, weighted by
    how closely they resemble the query.

    This is a heuristic ordering value, deliberately not normalised into a
    "confidence" because the underlying data cannot justify one.
    """
    return round(case_count * avg_similarity, 4)


def aggregate_candidates(
    cases: list[SimilarCase], *, top_k: int = 5
) -> list[Candidate]:
    """Group retrieved cases by disease and rank them by observed evidence."""
    grouped: dict[str, list[SimilarCase]] = {}
    for case in cases:
        key = case.disease.strip()
        if not key:
            continue
        grouped.setdefault(key, []).append(case)

    candidates: list[Candidate] = []
    for disease, members in grouped.items():
        similarities = [m.similarity for m in members]
        avg = sum(similarities) / len(similarities)
        top = max(similarities)

        # Symptom labels shared by the query and the cases, in first-seen order.
        supporting: list[str] = []
        seen: set[str] = set()
        for member in members:
            for symptom in member.symptoms:
                cleaned = (symptom or "").strip()
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    supporting.append(cleaned)

        candidates.append(
            Candidate(
                disease=disease,
                case_count=len(members),
                avg_similarity=round(avg, 4),
                top_similarity=round(top, 4),
                evidence_score=_evidence_score(len(members), avg),
                supporting_symptoms=supporting[:8],
                example_case_count=len(members),
            )
        )

    candidates.sort(
        key=lambda c: (c.evidence_score, c.case_count, c.top_similarity),
        reverse=True,
    )
    return candidates[:top_k]


def predict_conditions(
    query_features: str,
    *,
    gather: int = DEFAULT_GATHER,
    top_k: int = 5,
) -> list[Candidate]:
    """Retrieve similar cases for ``query_features`` and rank candidate diseases.

    Returns an empty list for an empty query, so a pet with no symptoms produces
    no suggestion rather than an arbitrary one.
    """
    if not query_features.strip():
        return []
    cases = find_similar(query_features, top_k=gather)
    return aggregate_candidates(cases, top_k=top_k)
