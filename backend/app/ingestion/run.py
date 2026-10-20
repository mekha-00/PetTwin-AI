"""Pipeline that reads ``data/raw/`` and writes the normalised outputs.

Run with::

    python -m app.ingestion.run

Source files are opened read-only. Everything written lands under
``data/processed/`` and ``data/sample/``. The run is idempotent: the same
inputs produce byte-identical outputs, which the test suite asserts.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.ingestion.normalise import (
    Normalisation,
    load_aliases,
    normalise_labels,
)
from app.ingestion.taxonomy import breed_report, canonical_breed
from app.ingestion.xlsx import iter_csv, read_xlsx

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

CLINICAL_CSV = RAW_DIR / "veterinary_clinical_data.csv"
ANIMAL_XLSX = RAW_DIR / "Animal_Vet.xlsx"
ALIASES = PROJECT_ROOT / "backend" / "app" / "ingestion" / "aliases.csv"

SYMPTOM_COLUMNS = ("Symptom_1", "Symptom_2", "Symptom_3", "Symptom_4", "Symptom_5")


def _write_csv(path: Path, header: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _duplicate_row_count(records: list[dict[str, str]]) -> int:
    seen: Counter = Counter(tuple(sorted(row.items())) for row in records)
    return sum(count - 1 for count in seen.values() if count > 1)


def process_symptoms() -> tuple[Normalisation, list[dict[str, str]]]:
    """Normalise symptom labels in the clinical CSV and write the outputs."""
    records = list(iter_csv(CLINICAL_CSV))
    labels = [
        row[column]
        for row in records
        for column in SYMPTOM_COLUMNS
        if row.get(column)
    ]

    normalisation = normalise_labels(labels, load_aliases(ALIASES))

    normalised_rows: list[dict[str, str]] = []
    for row in records:
        output = dict(row)
        for column in SYMPTOM_COLUMNS:
            value = row.get(column, "")
            output[column] = normalisation.canonicalise(value) if value else ""
        normalised_rows.append(output)

    _write_csv(
        PROCESSED_DIR / "veterinary_clinical_data.normalised.csv",
        list(records[0].keys()),
        normalised_rows,
    )

    mapping_rows = [
        {
            "raw_label": raw,
            "canonical_label": canonical,
            "raw_occurrences": normalisation.raw_counts[raw],
            "canonical_occurrences": normalisation.counts[canonical],
            "merged_with": " | ".join(
                label for label in normalisation.groups[canonical] if label != raw
            ),
        }
        for raw, canonical in sorted(
            normalisation.canonical_for_raw.items(), key=lambda item: item[1]
        )
    ]
    _write_csv(
        PROCESSED_DIR / "symptom_normalisation_map.csv",
        ["raw_label", "canonical_label", "raw_occurrences", "canonical_occurrences", "merged_with"],
        mapping_rows,
    )

    if normalisation.candidates:
        _write_csv(
            PROCESSED_DIR / "review" / "symptom_alias_candidates.csv",
            [
                "candidate",
                "suggested_canonical",
                "similarity",
                "occurrences",
                "canonical_occurrences",
                "status",
            ],
            normalisation.candidates,
        )

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(
        SAMPLE_DIR / "veterinary_clinical_data.sample.csv",
        list(records[0].keys()),
        normalised_rows[:25],
    )
    return normalisation, records


def process_animals() -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Normalise the Animal_Vet workbook, merging the split Labrador breed."""
    records = read_xlsx(ANIMAL_XLSX)
    normalised = [dict(record, breed=canonical_breed(record.get("breed", ""))) for record in records]

    header = list(records[0].keys()) if records else []
    _write_csv(PROCESSED_DIR / "animal_vet.normalised.csv", header, normalised)
    _write_csv(
        SAMPLE_DIR / "animal_vet.sample.csv", header, normalised[:25]
    )
    # Report against the raw records, otherwise the merge is invisible: the
    # normalised records already carry a single spelling.
    return normalised, [asdict(stat) for stat in breed_report(records)]


def build_report(
    normalisation: Normalisation,
    clinical_records: list[dict[str, str]],
    animals: list[dict[str, str]],
    breeds: list[dict[str, object]],
) -> dict[str, object]:
    """Assemble the machine-readable run report."""
    weights: dict[str, list[float]] = {}
    for record in animals:
        species = record.get("species", "")
        try:
            value = float(record.get("weight_kg") or "")
        except ValueError:
            continue
        weights.setdefault(species, []).append(value)

    per_species_weight = {
        species: {
            "count": len(values),
            "min_kg": min(values),
            "max_kg": max(values),
        }
        for species, values in sorted(weights.items())
    }

    return {
        "sources": {
            "veterinary_clinical_data.csv": {
                "rows": len(clinical_records),
                "duplicate_rows": _duplicate_row_count(clinical_records),
                "symptom_normalisation": normalisation.stats,
            },
            "Animal_Vet.xlsx": {
                "rows": len(animals),
                "duplicate_rows": _duplicate_row_count(animals),
                "breeds_merged": {
                    stat["canonical"]: stat["raw_values"]
                    for stat in breeds
                    if len(stat["raw_values"]) > 1
                },
                "weight_kg_by_species": per_species_weight,
            },
        },
        "outputs": sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for base in (PROCESSED_DIR, SAMPLE_DIR)
            for path in base.rglob("*")
            # The report is excluded so repeated runs are byte-identical
            # regardless of whether an earlier run left one behind.
            if path.is_file() and path.name != "ingestion_report.json"
        ),
    }


def main() -> dict[str, object]:
    normalisation, clinical_records = process_symptoms()
    animals, breeds = process_animals()
    report = build_report(normalisation, clinical_records, animals, breeds)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "ingestion_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
