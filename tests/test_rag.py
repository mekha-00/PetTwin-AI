"""Phase 5 tests — retrieval, answer grounding, and the RAG API.

These tests never touch the network and never load the real embedding model.
The ONNX session is slow to load and the corpus takes minutes to embed, so both
the embedder and the LLM are replaced with deterministic fakes. What is under
test is the logic around them: chunking, cosine scoring, ranking, the
``min_score`` filter, and the rule that the model is not called when retrieval
finds nothing.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.rag import answer as answer_module
from app.rag import store
from app.rag.answer import AnswerResult, answer_question
from app.rag.corpus import CHUNK_SIZE, Chunk, _paragraph_windows
from app.rag.embeddings import cosine_similarity
from app.rag.store import RetrievedChunk


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def test_chunk_size_and_pagination() -> None:
    """A caller-supplied PDF directory is read in order, with 1-based pages."""
    import pymupdf

    from app.rag.corpus import load_chunks

    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), "Vaccination schedule for puppies.")

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.pdf"
        doc.save(path)
        doc.close()

        chunks = load_chunks(Path(tmp))

    assert chunks, "expected at least one chunk from the sample PDF"
    assert all(isinstance(c, Chunk) for c in chunks)
    assert chunks[0].source == "sample.pdf"
    assert chunks[0].page == 1
    assert chunks[-1].page == 2
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_long_paragraph_is_hard_split() -> None:
    """A paragraph larger than the window is split, not left unbounded."""
    paragraph = "word " * 400
    windows = _paragraph_windows(paragraph, CHUNK_SIZE, overlap=0)
    assert len(windows) > 1
    assert all(len(w) <= CHUNK_SIZE for w in windows)


def test_missing_directory_yields_no_chunks(tmp_path) -> None:
    from app.rag.corpus import load_chunks

    assert load_chunks(tmp_path / "does-not-exist") == []


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------
def test_cosine_identical_vector_is_one() -> None:
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    matrix = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    assert cosine_similarity(v, matrix)[0] == pytest.approx(1.0, abs=1e-6)


def test_cosine_zero_vector_is_zero_not_nan() -> None:
    """An empty query must not divide by zero."""
    zero = np.zeros(3, dtype=np.float32)
    matrix = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    scores = cosine_similarity(zero, matrix)
    assert scores.shape == (1,)
    assert np.isfinite(scores).all()
    assert scores[0] == 0.0


def test_cosine_empty_matrix_is_empty() -> None:
    scores = cosine_similarity(np.ones(3, dtype=np.float32), np.zeros((0, 3), dtype=np.float32))
    assert scores.size == 0


# ---------------------------------------------------------------------------
# Search ranking and filtering (embedder stubbed, no model load)
# ---------------------------------------------------------------------------
@pytest.fixture()
def fake_index(monkeypatch):
    """Install a tiny index whose scores are controlled by the query text."""
    chunks = [
        Chunk(text="alpha passage", source="a.pdf", page=1, index=0),
        Chunk(text="beta passage", source="b.pdf", page=2, index=1),
        Chunk(text="gamma passage", source="c.pdf", page=3, index=2),
    ]
    matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    store.reset_index()
    monkeypatch.setattr(store, "build_index", lambda: store._Index(chunks, matrix))
    monkeypatch.setattr(store, "embed_query", lambda q: np.array(
        {"alpha": [1.0, 0.0, 0.0], "beta": [0.0, 1.0, 0.0]}.get(q, [0.0, 0.0, 1.0]),
        dtype=np.float32,
    ))
    yield
    store.reset_index()


def test_search_returns_best_match_first(fake_index) -> None:
    results = store.search("alpha", top_k=2)
    assert results[0].text == "alpha passage"
    assert results[0].score == pytest.approx(1.0, abs=1e-6)


def test_search_min_score_filters_weak_matches(fake_index) -> None:
    """An orthogonal (score 0) passage is dropped when a threshold is set."""
    results = store.search("alpha", top_k=3, min_score=0.5)
    assert [r.text for r in results] == ["alpha passage"]


def test_search_respects_top_k(fake_index) -> None:
    assert len(store.search("alpha", top_k=1)) == 1


# ---------------------------------------------------------------------------
# Answer grounding
# ---------------------------------------------------------------------------
def test_no_retrieval_never_calls_llm(monkeypatch) -> None:
    """When nothing clears min_score the model must not be invoked."""
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("LLM must not be called without sources")

    monkeypatch.setattr(answer_module, "search", lambda *a, **k: [])
    monkeypatch.setattr(answer_module, "_generate", boom)

    result = answer_question("unrelated question")

    assert called["n"] == 0
    assert result.grounded is False
    assert result.sources == []
    assert result.model is None


def test_grounded_answer_carries_sources(monkeypatch) -> None:
    passage = RetrievedChunk(
        text="Puppies are vaccinated from six weeks.",
        source="wsava.pdf",
        page=11,
        score=0.9,
    )
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: [passage])
    monkeypatch.setattr(answer_module, "_generate", lambda prompt: "From six weeks [1].")

    result = answer_question("when to vaccinate puppies")

    assert result.grounded is True
    assert result.answer == "From six weeks [1]."
    assert len(result.sources) == 1
    assert result.sources[0].source == "wsava.pdf"
    assert result.sources[0].index == 1


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------
def test_query_requires_authentication(client) -> None:
    response = client.post("/api/rag/query", json={"question": "parvovirus"})
    assert response.status_code == 401


def test_status_requires_authentication(client) -> None:
    assert client.get("/api/rag/status").status_code == 401


def test_query_rejects_short_question(client, owner_token) -> None:
    response = client.post(
        "/api/rag/query",
        json={"question": "x"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 422


def test_query_returns_503_when_llm_missing(client, owner_token, monkeypatch) -> None:
    """No GROQ key means a clear 503, not a 500 or a fabricated answer."""
    passage = RetrievedChunk(text="Parvovirus is viral.", source="x.pdf", page=1, score=0.8)
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: [passage])
    monkeypatch.setattr(answer_module.settings, "groq_api_key", "")

    response = client.post(
        "/api/rag/query",
        json={"question": "canine parvovirus"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 503
    assert "GROQ" in response.json()["detail"] or "model" in response.json()["detail"].lower()


def test_query_happy_path(client, owner_token, monkeypatch) -> None:
    passage = RetrievedChunk(
        text="Puppies are vaccinated from six weeks.",
        source="wsava.pdf",
        page=11,
        score=0.9,
    )
    monkeypatch.setattr(answer_module, "search", lambda *a, **k: [passage])
    monkeypatch.setattr(answer_module, "_generate", lambda prompt: "From six weeks [1].")

    response = client.post(
        "/api/rag/query",
        json={"question": "when should puppies be vaccinated", "top_k": 4},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded"] is True
    assert body["sources"][0]["source"] == "wsava.pdf"
    assert body["sources"][0]["page"] == 11
