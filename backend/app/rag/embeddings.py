"""Text embeddings via fastembed (local ONNX, no PyTorch).

The model is small (384 dimensions) and runs on CPU. It is cached on disk under
``backend/.cache/fastembed`` after the first download; later calls load it in
under a second, so the RAG endpoint pays no per-request model cost.

The embedder is created lazily and reused, because loading the ONNX session is
the expensive part and doing it per request would dominate the response time.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Sequence

import numpy as np

#: Small English model: 384-dim, ~67 MB, fast on CPU.
MODEL_NAME = "BAAI/bge-small-en-v1.5"

#: Cache inside the project so a re-clone does not re-download and a fresh
#: Windows temp wipe cannot invalidate it. Overridable with ``FASTEMBED_CACHE_DIR``
#: so the Docker build can pre-download into exactly the directory the runtime
#: reads — otherwise the baked model is silently ignored and re-fetched at boot.
CACHE_DIR = Path(
    os.environ.get(
        "FASTEMBED_CACHE_DIR",
        str(Path(__file__).resolve().parents[2] / ".cache" / "fastembed"),
    )
)

#: Bound ONNX's intra-op threads. On a 512 MB instance the default thread pool
#: reserves a large per-thread arena; one thread keeps startup inside the limit
#: at a negligible latency cost for a 384-dim model on short texts.
_EMBED_THREADS = int(os.environ.get("FASTEMBED_THREADS", "1"))

_model = None
_model_lock = threading.Lock()


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the embedding model cannot be loaded."""


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from fastembed import TextEmbedding

                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    _model = TextEmbedding(
                        MODEL_NAME,
                        cache_dir=str(CACHE_DIR),
                        threads=_EMBED_THREADS,
                    )
                except Exception as exc:  # pragma: no cover - env dependent
                    raise EmbeddingUnavailableError(str(exc)) from exc
    return _model


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Embed a batch of strings into a ``(n, 384)`` float32 array."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _get_model()
    vectors = list(model.embed(list(texts)))
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string into a ``(384,)`` float32 vector."""
    return embed_texts([text])[0]


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one vector against every row of ``matrix``.

    Both sides are L2-normalised first, so the dot product is the cosine. A
    zero-norm vector (empty text) yields all-zero scores rather than a divide by
    zero.
    """
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)
    q = query.astype(np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return np.zeros(matrix.shape[0], dtype=np.float32)
    m = matrix.astype(np.float32)
    m_norms = np.linalg.norm(m, axis=1)
    m_norms[m_norms == 0] = 1.0
    return (m @ q) / (m_norms * q_norm)
