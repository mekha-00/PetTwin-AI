"""Precompute the embedding indexes at image build time.

Both corpora are static: the veterinary PDFs under ``rag/documents`` and the
case table under ``data/external``. Embedding them on the first request takes
minutes and peaks over 512 MB, which is fatal on a free instance. This script
runs once during the Docker build and writes both matrices to
``INDEX_CACHE_DIR``; the app then loads them from disk at startup.

Run with ``python -m app.scripts.build_indexes`` from the ``backend`` directory.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from app.core.index_cache import file_fingerprint, save
from app.ml.dataset import DEFAULT_CSV, load_cases
from app.ml.features import features_for_case
from app.rag.corpus import DOCUMENTS_DIR, load_chunks
from app.rag.embeddings import MODEL_NAME, embed_texts


def build_rag() -> int:
    """Embed the PDF chunks and write the RAG index."""
    start = time.perf_counter()
    chunks = load_chunks()
    if not chunks:
        raise SystemExit("No PDF text found; refusing to write an empty RAG index.")
    matrix = embed_texts([chunk.text for chunk in chunks])
    save(
        "rag",
        matrix,
        [asdict(chunk) for chunk in chunks],
        model=MODEL_NAME,
        fingerprint=file_fingerprint(sorted(DOCUMENTS_DIR.glob("*.pdf"))),
    )
    elapsed = time.perf_counter() - start
    print(f"RAG index: {len(chunks)} chunks embedded in {elapsed:.1f}s")
    return len(chunks)


def build_ml() -> int:
    """Embed the external cases and write the case index."""
    start = time.perf_counter()
    cases = load_cases()
    if not cases:
        raise SystemExit("No cases found; refusing to write an empty case index.")
    matrix = embed_texts([features_for_case(case) for case in cases])
    save(
        "ml",
        matrix,
        [asdict(case) for case in cases],
        model=MODEL_NAME,
        fingerprint=file_fingerprint([Path(DEFAULT_CSV)]),
    )
    elapsed = time.perf_counter() - start
    print(f"Case index: {len(cases)} cases embedded in {elapsed:.1f}s")
    return len(cases)


def main() -> None:
    build_rag()
    build_ml()


if __name__ == "__main__":
    main()
