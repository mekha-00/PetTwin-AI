"""On-disk cache for embedding indexes.

Both the RAG corpus (840 chunks) and the external case table (431 cases) are
embedded with a small ONNX model. Doing that inline on the first request takes
minutes and spikes memory, which does not fit a 512 MB free instance. Because
both inputs are static, the vectors are precomputed once at image build time and
baked into the image; at runtime they are loaded from disk in milliseconds.

Each cache entry is two files under ``INDEX_CACHE_DIR``:

* ``<name>.npy``       — the float32 embedding matrix, one row per item.
* ``<name>.json``      — a small envelope holding the item payload plus the
  metadata needed to trust the matrix: model name, item count, and a fingerprint
  of the source files.

The fingerprint is derived from each source file's name and size. It is cheap to
compute (no parsing) and changes whenever a PDF or the CSV is replaced, so a
stale matrix is never paired with new content. If anything does not match, the
loader returns ``None`` and the caller falls back to embedding from scratch,
which keeps local development working with no cache present.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np

#: Version tag stored in every envelope. Bump when the payload shape changes so
#: old caches are ignored rather than misread.
CACHE_VERSION = 1


def cache_dir() -> Path:
    """Directory holding the prebuilt indexes.

    Defaults to ``backend/index_cache`` — the indexes are committed to the repo
    and copied into the image by ``COPY backend/``. Building them inside the
    Docker build was abandoned: embedding 840 chunks there needs several minutes
    and spikes memory, which failed the free-tier build and left the old image
    serving. Shipping the files keeps the build cheap and deterministic.
    """
    override = os.environ.get("INDEX_CACHE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "index_cache"


def file_fingerprint(paths: Iterable[Path]) -> str:
    """Stable fingerprint of the source files, from their names and sizes.

    Contents are not hashed: the inputs are immutable project assets, and a
    name+size change is a reliable enough signal while staying cheap at startup.
    """
    digest = hashlib.sha256()
    for path in sorted(Path(p) for p in paths):
        digest.update(f"{path.name}:{path.stat().st_size}\n".encode("utf-8"))
    return digest.hexdigest()


def save(
    name: str,
    matrix: np.ndarray,
    payload: list[dict[str, Any]],
    *,
    model: str,
    fingerprint: str,
) -> Path:
    """Write ``matrix`` and ``payload`` for ``name`` and return the directory."""
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / f"{name}.npy", np.asarray(matrix, dtype=np.float32))
    envelope = {
        "version": CACHE_VERSION,
        "model": model,
        "count": len(payload),
        "fingerprint": fingerprint,
        "items": payload,
    }
    (directory / f"{name}.json").write_text(
        json.dumps(envelope, ensure_ascii=False), encoding="utf-8"
    )
    return directory


def diagnostics(name: str, *, model: str, fingerprint: str) -> dict[str, Any]:
    """Describe a cache entry without loading its matrix into memory.

    Used by ``GET /api/rag/status`` to explain why a deployed instance may be
    falling back to embedding from scratch (which OOMs a 512 MB instance).
    """
    directory = cache_dir()
    matrix_path = directory / f"{name}.npy"
    meta_path = directory / f"{name}.json"
    info: dict[str, Any] = {
        "dir": str(directory),
        "npy_present": matrix_path.is_file(),
        "npy_bytes": matrix_path.stat().st_size if matrix_path.is_file() else None,
        "json_present": meta_path.is_file(),
        "expected_fingerprint": fingerprint,
        "stored_fingerprint": None,
        "stored_version": None,
        "stored_model": None,
        "stored_count": None,
        "items_len": None,
        "shape": None,
    }
    try:
        envelope = json.loads(meta_path.read_text(encoding="utf-8"))
        info["stored_fingerprint"] = envelope.get("fingerprint")
        info["stored_version"] = envelope.get("version")
        info["stored_model"] = envelope.get("model")
        info["stored_count"] = envelope.get("count")
        items = envelope.get("items")
        info["items_len"] = len(items) if isinstance(items, list) else None
    except Exception as exc:  # pragma: no cover - environment dependent
        info["json_error"] = str(exc)

    try:
        if matrix_path.is_file():
            matrix = np.load(matrix_path, allow_pickle=False, mmap_mode="r")
            info["shape"] = list(matrix.shape)
    except Exception as exc:  # pragma: no cover - environment dependent
        info["npy_error"] = str(exc)

    info["matches"] = (
        info["stored_fingerprint"] == fingerprint
        and info["stored_model"] == model
        and info["stored_version"] == CACHE_VERSION
        and info["shape"] is not None
        and info["stored_count"] is not None
        and info["shape"][0] == info["stored_count"]
    )
    return info


def load(
    name: str,
    *,
    model: str,
    fingerprint: str,
) -> tuple[np.ndarray, list[dict[str, Any]]] | None:
    """Return ``(matrix, items)`` for a trusted cache entry, else ``None``."""
    directory = cache_dir()
    matrix_path = directory / f"{name}.npy"
    meta_path = directory / f"{name}.json"
    if not matrix_path.is_file() or not meta_path.is_file():
        return None

    try:
        envelope = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if envelope.get("version") != CACHE_VERSION:
        return None
    if envelope.get("model") != model:
        return None
    if envelope.get("fingerprint") != fingerprint:
        return None

    items = envelope.get("items")
    if not isinstance(items, list) or envelope.get("count") != len(items):
        return None

    try:
        matrix = np.load(matrix_path, allow_pickle=False)
    except (OSError, ValueError):
        return None

    if matrix.ndim != 2 or matrix.shape[0] != len(items):
        return None
    return matrix, items
