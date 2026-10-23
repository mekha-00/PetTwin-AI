"""Nearest-case search over the external case table.

The cases are embedded once per process with the same local ONNX model the RAG
pipeline uses, and queried by cosine similarity. There is no trained classifier:
the label on a returned case is the diagnosis that was recorded for *that case*,
shown next to the resemblance score, so it reads as "a similar case had this"
rather than "your pet has this".

The index is built lazily behind a lock and cached, exactly like
``app.rag.store``. Building it costs one batch embed of 431 short strings, which
is a second or two after the model is loaded.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from app.core.index_cache import file_fingerprint, load as load_cached
from app.ml.dataset import DEFAULT_CSV, CaseRecord, load_cases
from app.ml.features import features_for_case
from app.rag.embeddings import MODEL_NAME, cosine_similarity, embed_query, embed_texts

#: Name of this index inside the shared on-disk cache.
CACHE_NAME = "ml"


def _corpus_fingerprint() -> str:
    return file_fingerprint([Path(DEFAULT_CSV)])


def _cases_to_payload(cases: list[CaseRecord]) -> list[dict]:
    return [asdict(case) for case in cases]


def _cases_from_payload(items: list[dict]) -> list[CaseRecord]:
    return [CaseRecord(**item) for item in items]


@dataclass(frozen=True)
class SimilarCase:
    """A retrieved case and how closely it resembles the query."""

    disease: str
    animal_type: str
    breed: str | None
    age_years: float | None
    gender: str | None
    weight_kg: float | None
    symptoms: list[str]
    duration: str | None
    body_temperature_c: float | None
    heart_rate_bpm: float | None
    similarity: float


class _CaseIndex:
    def __init__(self, cases: list[CaseRecord], matrix: np.ndarray) -> None:
        self.cases = cases
        self.matrix = matrix


_index: _CaseIndex | None = None
_index_lock = threading.Lock()


def build_index() -> _CaseIndex:
    """Build the case index, or return the cached one.

    A matrix precomputed at image build time is loaded from disk first, which is
    instant. If no trusted cache exists (local development), the cases are
    embedded here as before.
    """
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
                cached = load_cached(
                    CACHE_NAME,
                    model=MODEL_NAME,
                    fingerprint=_corpus_fingerprint(),
                )
                if cached is not None:
                    matrix, items = cached
                    _index = _CaseIndex(_cases_from_payload(items), matrix)
                else:
                    cases = load_cases()
                    if cases:
                        matrix = embed_texts([features_for_case(c) for c in cases])
                    else:
                        matrix = np.zeros((0, 384), dtype=np.float32)
                    _index = _CaseIndex(cases, matrix)
    return _index


def reset_index() -> None:
    """Drop the cached index. Used by tests and to force a rebuild."""
    global _index
    with _index_lock:
        _index = None


def index_size() -> int:
    """Case count without triggering an embedding run."""
    index = _index
    if index is not None:
        return len(index.cases)
    cached = load_cached(
        CACHE_NAME, model=MODEL_NAME, fingerprint=_corpus_fingerprint()
    )
    if cached is not None:
        return len(cached[1])
    return len(load_cases())


def find_similar(
    query_features: str, *, top_k: int = 5, min_score: float = 0.0
) -> list[SimilarCase]:
    """Return the ``top_k`` cases whose features most resemble ``query_features``."""
    index = build_index()
    if not index.cases or not query_features.strip():
        return []
    query_vector = embed_query(query_features)
    scores = cosine_similarity(query_vector, index.matrix)
    if scores.size == 0:
        return []

    order = np.argsort(scores)[::-1]
    results: list[SimilarCase] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for i in order:
        if len(results) >= top_k:
            break
        score = float(scores[i])
        if score < min_score:
            continue
        case = index.cases[int(i)]
        symptoms = list(case.symptoms) + list(case.flags)
        # The external file contains duplicate rows. Repeating an identical case
        # would fill the list with copies, so collapse exact repeats, keeping the
        # first (highest-scoring) occurrence.
        fingerprint = (
            case.disease.lower(),
            case.animal_type.lower(),
            tuple(sorted(s.lower() for s in symptoms)),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        results.append(
            SimilarCase(
                disease=case.disease,
                animal_type=case.animal_type,
                breed=case.breed,
                age_years=case.age_years,
                gender=case.gender,
                weight_kg=case.weight_kg,
                symptoms=symptoms,
                duration=case.duration,
                body_temperature_c=case.body_temperature_c,
                heart_rate_bpm=case.heart_rate_bpm,
                similarity=round(score, 4),
            )
        )
    return results
