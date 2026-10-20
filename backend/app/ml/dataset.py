"""Load the labelled animal case table used for similar-case retrieval.

``data/external/animal_disease_prediction.csv`` holds 431 recorded cases with a
diagnosis per row. It is far too small and too imbalanced for a classifier — the
largest class is 15 rows across 139 diseases — so it is used only as a corpus to
*retrieve* cases that look like the pet under discussion. Nothing here predicts
a disease; each row's label is shown as the diagnosis that was recorded for that
case, with the resemblance the search found.

Parsing is defensive: the file is external, so a malformed number or a missing
column must not crash the request. Bad values become ``None`` and the row is kept
with whatever else it has.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = PROJECT_ROOT / "data" / "external" / "animal_disease_prediction.csv"

#: Booleans in the file are stored as Yes/No strings.
_YES = {"yes", "y", "true", "1"}

#: The four symptom slots plus the fixed symptom flags, in file order.
_SYMPTOM_COLUMNS = ("Symptom_1", "Symptom_2", "Symptom_3", "Symptom_4")
_FLAG_COLUMNS = (
    "Appetite_Loss",
    "Vomiting",
    "Diarrhea",
    "Coughing",
    "Labored_Breathing",
    "Lameness",
    "Skin_Lesions",
    "Nasal_Discharge",
    "Eye_Discharge",
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class CaseRecord:
    """One recorded case from the external table."""

    index: int
    animal_type: str
    breed: str | None
    age_years: float | None
    gender: str | None
    weight_kg: float | None
    symptoms: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    duration: str | None = None
    body_temperature_c: float | None = None
    heart_rate_bpm: float | None = None
    disease: str = ""


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    match = _NUMBER_RE.search(str(raw).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_yes(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in _YES


def _clean(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def parse_row(row: dict[str, str], index: int) -> CaseRecord | None:
    """Turn one CSV row into a :class:`CaseRecord`, or ``None`` if unusable.

    A row without an animal type or a recorded disease carries no retrievable
    information, so it is dropped rather than indexed.
    """
    animal_type = _clean(row.get("Animal_Type"))
    disease = _clean(row.get("Disease_Prediction"))
    if not animal_type or not disease:
        return None

    symptoms = [
        cleaned
        for column in _SYMPTOM_COLUMNS
        if (cleaned := _clean(row.get(column))) is not None
    ]
    flags = [column.replace("_", " ").lower() for column in _FLAG_COLUMNS if _is_yes(row.get(column))]

    return CaseRecord(
        index=index,
        animal_type=animal_type,
        breed=_clean(row.get("Breed")),
        age_years=_to_float(row.get("Age")),
        gender=_clean(row.get("Gender")),
        weight_kg=_to_float(row.get("Weight")),
        symptoms=symptoms,
        flags=flags,
        duration=_clean(row.get("Duration")),
        body_temperature_c=_to_float(row.get("Body_Temperature")),
        heart_rate_bpm=_to_float(row.get("Heart_Rate")),
        disease=disease,
    )


def load_cases(csv_path: Path | None = None) -> list[CaseRecord]:
    """Read every usable case from ``csv_path``.

    Returns an empty list when the file is absent, so a missing external asset
    degrades the feature instead of breaking the app.
    """
    path = csv_path or DEFAULT_CSV
    if not path.exists():
        return []

    cases: list[CaseRecord] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for raw_index, row in enumerate(reader):
            record = parse_row(row, len(cases))
            if record is not None:
                cases.append(record)
    return cases


#: The fixed symptom flags, as display labels, in the order the columns appear.
FLAG_LABELS = (
    "Appetite Loss",
    "Vomiting",
    "Diarrhea",
    "Coughing",
    "Labored Breathing",
    "Lameness",
    "Skin Lesions",
    "Nasal Discharge",
    "Eye Discharge",
)


def symptom_vocabulary(csv_path: Path | None = None) -> list[str]:
    """Return the distinct symptom labels used across the case table.

    This drives the symptom picker: it is every free-text symptom value that
    appears in a case, plus the fixed flag labels, de-duplicated
    case-insensitively and sorted for a stable order. Retaining the original
    casing of the first occurrence keeps the labels readable.
    """
    cases = load_cases(csv_path)
    seen: dict[str, str] = {}
    for case in cases:
        for symptom in case.symptoms:
            seen.setdefault(symptom.strip().lower(), symptom.strip())
        for flag in case.flags:
            seen.setdefault(flag.strip().lower(), flag.strip())
    for label in FLAG_LABELS:
        seen.setdefault(label.lower(), label)
    return sorted(seen.values(), key=str.lower)

