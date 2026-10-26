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


def test_fingerprint_is_independent_of_input_order(tmp_path) -> None:
    """The digest must not depend on how the caller happens to enumerate files.

    ``sorted(Path)`` differs between POSIX and Windows because the Windows
    flavour case-folds, so a Windows-built cache used to look stale in the Linux
    image and triggered a full re-embed (502/OOM on a 512 MB instance).
    """
    for name, size in (("b.pdf", 10), ("A.pdf", 20), ("c.PDF", 30), ("d.pdf", 40)):
        (tmp_path / name).write_bytes(b"x" * size)

    paths = list(tmp_path.glob("*.pdf"))
    forward = index_cache.file_fingerprint(paths)
    backward = index_cache.file_fingerprint(list(reversed(paths)))

    assert forward == backward


def test_chunk_order_follows_file_names() -> None:
    from app.rag.corpus import document_paths

    names = [path.name for path in document_paths()]
    assert names == sorted(names)
