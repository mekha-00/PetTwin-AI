"""Tests for the Phase 1 dataset ingestion pipeline.

Two properties matter more than any individual mapping:

* ``data/raw/`` is never written. It is the immutable source of record.
* the pipeline is deterministic, so a reviewer can rerun it and diff.

The clinical CSV is read directly in the "source" tests and the real run is
executed once for the output tests, since it is the slowest step.
"""

from __future__ import annotations

import hashlib
from collections import Counter

import pytest

from app.ingestion import run as pipeline
from app.ingestion.normalise import fold, load_aliases, normalise_labels
from app.ingestion.taxonomy import canonical_breed
from app.ingestion.xlsx import read_xlsx

SYMPTOM_COLUMNS = pipeline.SYMPTOM_COLUMNS


def _raw_hashes() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (pipeline.CLINICAL_CSV, pipeline.ANIMAL_XLSX)
    }


class TestSourcesUnchanged:
    def test_raw_files_exist(self):
        assert pipeline.CLINICAL_CSV.exists()
        assert pipeline.ANIMAL_XLSX.exists()

    def test_raw_row_counts_match_phase_one_findings(self):
        clinical = list(pipeline.iter_csv(pipeline.CLINICAL_CSV))
        animals = read_xlsx(pipeline.ANIMAL_XLSX)
        # DATASET_ANALYSIS.md 1.1: 10000 clinical rows, 610 workbook rows.
        assert len(clinical) == 10000
        assert len(animals) == 610

    def test_animal_ids_are_unique(self):
        ids = Counter(row["animal_id"] for row in read_xlsx(pipeline.ANIMAL_XLSX))
        assert max(ids.values()) == 1


class TestFolding:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Fever", "fever"),
            ("  Coughing  ", "coughing"),
            ("Bloody Diarrhea", "bloody diarrhea"),
            ("bloody diarrhea", "bloody diarrhea"),
            ("Shortness of breath.", "shortness of breath"),
            ("Bleedingggg", "bleeding"),
            ("Bleeding", "bleeding"),
        ],
    )
    def test_fold_is_mechanical(self, raw, expected):
        assert fold(raw) == expected

    def test_fold_is_idempotent(self):
        for label in ("Fever", " bloody diarrhea ", "Shortness of breath."):
            once = fold(label)
            assert fold(once) == once

    def test_case_variants_collapse_to_one_canonical(self):
        result = normalise_labels(["Fever", "fever", "FEVER"])
        assert len(result.groups) == 1
        assert list(result.counts.values()) == [3]
        # The most frequent original spelling is kept as the surface form.
        assert "Fever" in result.groups

    def test_canonical_preserves_occurrence_count(self):
        labels = ["Pain"] * 10 + ["Pains"] * 2
        result = normalise_labels(labels)
        assert sum(result.counts.values()) == 12

    def test_approved_aliases_are_applied(self):
        from app.ingestion.normalise import Alias

        aliases = {"loss of appetite": Alias("loss of appetite", "Anorexia", "test", "tester")}
        result = normalise_labels(["Anorexia", "loss of appetite"], aliases)
        assert "Anorexia" in result.groups
        assert result.counts["Anorexia"] == 2
        assert result.stats["approved_aliases_applied"] == 1

    def test_unapproved_alias_is_never_applied(self, tmp_path):
        path = tmp_path / "aliases.csv"
        path.write_text(
            "raw,canonical,reason,approved_by\nloss of appetite,Anorexia,, \n",
            encoding="utf-8",
        )
        assert load_aliases(path) == {}

    def test_candidates_are_reported_not_applied(self):
        result = normalise_labels(["Pneumonia"] * 40 + ["Pnemonia"])
        assert "Pnemonia" in result.groups
        proposal = next(row for row in result.candidates if row["candidate"] == "Pnemonia")
        assert proposal["suggested_canonical"] == "Pneumonia"
        assert proposal["status"] == "PENDING_REVIEW"

    def test_every_occurrence_is_accounted_for(self):
        labels = ["Fever", "fever", "Weight loss", "Pain", "Pains"]
        result = normalise_labels(labels)
        assert sum(result.counts.values()) == len(labels)


class TestBreeds:
    def test_labrador_split_is_merged(self):
        assert canonical_breed("Labrador") == "Labrador Retriever"
        assert canonical_breed("Labrador Retriever") == "Labrador Retriever"

    def test_merge_covers_the_45_rows_named_in_phase_one(self):
        animals = read_xlsx(pipeline.ANIMAL_XLSX)
        merged = [
            row for row in animals if row["breed"].strip() in {"Labrador", "Labrador Retriever"}
        ]
        assert len(merged) == 45

    def test_unrelated_breed_is_untouched(self):
        assert canonical_breed("Siamese") == "Siamese"

    def test_blank_stays_blank(self):
        assert canonical_breed("  ") == ""


@pytest.fixture(scope="module")
def report():
    return pipeline.main()


class TestOutputs:
    def test_processed_files_exist(self, report):
        for relative in (
            "data/processed/veterinary_clinical_data.normalised.csv",
            "data/processed/animal_vet.normalised.csv",
            "data/processed/symptom_normalisation_map.csv",
            "data/processed/ingestion_report.json",
            "data/sample/veterinary_clinical_data.sample.csv",
            "data/sample/animal_vet.sample.csv",
        ):
            assert (pipeline.PROJECT_ROOT / relative).exists(), relative

    def test_row_count_is_preserved(self, report):
        rows = list(pipeline.iter_csv(pipeline.PROCESSED_DIR / "veterinary_clinical_data.normalised.csv"))
        assert len(rows) == 10000

    def test_no_duplicate_symptom_spellings_survive_folding(self, report):
        rows = list(pipeline.iter_csv(pipeline.PROCESSED_DIR / "veterinary_clinical_data.normalised.csv"))
        values = {row[column] for row in rows for column in SYMPTOM_COLUMNS if row[column]}
        assert len(values) == len({fold(value) for value in values})

    def test_breed_merge_applied_in_output(self, report):
        rows = list(pipeline.iter_csv(pipeline.PROCESSED_DIR / "animal_vet.normalised.csv"))
        breeds = {row["breed"] for row in rows}
        assert "Labrador Retriever" in breeds
        assert "Labrador" not in breeds

    def test_dates_are_iso_not_excel_serials(self, report):
        rows = list(pipeline.iter_csv(pipeline.PROCESSED_DIR / "animal_vet.normalised.csv"))
        with_date = [row for row in rows if row.get("mating_date")]
        assert with_date
        for row in with_date:
            assert row["mating_date"][:2] == "20"

    def test_report_records_the_duplicate_rows_phase_one_found(self, report):
        assert report["sources"]["veterinary_clinical_data.csv"]["duplicate_rows"] == 20

    def test_report_records_weight_scale_per_species(self, report):
        weights = report["sources"]["Animal_Vet.xlsx"]["weight_kg_by_species"]
        # A single distribution across species is meaningless, which is why
        # weight is reported per species rather than globally.
        assert len(weights) > 1
        assert max(entry["max_kg"] for entry in weights.values()) > 1000

    def test_raw_files_untouched_by_a_run(self, report):
        assert _raw_hashes() == _RAW_HASHES


_RAW_HASHES = _raw_hashes()
