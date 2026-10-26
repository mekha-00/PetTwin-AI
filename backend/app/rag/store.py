"""In-memory vector index over the PDF corpus.

There is no vector database. The corpus is small (a few thousand chunks), so a
single numpy matrix plus a cosine dot product is both simpler and fast enough.
The index is built once per process and cached behind a lock; a second request
reuses the same matrix.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from app.core.index_cache import (
    diagnostics as diagnostics_for,
    file_fingerprint,
    load as load_cached,
    load_unverified,
)
from app.rag.corpus import DOCUMENTS_DIR, Chunk, load_chunks
from app.rag.embeddings import MODEL_NAME, cosine_similarity, embed_query, embed_texts

#: Name of this index inside the shared on-disk cache.
CACHE_NAME = "rag"

logger = logging.getLogger(__name__)


def _corpus_fingerprint() -> str:
    return file_fingerprint(Path(p) for p in DOCUMENTS_DIR.glob("*.pdf"))


def _chunks_to_payload(chunks: list[Chunk]) -> list[dict]:
    return [asdict(chunk) for chunk in chunks]


def _chunks_from_payload(items: list[dict]) -> list[Chunk]:
    return [Chunk(**item) for item in items]


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk together with its similarity score for a query."""

    text: str
    source: str
    page: int
    score: float


class _Index:
    def __init__(self, chunks: list[Chunk], matrix: np.ndarray) -> None:
        self.chunks = chunks
        self.matrix = matrix


_index: _Index | None = None
_index_lock = threading.Lock()


def build_index() -> _Index:
    """Build the index from the PDFs, or return the cached one.

    A matrix precomputed at image build time is loaded from disk first, which is
    instant and avoids embedding 840 chunks on the first request. If no trusted
    cache exists (local development), the chunks are embedded here as before.
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
                    _index = _Index(_chunks_from_payload(items), matrix)
                else:
                    stale = load_unverified(CACHE_NAME, model=MODEL_NAME)
                    if stale is not None:
                        logger.warning(
                            "RAG index cache fingerprint drifted; using the "
                            "committed matrix instead of re-embedding %d chunks",
                            len(stale[1]),
                        )
                        matrix, items = stale
                        _index = _Index(_chunks_from_payload(items), matrix)
                    else:
                        chunks = load_chunks()
                        matrix = embed_texts([c.text for c in chunks])
                        _index = _Index(chunks, matrix)
    return _index


def reset_index() -> None:
    """Drop the cached index. Used by tests and to force a rebuild."""
    global _index
    with _index_lock:
        _index = None


def index_size() -> int:
    """Passage count without triggering an embedding run.

    Status checks call this, so it must stay cheap even if the process has not
    built the index yet. A baked cache gives the count directly; otherwise the
    PDFs are only parsed (never embedded).
    """
    index = _index
    if index is not None:
        return len(index.chunks)
    cached = load_cached(
        CACHE_NAME, model=MODEL_NAME, fingerprint=_corpus_fingerprint()
    )
    if cached is not None:
        return len(cached[1])
    return len(load_chunks())


def is_loaded() -> bool:
    """Whether the matrix is already in memory (cheap status probe)."""
    return _index is not None


def diagnostics() -> dict:
    """Explain cache state for the deployed instance (see ``index_cache``)."""
    import hashlib
    import json

    from app.core.index_cache import cache_dir

    paths = sorted(Path(p) for p in DOCUMENTS_DIR.glob("*.pdf"))
    data = diagnostics_for(
        CACHE_NAME, model=MODEL_NAME, fingerprint=file_fingerprint(paths)
    )
    data["sources"] = [{"name": p.name, "size": p.stat().st_size} for p in paths]

    try:
        chunks = load_chunks()
        data["parsed_chunks"] = len(chunks)
        data["parsed_hash"] = hashlib.sha256(
            "".join(c.text for c in chunks).encode("utf-8")
        ).hexdigest()[:16]
    except Exception as exc:  # pragma: no cover - environment dependent
        data["parse_error"] = str(exc)

    try:
        envelope = json.loads((cache_dir() / f"{CACHE_NAME}.json").read_text("utf-8"))
        items = envelope.get("items") or []
        data["cache_hash"] = hashlib.sha256(
            "".join(str(item.get("text", "")) for item in items).encode("utf-8")
        ).hexdigest()[:16]
    except Exception as exc:  # pragma: no cover - environment dependent
        data["cache_read_error"] = str(exc)

    return data


def search(query: str, *, top_k: int = 4, min_score: float = 0.0) -> list[RetrievedChunk]:
    """Return the ``top_k`` most similar passages to ``query``.

    ``min_score`` filters out weak matches so an unrelated question returns an
    empty list rather than four irrelevant passages the LLM might still use.
    """
    index = build_index()
    if not index.chunks:
        return []
    query_vector = embed_query(query)
    scores = cosine_similarity(query_vector, index.matrix)
    if scores.size == 0:
        return []

    order = np.argsort(scores)[::-1][:top_k]
    results: list[RetrievedChunk] = []
    for i in order:
        score = float(scores[i])
        if score < min_score:
            continue
        chunk = index.chunks[int(i)]
        results.append(
            RetrievedChunk(
                text=chunk.text,
                source=chunk.source,
                page=chunk.page,
                score=score,
            )
        )
    return results
