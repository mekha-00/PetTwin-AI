"""Extract and chunk the veterinary PDF corpus.

Text is pulled with PyMuPDF and split into overlapping windows on paragraph
boundaries. Chunking is intentionally simple (fixed size, fixed overlap) rather
than semantic: the goal is to keep each passage small enough to embed usefully
while guaranteeing that a sentence split across a boundary still appears whole
in one of the neighbouring chunks.

Every chunk keeps its source filename and 1-based page number, so an answer can
cite exactly where a passage came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

#: Project root (…/PetTwin-AI), four levels up from this file.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS_DIR = PROJECT_ROOT / "rag" / "documents"

#: Characters per chunk and the overlap between adjacent chunks.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage of text and where it came from."""

    text: str
    source: str
    page: int
    index: int


def _paragraph_windows(text: str, size: int, overlap: int) -> list[str]:
    """Split ``text`` into ~``size``-character windows on paragraph boundaries.

    A paragraph longer than ``size`` is hard-split so no window can grow without
    bound. Windows overlap by ``overlap`` characters so a sentence spanning a
    boundary is still fully contained in at least one window.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    windows: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            windows.append(buffer.strip())
        buffer = ""

    for para in paragraphs:
        if len(para) > size:
            flush()
            start = 0
            while start < len(para):
                windows.append(para[start : start + size].strip())
                start += size - overlap
            continue
        if len(buffer) + len(para) + 1 <= size:
            buffer = f"{buffer}\n{para}" if buffer else para
        else:
            flush()
            buffer = para
    flush()

    if overlap and len(windows) > 1:
        merged: list[str] = []
        for i, window in enumerate(windows):
            if i == 0:
                merged.append(window)
                continue
            tail = windows[i - 1][-overlap:]
            merged.append(f"{tail} {window}".strip())
        return merged
    return windows


def load_chunks(documents_dir: Path | None = None) -> list[Chunk]:
    """Read every PDF under ``documents_dir`` and return its chunks in order."""
    directory = documents_dir or DOCUMENTS_DIR
    if not directory.exists():
        return []

    chunks: list[Chunk] = []
    for pdf_path in sorted(directory.glob("*.pdf")):
        try:
            document = pymupdf.open(pdf_path)
        except Exception:
            # A corrupt or unreadable PDF must not take the whole index down.
            continue
        try:
            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text()
                for window in _paragraph_windows(page_text, CHUNK_SIZE, CHUNK_OVERLAP):
                    chunks.append(
                        Chunk(
                            text=window,
                            source=pdf_path.name,
                            page=page_number,
                            index=len(chunks),
                        )
                    )
        finally:
            document.close()
    return chunks
