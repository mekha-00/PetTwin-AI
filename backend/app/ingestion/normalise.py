"""Symptom label normalisation.

Three tiers, described in :mod:`app.ingestion`. This module owns tier 1
(mechanical folding) and tier 3 (candidate detection); tier 2 is a lookup into
a human-reviewed table.

The distinction that matters: folding ``"Bloody Diarrhea"`` onto
``"bloody diarrhea"`` is arithmetic, while folding ``"loss of appetite"`` onto
``"Anorexia"`` is a clinical claim. Only the first is done automatically.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

_WHITESPACE = re.compile(r"\s+")
_TRAILING_PUNCT = re.compile(r"[\s.,;:!]+$")
_REPEATS = re.compile(r"(.)\1{2,}")

#: Terms below this frequency are too rare to justify a merge on their own and
#: are surfaced in the review queue rather than normalised away.
CANDIDATE_MIN_FREQUENCY = 20

#: Above this similarity ratio a pair is proposed for review. Deliberately
#: conservative: a review queue that is too noisy gets ignored, one that is too
#: quiet hides real duplicates.
CANDIDATE_SIMILARITY = 0.82


def fold(label: str) -> str:
    """Mechanically normalise a label. Involves no clinical judgment.

    Applies NFKC, collapses whitespace, folds case, strips trailing
    punctuation and repeated characters.
    """
    text = unicodedata.normalize("NFKC", label)
    text = _WHITESPACE.sub(" ", text).strip()
    text = _TRAILING_PUNCT.sub("", text)
    text = _REPEATS.sub(r"\1", text)
    return text.casefold()


@dataclass(frozen=True)
class Alias:
    """A reviewer-approved merge of one raw label onto a canonical form."""

    raw: str
    canonical: str
    reason: str
    approved_by: str


@dataclass
class Normalisation:
    """Result of normalising one label set."""

    canonical_for_raw: dict[str, str] = field(default_factory=dict)
    groups: dict[str, list[str]] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    raw_counts: Counter = field(default_factory=Counter)
    candidates: list[dict[str, object]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    def canonicalise(self, label: str) -> str:
        raw = label.strip()
        return self.canonical_for_raw.get(raw, raw)


def load_aliases(path: Path) -> dict[str, Alias]:
    """Load the reviewer-approved alias table, keyed by folded raw label.

    A row is ignored unless it names an approver, so an unreviewed draft cannot
    silently change the data.
    """
    aliases: dict[str, Alias] = {}
    if not path.exists():
        return aliases
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("raw") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            approved_by = (row.get("approved_by") or "").strip()
            if not raw or not canonical or not approved_by:
                continue
            aliases[fold(raw)] = Alias(
                raw=raw,
                canonical=canonical,
                reason=(row.get("reason") or "").strip(),
                approved_by=approved_by,
            )
    return aliases


def suggest_candidates(counts: Counter[str]) -> list[dict[str, object]]:
    """Propose near-miss merges for human review. Never applied automatically.

    Compares each rare canonical label against the frequent ones and reports
    pairs above :data:`CANDIDATE_SIMILARITY`, strongest evidence first.
    """
    frequent = sorted(
        (label for label, n in counts.items() if n >= CANDIDATE_MIN_FREQUENCY),
        key=lambda label: -counts[label],
    )
    rare = sorted(
        ((label, n) for label, n in counts.items() if n < CANDIDATE_MIN_FREQUENCY),
        key=lambda pair: -pair[1],
    )

    proposals: list[dict[str, object]] = []
    for label, frequency in rare:
        best_ratio, best_other = 0.0, ""
        for other in frequent:
            ratio = SequenceMatcher(None, label, other).ratio()
            if ratio > best_ratio:
                best_ratio, best_other = ratio, other
        if best_ratio >= CANDIDATE_SIMILARITY:
            proposals.append(
                {
                    "candidate": label,
                    "suggested_canonical": best_other,
                    "similarity": round(best_ratio, 3),
                    "occurrences": frequency,
                    "canonical_occurrences": counts[best_other],
                    "status": "PENDING_REVIEW",
                }
            )
    proposals.sort(key=lambda row: (-float(row["similarity"]), -int(row["occurrences"])))
    return proposals


def normalise_labels(
    labels: list[str], aliases: dict[str, Alias] | None = None
) -> Normalisation:
    """Fold raw labels onto canonical forms, applying only approved aliases.

    Aliases are resolved in a second pass so that an approved merge cannot
    double-count: occurrences are summed into the final canonical label, not
    into the intermediate one.
    """
    aliases = aliases or {}
    raw_counts = Counter(label.strip() for label in labels if label and label.strip())

    buckets: dict[str, list[str]] = {}
    for label in raw_counts:
        buckets.setdefault(fold(label), []).append(label)

    canonical_per_key: dict[str, str] = {}
    for key, group in buckets.items():
        alias = aliases.get(key)
        if alias:
            canonical_per_key[key] = alias.canonical
        else:
            # Most frequent spelling wins, and ties prefer the title-cased
            # variant so the output style stays consistent with the source's
            # dominant style. This is a display choice, not a clinical one.
            canonical_per_key[key] = max(
                group,
                key=lambda label: (raw_counts[label], label == label.title(), label),
            )

    # A fold key and a reviewed alias may both land on the same canonical, so
    # gather the surviving keys per canonical before counting.
    keys_per_canonical: dict[str, list[str]] = {}
    for key, canonical in canonical_per_key.items():
        keys_per_canonical.setdefault(canonical, []).append(key)

    result = Normalisation(raw_counts=raw_counts)
    for canonical, keys in keys_per_canonical.items():
        members: list[str] = []
        for key in keys:
            members.extend(buckets[key])
        members.sort(key=lambda label: -raw_counts[label])
        result.groups[canonical] = members
        result.counts[canonical] = sum(raw_counts[label] for label in members)
        for member in members:
            result.canonical_for_raw[member] = canonical

    result.candidates = suggest_candidates(result.counts)
    result.stats = {
        "raw_distinct_labels": len(raw_counts),
        "canonical_labels": len(result.groups),
        "collapsed_by_folding": len(raw_counts) - len(result.groups),
        "approved_aliases_applied": sum(1 for key in aliases if key in buckets),
        "total_occurrences": sum(raw_counts.values()),
        "labels_under_min_frequency": sum(
            1 for n in result.counts.values() if n < CANDIDATE_MIN_FREQUENCY
        ),
        "candidates_awaiting_review": len(result.candidates),
    }
    return result
