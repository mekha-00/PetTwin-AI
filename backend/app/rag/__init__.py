"""Retrieval-augmented generation over the veterinary PDFs in ``rag/documents/``.

The pipeline is deliberately simple and fully in-memory:

1. :mod:`app.rag.corpus` extracts and chunks the PDFs.
2. :mod:`app.rag.embeddings` embeds chunks with a local ONNX model (fastembed).
3. :mod:`app.rag.store` keeps the vectors in a numpy array and answers cosine
   similarity queries.
4. :mod:`app.rag.answer` sends the retrieved passages plus a question to the LLM
   and returns an answer with the sources it used.

The index is rebuilt once per process from the PDFs and cached, so there is no
vector database to install or persist.
"""

from app.rag.answer import AnswerResult, SourcePassage, answer_question

__all__ = ["AnswerResult", "SourcePassage", "answer_question"]
