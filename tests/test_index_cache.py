"""The indexes shipped in ``backend/index_cache`` must match the current corpus.

They are committed so the Docker build never has to embed anything. If a PDF or
the case CSV changes and the indexes are not regenerated, the loader will reject
the stale files and fall back to embedding on first request — exactly the slow
path this cache exists to avoid. This test fails loudly instead.

Regenerate with::

    cd backend && python -m app.scripts.build_indexes
"""

from __future__ import annotations

import numpy as np

from app.core import index_cache
from app.ml import similar
from app.rag import store
from app.rag.embeddings import MODEL_NAME


def test_committed_indexes_exist_and_match_sources(monkeypatch) -> None:
    # conftest points INDEX_CACHE_DIR at an empty temp dir; this test is about
    # the committed files, so read the default location.
    monkeypatch.delenv("INDEX_CACHE_DIR", raising=False)

    rag = index_cache.load(
        "rag", model=MODEL_NAME, fingerprint=store._corpus_fingerprint()
    )
    ml = index_cache.load(
        "ml", model=MODEL_NAME, fingerprint=similar._corpus_fingerprint()
    )

    assert rag is not None, (
        "backend/index_cache/rag.* is missing or stale; "
        "run `python -m app.scripts.build_indexes` in backend/"
    )
    assert ml is not None, (
        "backend/index_cache/ml.* is missing or stale; "
        "run `python -m app.scripts.build_indexes` in backend/"
    )

    rag_matrix, rag_items = rag
    ml_matrix, ml_items = ml

    assert rag_matrix.shape == (len(rag_items), 384)
    assert ml_matrix.shape == (len(ml_items), 384)
    assert len(rag_items) > 0
    assert len(ml_items) > 0
    assert np.isfinite(rag_matrix).all()
    assert np.isfinite(ml_matrix).all()
