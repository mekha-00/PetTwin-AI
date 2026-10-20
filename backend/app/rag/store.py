"""In-memory vector index over the PDF corpus.

There is no vector database. The corpus is small (a few thousand chunks), so a
single numpy matrix plus a cosine dot product is both simpler and fast enough.
The index is built once per process and cached behind a lock; a second request
reuses the same matrix.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from app.rag.corpus import Chunk, load_chunks
from app.rag.embeddings import cosine_similarity, embed_query, embed_texts


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
    """Build the index from the PDFs, or return the cached one."""
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
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
    return len(build_index().chunks)


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
