# Dataset Analysis

**Project:** PetTwin AI — A Multi-Agent Digital Twin for Pet Healthcare and Clinical Decision Support
**Phase:** 1 (Inspection and scaffolding)
**Analysis date:** 2026-09-28
**Analysis tools used:** Python 3.11.9, pandas 2.3.3, openpyxl, PyMuPDF 1.27.2.3

This document records only what was actually found on disk. No dataset values, row
counts, page counts, model accuracies, or medical conclusions in this file were
estimated, assumed, or invented. Every number below was produced by reading the
files.

---

## 1. Discovery context

At the start of Phase 1 no `PetTwin-AI` directory existed on this machine. All
source material was located as loose files in the user profile's `Downloads`
folder, mixed with unrelated personal files.

Files were **copied** into this project. The originals in `Downloads` were not
moved, renamed, modified, or deleted. All nine copied files were verified
byte-identical (MD5) to their source after copying.

---

## 2. Datasets found

Two tabular datasets were found. Both are real files with real contents; neither
contains a target/label column for supervised disease prediction.

### 2.1 `data/raw/veterinary_clinical_data.csv`

| Property | Value |
|---|---|
| File name | `veterinary_clinical_data.csv` |
| File type | CSV, comma-separated, UTF-8 |
| Size | 977,990 bytes |
| Rows | 10,000 |
| Columns | 10 |
| Memory (pandas deep) | 5,528,943 bytes |

**Columns and dtypes**

| Column | dtype | Role |
|---|---|---|
| `AnimalName` | object | categorical — species |
| `Breed` | object | categorical |
| `Age` | float64 | numeric |
| `Weight_kg` | float64 | numeric |
| `MedicalHistory` | object | categorical — past history |
| `Symptom_1` | object | free text |
| `Symptom_2` | object | free text |
| `Symptom_3` | object | free text |
| `Symptom_4` | object | free text |
| `Symptom_5` | object | free text |

**Missing values:** 0 in every one of the 10 columns.

**Duplicate records:** 20 exact full-row duplicates.

**Numerical field summary**

| Field | count | mean | std | min | 25% | 50% | 75% | max |
|---|---|---|---|---|---|---|---|---|
| `Age` | 10000 | 8.428050 | 4.639286 | 0.5 | 4.8 | 8.4 | 12.0 | 18.0 |
| `Weight_kg` | 10000 | 14.891990 | 12.624691 | 2.5 | 5.3 | 7.3 | 25.5 | 45.0 |

**Categorical field summary**

`AnimalName` — 2 unique values, with inconsistent casing:

| Value | Count |
|---|---|
| `Dog` | 5,020 |
| `cat` | 4,980 |

`Breed` — 18 unique values:

| Breed | Count | Breed | Count |
|---|---|---|---|
| Mixed Breed | 1,105 | British Shorthair | 499 |
| Ragdoll | 620 | Persian | 499 |
| Bengal | 614 | Labrador Retriever | 484 |
| Siamese | 584 | Boxer | 483 |
| Scottish Fold | 572 | Beagle | 475 |
| Bulldog | 559 | Poodle | 450 |
| Rottweiler | 557 | Golden Retriever | 435 |
| German Shepherd | 535 | Maine Coon | 515 |
| Sphynx | 511 | Yorkshire Terrier | 503 |

`MedicalHistory` — 11 unique values:

| Value | Count | Value | Count |
|---|---|---|---|
| Skin conditions history | 1,017 | Allergies | 897 |
| No previous conditions | 995 | Dental issues | 889 |
| Recent surgery | 953 | Parasite history | 888 |
| Chronic illness | 940 | Previous kidney disease | 870 |
| Not vaccinated | 922 | Vaccinated | 832 |
| | | Previous heart condition | 797 |

**Symptom columns — key finding**

The five symptom columns hold free-text entries, not a controlled vocabulary.

- Total symptom cells: 50,000 (10,000 rows × 5 slots)
- **Unique symptom labels observed: 935**
- Ten core labels dominate the distribution:

| Symptom label | Occurrences |
|---|---|
| Fever | 3,524 |
| Weight loss | 3,066 |
| Diarrhea | 2,980 |
| Pain | 2,684 |
| Coughing | 2,655 |
| Lethargy | 2,602 |
| Vomiting | 2,600 |
| Weakness | 2,540 |
| Sneezing | 2,432 |
| Anorexia | 2,406 |

- The ten core labels fill all 5 slots in 8,465 of 10,000 rows (84.65%)
- 1,535 rows contain no core label at all
- Rows by number of core labels present: 0 → 1,535; 1 → 1,420; 2 → 1,162; 3 → 1,671; 4 → 2,328; 5 → 1,884
- **2,813 rows repeat a symptom within the same row** (2,841 when compared case-insensitively)

**Data-quality issues observed (examples quoted verbatim from the file)**

- Case variants of the same concept: `Fever` (3,524) vs `fever` (88)
- Appetite variants: `loss of appetite` (303), `Loss of appetite` (190), `Loss of  appetite` (94, double space), `Loss of Appetite` (79)
- Synonym pairs: `Pain` (2,684) vs `Pains` (537); `Dyspnea` (134) vs `Difficulty in breathing` (186)
- Species-mismatched or questionable labels appear in rows, e.g. `Drop on egg production` on a Dog row, `Fetopelvic dispropotion` and `Uteria inertia` on cat rows
- Symptom vocabulary mixes general signs (`Fever`, `Diarrhea`) with condition-specific signs (`Malpresentation`, `Fetopelvic dispropotion`), which is consistent with the column being populated from more than one source

**Possible target variable:** none. There is no diagnosis, disease, outcome, or
label column. A target would have to be supplied or derived in a later phase, and
deriving one from the symptom columns would be a modelling decision, not a fact
present in the data. This has not been done.

**Critical structural limitation:** there is **no pet identifier column** and **no
date or timestamp column**. Each row is a single anonymous encounter snapshot.
This dataset therefore cannot represent an individual pet's history on its own,
and cannot by itself populate a Digital Twin.

### 2.2 `data/raw/Animal_Vet.xlsx`

| Property | Value |
|---|---|
| File name | `Animal_Vet.xlsx` |
| File type | Excel workbook (OOXML) |
| Size | 60,072 bytes |
| Sheets | 1 — `animal_vet_data3` |
| Rows (in sheet) | 610 |
| Columns | 16 |

**Columns and dtypes**

| Column | dtype | Role |
|---|---|---|
| `Animal_ID` | object | identifier — `ANML001` … `ANML610` |
| `Species` | object | categorical |
| `Breed` | object | categorical |
| `Age_Years` | float64 | numeric |
| `Weight_kg` | float64 | numeric |
| `Mating_Date` | datetime64 | date |
| `Estimated_Delivery_Date` | object | date (nullable) |
| `Pregnancy_Status` | object | categorical |
| `Body_Temperature_F` | float64 | numeric — vital sign |
| `Discharge_Type` | object | categorical (nullable) |
| `Behavior_Change` | object | categorical |
| `Appetite_Change` | object | categorical |
| `Fetal_Heart_Sound` | object | categorical |
| `Vomiting` | object | categorical |
| `Brucella_Test_Result` | object | categorical — lab test |
| `Toxoplasma_Test_Result` | object | categorical — lab test |

**Missing values**

| Column | Missing | % of 610 |
|---|---|---|
| `Estimated_Delivery_Date` | 271 | 44.4% |
| `Discharge_Type` | 186 | 30.5% |

All other 14 columns have 0 missing values.

**Duplicate records:** 0. `Animal_ID` is unique across all 610 rows, spanning
`ANML001` to `ANML610`.

**Numerical field summary**

| Field | count | mean | std | min | 25% | 50% | 75% | max |
|---|---|---|---|---|---|---|---|---|
| `Age_Years` | 610 | 4.684098 | 2.303818 | 0.5 | 2.9 | 4.4 | 6.3 | 12.0 |
| `Weight_kg` | 610 | 143.841754 | 491.410773 | 2.3 | 7.2 | 35.2 | 132.925 | 11512.0 |
| `Body_Temperature_F` | 610 | 101.827213 | 1.015971 | 99.0 | 101.1 | 101.8 | 102.7 | 104.0 |

`Weight_kg` spans 2.3 kg to 11,512 kg. This is a multi-species scale (a cat and
a bovine are not on the same weight distribution), so weight must be analysed or
modelled per species, not globally. `Body_Temperature_F` is tightly distributed
in a plausible physiological band and behaves as a clean vital sign.

**Categorical field summary**

`Species` — 7 unique values:

| Species | Count |
|---|---|
| Cat | 162 |
| Goat | 141 |
| Cow | 138 |
| Dog | 138 |
| Horse | 13 |
| Rabbit | 12 |
| Pig | 6 |

`Breed` — 21 unique values:

| Breed | Count | Breed | Count |
|---|---|---|---|
| Jersey | 112 | Quarter Horse | 5 |
| Persian | 56 | New Zealand White | 5 |
| Maine Coon | 56 | Thoroughbred | 4 |
| Alpine | 51 | Yorkshire | 4 |
| Siamese | 50 | Dutch | 4 |
| Beagle | 49 | Arabian | 4 |
| Boer | 47 | Flemish Giant | 3 |
| German Shepherd | 44 | Landrace | 2 |
| Nubian | 43 | Labrador | 20 |
| Labrador Retriever | 25 | Holstein | 14 |
| | | Gir | 12 |

`Labrador` (20) and `Labrador Retriever` (25) are the same breed recorded under
two different labels — a merge will be required before use.

**Binary and test fields**

| Field | Values and counts |
|---|---|
| `Pregnancy_Status` | Yes 339, No 271 |
| `Vomiting` | Yes 310, No 300 |
| `Fetal_Heart_Sound` | Detected 310, Not Detected 300 |
| `Appetite_Change` | Normal 226, Increased 199, Decreased 185 |
| `Behavior_Change` | Aggressive 156, Nesting 152, Normal 135, Restless 132, Lethargic 35 |
| `Discharge_Type` | Bloody 191, Clear 183, Purulent 50, **missing 186** |
| `Brucella_Test_Result` | Not Done 216, Negative 207, Positive 187 |
| `Toxoplasma_Test_Result` | Not Done 217, Negative 214, Positive 179 |

`Mating_Date` ranges from 2025-02-27 to 2025-07-23.

**Possible target variable:** none. There is no diagnosis, disease, or outcome
column. The closest things to outcomes are `Discharge_Type` and the two test
result fields, but none of these is a disease label, and `Discharge_Type` is 30.5%
missing.

**Scope note:** this dataset is a **pregnancy and reproductive health** record
set — mating date, estimated delivery, pregnancy status, fetal heart sound,
brucellosis and toxoplasmosis screening, and discharge type. It is valuable for
the Digital Twin, but it does not cover general clinical disease.

**Strength for the Digital Twin:** unlike the CSV, this dataset has a genuine
per-animal identifier (`Animal_ID`) and real dates, which is the minimum needed
to assemble a longitudinal per-pet history.

---

## 3. Target variable assessment (summary of a real gap)

Neither available dataset contains a disease or diagnosis label. A supervised
disease-risk model cannot be trained on them as they stand. Per the project's
Phase 1 rules, **no target was invented and no model was trained**. A properly
labelled disease dataset is required before the ML pipeline in `ml/` can be
built.

Additionally, the CSV has no pet identifier, so it cannot anchor a Digital Twin
without a designed identifier and timestamp layer. Both gaps are recorded here
rather than papered over.

---

## 4. Suitability assessment

| Dataset | (a) Digital Twin health records | (b) Disease-risk ML | (c) Veterinary RAG |
|---|---|---|---|
| `veterinary_clinical_data.csv` | **Partial** — good clinical attributes (species, breed, age, weight, medical history, symptoms) but **no pet ID and no dates**, so rows cannot be grouped into a per-pet timeline without new design work. 20 dupes, 935 raw symptom labels, casing/synonym issues need a normalisation pass. | **Not suitable as-is** — no target column. | **Not applicable** — tabular data is not a RAG corpus. |
| `Animal_Vet.xlsx` | **Yes, strongest available** — `Animal_ID` unique across 610 rows, real dates, vitals, lab tests, clinical observations. Covers the reproductive-health subdomain. Weaknesses: 44.4% missing delivery date, 30.5% missing discharge type, `Labrador`/`Labrador Retriever` split, multi-species weight scale. | **Not suitable as-is** — no target column. | **Not applicable** — tabular data is not a RAG corpus. |

### Suitability for (a), in short

`Animal_Vet.xlsx` is the better Digital Twin source because a Digital Twin is by
definition per-individual and time-ordered, and this file has both a key and
timestamps. `veterinary_clinical_data.csv` contributes the broader clinical
picture (symptoms, medical history) but is anonymous and untimed, so it will
require an identity-and-time design before it can be attached to any twin.

### Suitability for (b), in short

Neither file can be used. The blocker is a missing label, not data volume. Both
files are large enough by row count; what is absent is ground truth.

### Suitability for (c), in short

RAG sources are the PDFs in section 5, not these two files.

---

## 5. Documents found (veterinary RAG candidates)

Ten veterinary or animal-health PDFs were found. Titles and page counts below were
read directly from the PDFs with PyMuPDF.

### 5.1 Accepted into `rag/documents/` — 7 files

| File | Pages | Verified title / identifier |
|---|---|---|
| `WSAVA-Vaccination-guidelines-2024.pdf` | 40 | "2024 guidelines for the vaccination of dogs and cats" — World Small Animal Veterinary Association (WSAVA) Vaccination Guidelines Group; *Journal of Small Animal Practice*, 2024 |
| `Dogs-Vaccination-Table.pdf` | 1 | WSAVA "Core vaccines for pet dogs" table (single page) |
| `AI_Veterinary_Assistance_Enhancing_Clinical_Decision-Making_in_Animal_Healthcare.pdf` | 13 | "AI Veterinary Assistance: Enhancing Clinical Decision-Making in Animal Healthcare" — DOI `10.1109/ACCESS.2025.3587787`, IEEE Access, published 10 July 2025 |
| `PIIS2666389924001612.pdf` | 15 | "Concepts and applications of digital twins in healthcare and medicine" — Zhang K. et al., *Cell Biomaterials* |
| `1-s2.0-S0034528825002504-main.pdf` | 10 | "Artificial intelligence and companion animals: Perspectives on digital healthcare for dogs, cats, and pet ownership" — Arshad M.F. et al., Univ. of Sassari |
| `2411.10466v1.pdf` | 9 | "IUMENTA\*: A generic framework for animal digital twins within the Open Digital Twin Platform" — Youssef A. et al., Wageningen University and Research (arXiv) |
| `fvets-13-1744053.pdf` | 13 | PDF title metadata: "From machine learning to digital twin integration for livestock production and research" — DOI `10.3389/fvets.2026.1744053`, *Frontiers in Veterinary Science*, published 02 February 2026 |

### 5.2 Found but deliberately NOT copied

| File | Reason |
|---|---|
| `WSAVA-Vaccination-guidelines-2024 (1).pdf` | **Exact byte-for-byte duplicate** of `WSAVA-Vaccination-guidelines-2024.pdf` (both 831,198 bytes, MD5 prefix `75f1b6c1d362`, both 40 pages). Copying it would put the same document in the RAG corpus twice. |
| `PAWSENSE AI ABSTRACT (3).pdf` | This is **our own project's abstract** — "PetTwin AI: A Multi-Agent Digital Twin for Pet Healthcare and Clinical Decision Support", Team 4. Feeding our own write-up into the RAG index would be self-referential and would let the system cite itself. It is a project document, not a knowledge source. Left in `Downloads`. |
| `jmir-2025-1-e55015.pdf` | "Digital Twins for Clinical and Operational Decision-Making: Scoping Review" — *JMIR*, 22 pages. Relevant digital-twin background, but **human** healthcare, not veterinary. Held back for possible background reading. |
| `s44433-026-00019-4.pdf` | "Animal digital twins: systems architecture for climate-smart protein production" — *npj Veterinary Sciences*, 6 pages. Animal digital twins, but oriented to **livestock production and sensor-based farm records**, not pet clinical records. Weak fit for this project. |

### 5.3 Corroborating note file (not copied)

`S0034528825002504.txt` — a 3-line plain-text note mapping DOIs to the PDFs that
were downloaded. Its contents are:

- `Zhang K., Zhou H.Y., Baptista-Hon D.T., et al. Concepts and Applications of Digital Twins in Healthcare and Medicine. Cell Biomaterials, 2024` → `PIIS2666389924001612.pdf`
- `Research in Veterinary Science, vol. 193, Art. no. 105776, 2025, doi: 10.1016/j.rvsc.2025.105776` → `1-s2.0-S0034528825002504-main.pdf`
- `Volume 13 - 2026 | https://doi.org/10.3389/fvets.2026.1744053` → `fvets-13-1744053.pdf`

This confirms the PDFs were deliberately collected for this project. The named
*Research in Veterinary Science* article (`10.1016/j.rvsc.2025.105776`) is
referenced in the note but **no corresponding PDF is present in `Downloads`** —
it is a missing source, recorded here as an open item.

### 5.4 RAG notes and risks

- **Content overlap:** `Dogs-Vaccination-Table.pdf` is a single-page extract of
  the same WSAVA material contained in the 40-page
  `WSAVA-Vaccination-guidelines-2024.pdf`. At ingestion both would be chunked
  into a FAISS index, producing near-duplicate vectors. The table is useful as a
  fast-retrieval summary, but chunk-level deduplication will be needed.
- **Chunkability:** 7 documents, 91 pages total. All contain extractable text
  layers (PyMuPDF returned readable text from page 1 of every file), so no OCR
  step is required.
- **Domain split of the corpus:** 5 of 7 are pet/veterinary-clinical
  (WSAVA ×2, IEEE AI Veterinary Assistance, AI & companion animals, IUMENTA
  animal twins), 1 is human healthcare digital twins (Cell Biomaterials), and 1 is
  livestock ML/digital-twin (Frontiers Vet Sci). Only the veterinary-clinical
  subset should be allowed to answer clinical pet questions; the other two need
  either exclusion or explicit metadata labelling.
- **Citation safety:** the RAG layer must cite source document and page for every
  retrieved passage so that a generated clinical suggestion is always traceable
  to a real, named source.

---

## 6. Files inspected and excluded as irrelevant

Present in `Downloads`, confirmed unrelated to PetTwin AI, not copied:

| File | Type | Reason |
|---|---|---|
| `Iris.csv`, `Iris (1).csv` | CSV | Iris flower dataset — no veterinary content |
| `STUDENTSCORE_DATASET (1).csv` | CSV | 24 rows, columns `Hours, Scores` — student scores, no veterinary content |
| `program 12.ipynb`, `Program10.ipynb`, `Program11.ipynb` | Jupyter | Coursework notebooks, not project assets |
| `Dog Emotions.jpg` | JPEG | Image, not a dataset |
| `S0034528825002504.txt` | TXT | DOI note file, see 5.3 |
| `social-feed-platform/`, `social-feed-platform-1/`, `academic_quest/`, `gcc/`, `seminar/`, `shukulu/`, `Newproject/` | Dirs | Unrelated pre-existing projects |
| Resumes, CVs, govt application forms, `MINI PROJECT REPORT` files, presentation templates, installer `.exe`/`.msi` files | Various | Personal and unrelated files |

No data was taken from any of the above.

---

## 7. Open items for Phase 2

1. **Obtain a labelled disease dataset.** The single hard blocker on the ML
   pipeline. No target exists in current data.
2. **Decide the Digital Twin identity design.** `Animal_Vet.xlsx` supplies
   `Animal_ID`; `veterinary_clinical_data.csv` supplies none. A pet entity,
   encounter/event, and observation schema must be designed so both sources can
   be attached without fabricating identifiers.
3. **Build a symptom normalisation map.** 935 raw labels, 20 duplicate rows,
   and the case/synonym variants listed in 2.1 need collapsing to a controlled
   vocabulary. The mapping must be derived from the data and reviewed, not
   guessed.
4. **Handle `Labrador` vs `Labrador Retriever`** in `Animal_Vet.xlsx` (45 rows
   total) as a single breed.
5. **Model weight per species** in `Animal_Vet.xlsx`; the 2.3–11,512 kg range is
   not a single distribution.
6. **Decide RAG corpus policy** for the non-clinical and overlapping documents
   described in 5.4.
7. **Track down the missing source** `10.1016/j.rvsc.2025.105776`
   (Research in Veterinary Science, vol. 193, art. 105776, 2025), referenced in
   5.3 but not present on disk.
