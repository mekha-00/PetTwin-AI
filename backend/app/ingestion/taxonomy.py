"""Breed and species canonicalisation, derived from the observed values.

Every entry records how many rows it accounts for, so the mapping can be
checked against the data rather than trusted. Values are collapsed only where
the source itself shows they are the same thing recorded twice.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

#: Breeds the source records under two names. ``DATASET_ANALYSIS.md`` 5.2
#: flagged the split; both spellings are counts in the Phase 1 profile, so the
#: merge is derived from the data rather than assumed.
BREED_ALIASES: dict[str, str] = {
    "labrador": "Labrador Retriever",
    "labrador retriever": "Labrador Retriever",
}

#: Case/whitespace variants seen in ``Breed`` are folded before the alias
#: table is consulted.
_TRAILING_COMMA = ","


@dataclass(frozen=True)
class BreedStats:
    canonical: str
    rows: int
    raw_values: dict[str, int]


def canonical_breed(raw: str) -> str:
    """Return the canonical spelling of a breed value."""
    from app.ingestion.normalise import fold

    cleaned = raw.strip().rstrip(_TRAILING_COMMA).strip()
    if not cleaned:
        return ""
    return BREED_ALIASES.get(fold(cleaned), cleaned)


def breed_report(records: list[dict[str, str]], field: str = "breed") -> list[BreedStats]:
    """Group records by canonical breed, listing the raw spellings merged."""
    per_canonical: dict[str, Counter] = {}
    for record in records:
        canonical = canonical_breed(record.get(field, ""))
        if not canonical:
            continue
        per_canonical.setdefault(canonical, Counter())[
            record.get(field, "").strip().rstrip(_TRAILING_COMMA).strip()
        ] += 1
    return sorted(
        (
            BreedStats(
                canonical=canonical,
                rows=sum(counter.values()),
                raw_values=dict(counter),
            )
            for canonical, counter in per_canonical.items()
        ),
        key=lambda stat: (-stat.rows, stat.canonical),
    )
