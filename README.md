# PetTwin AI

**A Multi-Agent Digital Twin for Pet Healthcare and Clinical Decision Support**

Final-year BTech project.

> **Built to a demo-grade standard.** This README is explicit about what is real
> and what is deliberately shallow. The system runs end to end and every AI
> feature is honest about its limits. See [Demo-grade scope](#demo-grade-scope).

---

## Purpose

PetTwin AI is a **software-only** system that maintains a *Digital Twin* of an
individual pet — a continuously updated, structured software representation of
that pet's health information and history — and uses cooperating AI components,
a retrieval-augmented veterinary knowledge base, and a retrieval-based
machine-learning component to support veterinary clinical decision making.

The Digital Twin here is a data model and a set of services, not a graphical or
3D representation. There is no 3D animal model, no hardware, no sensors, no
wearables, and no IoT devices anywhere in this project. All inputs are software
data: tabular clinical records, veterinary reference documents, and values
entered by a user or veterinarian.

**Intended use.** A veterinarian or pet owner reviews a pet's twin, and the
system surfaces relevant veterinary guidance from a citable document corpus and
similar recorded cases, each traceable back to its source. The system is an
**assistive** tool. It does not diagnose, does not replace a veterinarian, and
does not prescribe treatment.

> **No compliance claim.** This project has **not** been assessed against HIPAA
> or GDPR and makes **no claim** of compliance with either, or with any other
> privacy or security regulation.

### Current status

**Phases 1 through 7 are complete.** What exists today is a working pet-health
record system with:

- accounts and role-based veterinarian/owner access,
- owned pets and clinical records,
- an on-demand Digital Twin assembled from verified records,
- a **retrieval-augmented generation** pipeline that answers from seven indexed
  veterinary PDFs and cites the passages it used,
- a small **LangGraph agent** (`POST /api/pets/{id}/ask`) that reads a pet's twin
  and searches the corpus to answer a question about that pet,
- **similar-case retrieval** (`GET /api/pets/{id}/similar-cases`) over an
  external labelled case table, shown as recorded cases — not predictions,
- a complete **React frontend** covering all of the above.

Nothing labelled "AI" is simulated. Where a feature is intentionally shallow for
the demo, it says so in [Demo-grade scope](#demo-grade-scope).

---

## Demo-grade scope

This project is presented at **demo grade**: every feature runs, is tested, and
is honest about what it does not do. The following are the deliberate limits, all
of which are safe to state in a viva.

### What is real and working

| Feature | Status |
|---|---|
| Pet records, clinical records, Digital Twin assembly | complete |
| Role-based access (owner, caregiver, veterinarian, clinic) and owner-invited sharing | complete |
| RAG question answering grounded in 7 veterinary PDFs, with page citations | complete |
| LangGraph agent answering about one pet, using twin + corpus tools | complete |
| Similar-case retrieval over the external case table | complete |
| Evidence-based condition ranking from similar recorded cases | complete |
| 279 backend tests, `npm run lint`, `npm run build` | all green |

### What is intentionally shallow

| Area | Demo-grade choice | Why |
|---|---|---|
| Embeddings | `BAAI/bge-small-en-v1.5` via **fastembed** (local ONNX), not a hosted embedding API | No network dependency, runs offline, small enough for a laptop |
| Vector store | NumPy cosine index built in-process, not FAISS | Corpus is 840 chunks; an ANN library would add a dependency for no measured gain |
| Agent | A **single** LangGraph graph with two tools, not the multi-agent team described in the goal | Enough to demonstrate tool routing and guardrails without an LLM cost/robustness risk |
| ML | **Retrieval** of similar cases, **not** a trained classifier | The only labelled dataset is 431 rows across 139 diseases (largest class 15) — too small and too imbalanced to train a trustworthy model. A supervised model here would be theatre |
| Similar-case labels | The diagnosis **recorded for that case**, shown next to a resemblance score | The system must never present a resemblance as a probability of disease |

### What is deliberately not built at any point

- No disease prediction model, no clinical decision support, no risk score.
- No diagnosis, prescription, or treatment advice from the agent or RAG. The
  model is never given a tool that could produce one.
- No sensor, wearable, or real-time data. All inputs are records and documents.
- No compliance certification of any kind.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend — React + Vite + Tailwind + React Router + Axios      │
│  Lucide icons. Auth, pet dashboard, clinical records, twin,     │
│  timeline, clinical reference (RAG), agent Q&A, patients.       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP (Axios → /api)
┌──────────────────────────────▼──────────────────────────────────┐
│  Backend — FastAPI + SQLAlchemy + Pydantic + PostgreSQL          │
│  api/ · core/ · models/ · schemas/ · services/ · ingestion/     │
│  ┌───────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │ agents/       │  │ rag/           │  │ ml/                │  │
│  │ LangGraph     │  │ PyMuPDF →      │  │ fastembed →        │  │
│  │ plan/act loop │  │ fastembed →    │  │ NumPy cosine       │  │
│  │ via Groq LLM  │  │ NumPy cosine   │  │ similar-case       │  │
│  │  BUILT        │  │  BUILT         │  │ retrieval — BUILT  │  │
│  └───────────────┘  └────────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Digital Twin = assembled on demand by a SERVICE (Phase 3, built) from the
verified records in PostgreSQL. It is NOT a table.
```

### Digital Twin rule

**The database stores verified pet information. The Digital Twin is a service
that assembles the pet's current health state from those records on request.**

This distinction is enforced in the schema, not just in documentation:

- There is **no `digital_twin` table**. Persisting an assembled health summary as
  a row would create a second source of truth that silently drifts from the
  clinical records it was derived from.
- `health_timeline_events` is an **append-only event log** of verified facts. It
  records *that* something happened, when, and where it came from. It stores no
  interpretation, no risk score, and no current status.
- A test asserts that no twin table exists
  (`tests/test_startup.py::test_no_digital_twin_table_exists`).
- The twin endpoint is `GET /api/pets/{pet_id}/digital-twin`. There is no
  scheduled job writing it, no cache table, and no sensor data.

### Original records vs AI output

Clinical records are the source of truth and are never overwritten by anything a
model produces. Every record carries:

- `source_type` — `veterinary_record`, `owner_report`, `manual_entry`,
  `dataset_import`, or `ai_analysis`
- `verification_status` — `unverified` or `verified`

`ai_analysis` is reserved in the enum so that AI output, when added, lands in a
separate namespace that **references but never mutates** the source record.
**Phases 4–7 create no AI tables and write no AI output to the database**: the
agent and similar-case search are read-only, and the RAG answer is returned to
the caller rather than persisted.

---

## Technology stack

| Layer | Technology | Installed |
|---|---|---|
| Frontend | React, Vite, Tailwind CSS, React Router, Axios, Lucide React | yes |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, PostgreSQL | yes |
| Auth | PyJWT, bcrypt | yes |
| Testing | pytest, httpx | yes |
| AI / agents | LangGraph, LangChain, Groq API (`openai/gpt-oss-120b`) | yes |
| Retrieval / ML | fastembed (ONNX), NumPy | yes |
| Document processing | PyMuPDF | yes |

The ingestion pipeline under `backend/app/ingestion/` deliberately uses only
the **standard library** (`csv`, `zipfile`, `xml.etree`) so that the project's
dependency surface stays small. There is no `pandas` or `openpyxl`.

> **Model note.** The default Groq model is `openai/gpt-oss-120b`. Earlier
> `llama-3.3-70b-versatile` is **not** available on this account (the API returns
> `model_not_found`). `gpt-oss` models emit reasoning tokens, so the call sets an
> explicit `max_tokens` budget rather than relying on a default.

---

## Database architecture

PostgreSQL 16, SQLAlchemy 2.0 ORM, UUID primary keys, native PostgreSQL enums,
timezone-aware timestamps. Driver: `psycopg2` (`postgresql+psycopg2://`).

### The 12 entities

| # | Model | Table | Purpose |
|---|---|---|---|
| 1 | `User` | `users` | Account, bcrypt hash, role, activation state |
| 2 | `Pet` | `pets` | The subject of a Digital Twin — identity only, no health state |
| 3 | `PetAccess` | `pet_access` | **The authorization gate.** Ownership/access relationship |
| 4 | `HealthRecord` | `health_records` | Canonical verified record header for a clinical event |
| 5 | `SymptomRecord` | `symptom_records` | A single observed clinical sign |
| 6 | `DiagnosisRecord` | `diagnosis_records` | A conclusion reached about a condition |
| 7 | `MedicationRecord` | `medication_records` | Prescribed/administered medication |
| 8 | `VaccinationRecord` | `vaccination_records` | Vaccine administration and next-due date |
| 9 | `LabReport` | `lab_reports` | A single test result with reference range |
| 10 | `VeterinaryVisit` | `veterinary_visits` | One clinical encounter |
| 11 | `HealthTimelineEvent` | `health_timeline_events` | Append-only chronological event log |
| 12 | `PetAllergy` | `pet_allergies` | A known allergen. Added in Phase 3 |

### Relationship shape

```
User ──< PetAccess >── Pet ──< VeterinaryVisit
                              ├──< HealthRecord ──< SymptomRecord
                              │               ├──< DiagnosisRecord
                              │               ├──< MedicationRecord
                              │               ├──< VaccinationRecord
                              │               └──< LabReport
                              └──< HealthTimelineEvent
```

Ownership is a row in `pet_access` (role `owner`), not a column on `users` or
`pets`. A pet can therefore have an owner, a caregiver, a veterinarian, and a
clinic without duplicating the pet. Access is revoked by setting `revoked_at`,
so grants are auditable rather than deleted.

### Database provisioning

Two databases exist, both owned by the `pettwin` role:

| Database | Purpose |
|---|---|
| `pettwin` | Development |
| `pettwin_test` | Test runs (schemas are created and dropped per run) |

Tables are **not** auto-created in normal use (`DB_AUTO_CREATE=False`). To build
the development schema:

```bash
cd backend
.venv\Scripts\python -c "from app.core.database import create_all; create_all()"
```

---

## Authentication and authorization

### Flow

```
register/login  ──►  bcrypt(password)  ──►  users.hashed_password
                                              │
                    create_access_token()     │  HS256, SECRET_KEY from env
                    signs {sub, iat, exp, jti, type, iss, aud}
                                              ▼
                                    Authorization: Bearer <jwt>
                                              │
                    decode_access_token() verifies signature, expiry,
                    issuer, audience, and pins the algorithm
                                              ▼
                                  get_current_user  ──►  User
                                              │
                                  load_accessible_pet(pet_id)  → 404 if not yours
                                              ▼
                                    the pet's records
```

### Password handling

- Passwords are hashed with **bcrypt** (cost 12 by default). The plaintext is
  never stored, never logged, and never returned.
- `UserRead` has no `hashed_password` field, so the hash cannot leak into a
  response even by accident.
- bcrypt silently truncates input past **72 bytes**, so the byte length is
  validated explicitly and a longer password is rejected with a 422 rather than
  being quietly shortened.

### Token handling

- `PyJWT`, algorithm **pinned to HS256** on both encode and decode. A token
  presented with `alg: none`, or signed with a different key, is rejected.
- Claims: `sub`, `iat`, `exp`, `jti`, `type`, `iss`, `aud`. Issuer and audience
  are both verified. `iss`/`aud`/`exp`/`iat`/`sub` are all *required* claims.
- `SECRET_KEY` is read from the environment only. There is **no working
  default**: if it is empty or shorter than 32 characters the app refuses to
  start. A default signing key would let anyone forge tokens.
- `JWT_ALGORITHM` is restricted to `HS256` by a validator.

### Authorization

- Every private pet route resolves the user from the bearer token, never from
  the request body, and then requires an **active `pet_access` grant**.
- **Cross-user access returns 404, not 403.** A 403 would confirm that a pet id
  exists, letting a caller enumerate other people's pets. A test asserts that a
  forbidden pet and a nonexistent pet return byte-identical responses.
- Failed login returns 401 for both an unknown email and a wrong password, so
  the endpoint cannot be used to discover which emails are registered.
- Inactive accounts get 403 on both login and protected routes.
- CORS is an explicit allowlist from the environment. A wildcard origin is never
  used, because the API is token-authenticated.

#### Roles

Two role namespaces exist and are deliberately separate:

- **Account role** (`users.role`): `pet_owner`, `veterinarian`, `clinic_staff`,
  `admin`. A person declares their account role **at signup**
  (`pet_owner` or `veterinarian`); `clinic_staff` and `admin` are **rejected** at
  self-signup and must be provisioned out of band.
- **Pet access role** (`pet_access.role`): `owner`, `caregiver`, `veterinarian`,
  `clinic` — the capability the person holds *for one specific pet*.

| Action | Owner | Caregiver | Veterinarian | Clinic |
|---|---|---|---|---|
| Read the pet and its records | yes | yes | yes | yes |
| Add / edit clinical records | yes | yes | yes | yes |
| Verify a record | no | no | **yes** | no |
| Soft-delete the pet (`DELETE /api/pets/{id}`) | **yes** | 403 | 403 | 403 |
| Purge the pet (`POST /api/pets/{id}/purge`) | **yes** | 403 | 403 | 403 |
| Edit the pet's identity profile | **yes** | yes | no | no |

Soft deletion revokes the access grant of every **collaborator** but deliberately
**keeps the owner's grant**, so the owner can still read the record of what was
known about the animal. Purge is owner-only because erasure permanently destroys
medical history. A veterinarian can read and add to the record and can *verify*
entries, but cannot purge the pet or rewrite its identity.

#### Sharing a pet

An **owner invites a veterinarian by email** through
`POST /api/pets/{pet_id}/access`, optionally with a reason. The invite creates a
`pet_access` row with the chosen pet role. `DELETE
/api/pets/{pet_id}/access/{user_id}` revokes it (sets `revoked_at`, keeping the
row auditable). A veterinarian who self-declares at signup still sees nothing
until an owner grants access to a specific pet.

### Secrets

- No secret is hard-coded anywhere. `.env` is git-ignored; `.env.example`
  contains placeholder names with empty values only.
- `GROQ_API_KEY` is read by the backend only and is never exposed to the
  frontend. Without it, the app runs fully and the AI endpoints return 503.
- **Action required:** the local `SECRET_KEY` and database password in your `.env`
  were set during setup. Rotate the database password if it was ever shared
  outside this machine.

---

## API endpoints

Base prefix: `/api`. Interactive docs at `http://127.0.0.1:8000/docs`.
**34 paths, 63 operations** (excluding the docs/OpenAPI paths).

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | public | Liveness, version, phase, feature flags, DB configured |

#### Auth and users

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | public | Create an account, returns a token |
| `POST` | `/api/auth/login` | public | Exchange credentials for a token (JSON body) |
| `GET` | `/api/auth/me` | bearer | Current authenticated user |
| `GET` | `/api/users/me` | bearer | Basic user profile |
| `PATCH` | `/api/users/me` | bearer | Update own profile only |

#### Pets

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/pets` | bearer | Register a pet |
| `GET` | `/api/pets` | bearer | List pets I can access (`include_deceased`, `search`, paging) |
| `GET` | `/api/pets/{pet_id}` | bearer + grant | Read one of my pets |
| `PATCH` | `/api/pets/{pet_id}` | owner/caregiver | Update a pet |
| `DELETE` | `/api/pets/{pet_id}` | **owner only** | Soft-delete; revokes collaborators, keeps owner |
| `POST` | `/api/pets/{pet_id}/purge` | **owner only** | Permanently destroy the pet and its history |

#### Access sharing (Phase 4)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/pets/{pet_id}/access` | bearer + grant | List active grants for the pet |
| `POST` | `/api/pets/{pet_id}/access` | **owner** | Invite a user by email with a pet role |
| `DELETE` | `/api/pets/{pet_id}/access/{user_id}` | **owner** | Revoke a grant |

#### Allergies

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/pets/{pet_id}/allergies` | owner/caregiver | Record an allergen |
| `GET` | `/api/pets/{pet_id}/allergies` | bearer + grant | List allergens |
| `GET` | `/api/pets/{pet_id}/allergies/{allergy_id}` | bearer + grant | Read one allergen |
| `PATCH` | `/api/pets/{pet_id}/allergies/{allergy_id}` | owner/caregiver | Update, including `verification_status` |
| `DELETE` | `/api/pets/{pet_id}/allergies/{allergy_id}` | owner/caregiver | Remove an allergen |

#### Clinical records

All seven types share the same shape: `POST`/`GET`/`GET {id}`/`PATCH {id}`/
`DELETE {id}` under `/api/pets/{pet_id}/…`, gated on the pet grant.

| Path segment | Model | Additional required fields |
|---|---|---|
| `/health-records` | `HealthRecord` | `title`, `occurred_at` |
| `/symptoms` | `SymptomRecord` | `health_record_id`, `symptom_name` |
| `/diagnoses` | `DiagnosisRecord` | `health_record_id`, `diagnosis_name`, `diagnosed_at` |
| `/medications` | `MedicationRecord` | `health_record_id`, `medication_name`, `started_at` |
| `/vaccinations` | `VaccinationRecord` | `health_record_id`, `vaccine_name`, `administered_at` |
| `/lab-reports` | `LabReport` | `health_record_id`, `test_name`, `performed_at` |
| `/visits` | `VeterinaryVisit` | `visit_at` |

#### Digital Twin

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/pets/{pet_id}/digital-twin` | bearer + grant | Assemble the twin on demand |
| `GET` | `/api/pets/{pet_id}/health-timeline` | bearer + grant | Chronological event log (`verified_only`, paging) |

#### Retrieval-augmented generation (Phase 5)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/rag/query` | bearer | Answer a question from the indexed corpus, with page citations |
| `GET` | `/api/rag/status` | bearer | Corpus readiness and passage count |

`POST /api/rag/query` returns **503** when no `GROQ_API_KEY` is configured or the
embedding model is unavailable. When no passage clears the relevance threshold,
the model is never called and the answer says the corpus does not cover it.

#### Agent (Phase 6)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/pets/{pet_id}/ask` | bearer + grant | Ask a question about one pet |

The agent loads the pet's **verified** twin and can call two read-only tools:
read the twin, and search the corpus. It never diagnoses, prescribes, or writes,
and it returns **503** when no `GROQ_API_KEY` is configured.

#### Similar cases (Phase 7)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/pets/{pet_id}/similar-cases` | bearer + grant | Recorded cases that resemble this pet |

Retrieval only, with a `top_k` of 1–10. Each result shows the diagnosis
**recorded for that case** beside a resemblance score, and the response carries a
disclaimer that this is not a diagnosis. Returns **503** if the index or
embedding model is unavailable.

#### Condition ranking (Phase 7)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/pets/{pet_id}/symptom-options` | bearer + grant | The 25-label symptom vocabulary plus this pet's prefilled symptoms and species |
| `POST` | `/api/pets/{pet_id}/predict-conditions` | bearer + grant | Rank possible conditions from similar recorded cases |

`POST` prefills from the pet's verified twin when the body omits `symptoms`, and
takes an override otherwise. `symptoms` is capped at 50 entries and `top_k` is
1–10. Candidates are ranked by an **evidence score** that is a relative ranking
weight, **not** a probability; the response and UI state this explicitly. Returns
**503** if the index or embedding model is unavailable.

All private pet routes return **404** for a pet the caller cannot access, so pet
ids cannot be enumerated.

---

## How the AI features work

### RAG pipeline (Phase 5) — `backend/app/rag/`

```
rag/documents/*.pdf
  → corpus.py      PyMuPDF extracts text, splits into ~840 overlapping chunks
  → embeddings.py  fastembed (BAAI/bge-small-en-v1.5, local ONNX) → vectors
  → store.py       NumPy matrix, cosine top-k, relevance threshold
  → answer.py      Groq LLM is given ONLY the retrieved passages, must cite them
```

- The index is built **once per process** and cached. Building it embeds all 840
  chunks (a couple of minutes the first time); afterwards queries are fast.
- An eager **warm-up at startup** (`RAG_WARMUP_ON_STARTUP=true`) builds the index
  during the FastAPI lifespan so the first live question does not stall. **The
  test suite disables this** (`RAG_WARMUP_ON_STARTUP=false`) because the
  function-scoped `TestClient` fixture would otherwise rebuild the index per test.
- If no passage clears the threshold, **the LLM is never called** — the answer
  states the corpus does not cover the question. This is asserted by a test.

### Agent (Phase 6) — `backend/app/agents/`

```
START → plan ──(tool calls)──► use_tools ──► plan   (bounded loop)
             └──(no more tools)──► finalize → END
```

- A minimal **LangGraph** graph: a `plan` node asks the LLM, which may emit tool
  calls; `use_tools` runs them; the loop repeats up to `max_steps`, then
  `finalize` forces a prose answer with tools disabled.
- Two tools, both read-only: `read_pet_twin` (the pet's verified twin) and
  `search_literature` (the RAG corpus). The system prompt requires the model to
  answer only from tool results and to **never diagnose or prescribe**.
- Access is checked with `load_accessible_pet` **before** the twin is assembled,
  so an inaccessible pet is a 404 and never reaches the model.

### Similar-case retrieval (Phase 7) — `backend/app/ml/`

```
data/external/animal_disease_prediction.csv
  → dataset.py   parse 431 cases (normalize °C, Yes/No flags, symptoms)
  → features.py  case → feature string; pet twin → the SAME feature string shape
  → similar.py   embed cases once, cosine nearest-neighbour query
  → service.py   build the pet's query from its twin, run the search
```

- **This is retrieval, not prediction.** No classifier is trained.
- The pet's symptoms, species, breed, sex, age band, and weight band are turned
  into the same structured token string as each stored case, so cosine similarity
  is meaningful across both sides.
- Identical duplicate rows from the source file are collapsed so the list is not
  filled with copies.

### Evidence-based condition ranking (Phase 7) — `backend/app/ml/predict.py`

```
pet twin or caller-supplied symptoms
  → features.py            query → the same feature token string as a case
  → similar.py             gather the nearest recorded cases
  → predict.py             group those cases by diagnosis and rank
  → service.py             prefill from the twin, or take an override
```

- **This is not a diagnosis and not a probability.** There is no trained
  classifier; the majority-class baseline in the source table is 20%, so a
  classifier is not defensible.
- Candidates are ranked by `evidence_score = case_count × avg_similarity` — a
  **relative ranking weight**, explicitly *not* a percentage confidence. The API
  and UI never present it as a probability.
- The UI prefills the pet's recorded symptoms and lets the user edit them, so the
  feature works both as "what does my pet's record suggest" and as a what-if tool.
- Each candidate reports how many similar recorded cases carried that diagnosis,
  the average resemblance, and which symptoms were shared.

---

## Environment configuration

Copy the template and fill it in. Every secret value is empty in the template.

```bash
cp .env.example .env
```

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SECRET_KEY` | **yes** | — | Min 32 chars. App refuses to start without it. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | **yes** | — | Assembled into the connection string. |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` | yes | `127.0.0.1` / `5432` / — | |
| `JWT_ALGORITHM` | no | `HS256` | Validator rejects anything else. |
| `JWT_ISSUER` / `JWT_AUDIENCE` | no | `pettwin-api` / `pettwin-frontend` | Both verified on decode. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` | |
| `BCRYPT_ROUNDS` | no | `12` | |
| `DB_AUTO_CREATE` | no | `False` | Leave off outside a throwaway database. |
| `CORS_ORIGINS` | no | localhost:5173 | Comma-separated allowlist. |
| `GROQ_API_KEY` | no | empty | Backend only. Without it, AI endpoints return 503. |
| `GROQ_MODEL` | no | `openai/gpt-oss-120b` | Must be a model the key can access. |
| `RAG_WARMUP_ON_STARTUP` | no | `true` | Build the RAG index at boot. Tests set it `false`. |
| `VITE_API_BASE_URL` | no | `http://localhost:8000/api` | URL, not a secret. |

The connection string is **assembled at runtime** from the `POSTGRES_*` parts.
It is never written in source, never committed, and never sent to the frontend.

`VITE_API_BASE_URL` is the **only** variable the frontend reads. It lives in
`frontend/.env` and is a public URL, never a credential. Vite inlines anything
prefixed `VITE_` into the browser bundle, so no secret may ever use that prefix.

---

## How to run the backend

```bash
# 1. create the virtual environment (first time only)
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. create .env at the project root and fill in SECRET_KEY + POSTGRES_*
#    (optionally set GROQ_API_KEY to enable the AI endpoints)

# 3. build the development schema (first time only)
.venv\Scripts\python -c "from app.core.database import create_all; create_all()"

# 4. start the server
.venv\Scripts\python -m uvicorn app.main:app --reload
```

On first boot the server logs `RAG index ready: N passages indexed`. The API is
then at `http://127.0.0.1:8000` and the docs at `http://127.0.0.1:8000/docs`.

## How to run the frontend

```bash
# from the project root
cd frontend
npm install
cp .env.example .env      # then set VITE_API_BASE_URL if it differs
npm run dev
```

The app is then at `http://localhost:5173`. Use `npm run build` for a production
bundle into `frontend/dist/`, and `npm run lint` for a zero-warning check.

The frontend cannot reach the API until the backend is running and its origin is
listed in `CORS_ORIGINS`.

---

## How to run the ingestion pipeline

Turns the two read-only files in `data/raw/` into normalised outputs in
`data/processed/`.

```bash
# from the backend directory
.venv\Scripts\python -m app.ingestion.run
```

Outputs:

| File | Contents |
|---|---|
| `data/processed/veterinary_clinical_data.normalised.csv` | 10,000 rows, symptom labels folded |
| `data/processed/animal_vet.normalised.csv` | 610 rows, Labrador split merged, dates as ISO |
| `data/processed/symptom_normalisation_map.csv` | raw label to canonical label, with counts |
| `data/processed/ingestion_report.json` | run statistics, duplicate counts, weight by species |
| `data/processed/review/symptom_alias_candidates.csv` | proposed merges awaiting human sign-off |
| `data/sample/*.csv` | 25-row slices for inspection |

**The pipeline never writes to `data/raw/`.** It is deterministic and idempotent:
running it twice produces byte-identical outputs, and a test asserts the source
files' hashes are unchanged.

---

## How to run the tests

```bash
# from the project root
backend\.venv\Scripts\python -m pytest
```

Optional: `backend\.venv\Scripts\python -m pytest -v` for per-test output.

The tests run against **real PostgreSQL**, in the `pettwin_test` database. Each
session creates a uniquely named throwaway schema (`test_<random>`), builds the
tables inside it, and drops the schema on teardown — so parallel runs cannot
collide and nothing is left behind. **SQLite is not used anywhere.**

Coverage:

| File | Tests |
|---|---|
| `tests/test_startup.py` | 11 - startup, routes, OpenAPI, config, 12 tables mapped, no twin table |
| `tests/test_security_password_hashing.py` | 19 - bcrypt hashing, 72-byte guard, no plaintext at rest or in responses, JWT tampering/expiry/`alg:none` |
| `tests/test_auth_api.py` | 15 - registration, duplicate email, input validation, login, inactive account |
| `tests/test_protected_endpoints.py` | 16 - 401/403/404 paths, cross-user pet isolation, CORS allowlist |
| `tests/test_pet_crud.py` | 21 - pet and allergy CRUD, owner-only soft delete and purge |
| `tests/test_pet_authorization.py` | 19 - grant isolation, caregiver capability, 404-not-403 enumeration |
| `tests/test_clinical_records.py` | 20 - the seven clinical record types, validation, cross-pet guards |
| `tests/test_digital_twin.py` | 39 - twin assembly, verified filtering, provenance, timeline |
| `tests/test_phase4_roles_access.py` | 23 - account roles, signup limits, vet capabilities, invite/revoke |
| `tests/test_rag.py` | 16 - chunking, cosine and ranking, `min_score` filter, no-sources ⇒ LLM never called, API auth/422/503 |
| `tests/test_agents.py` | 16 - both tool-call shapes, multi-tool, loop bound, prompt guardrail, budget exhaustion, API |
| `tests/test_similar_cases.py` | 18 - CSV parsing, feature construction, ranking, dedupe, service, API |
| `tests/test_predict.py` | 17 - evidence ranking, aggregation, prefill vs override, guards, API |
| `tests/test_ingestion.py` | 29 - normalisation, Labrador merge, idempotency, raw files untouched |

**Current result: 279 passed.**

The AI tests are **offline**: they stub the embedding model and the Groq LLM, so
they run in milliseconds and need no API key or network. Live behaviour is
verified separately with a real Groq key, the real corpus, and the real database.

There are currently **no frontend tests**: `frontend/package.json` has no test
runner configured. All 279 tests are backend.

---

## Deployment (hosted demo)

The demo is deployed as two Render services plus a free Neon Postgres database:

| Piece | Host | Notes |
|---|---|---|
| `pettwin-api` | Render Web Service (Docker) | Built from `./Dockerfile`, repo root context |
| `pettwin-web` | Render Static Site | `cd frontend && npm install && npm run build` |
| Database | Neon (free tier) | PostgreSQL; TLS required |

### One-time setup

1. **Neon** — create a project, copy the connection details (`host`, `db`, `user`,
   `password`). Neon requires TLS, which `POSTGRES_SSLMODE=require` handles.
2. **Render** — create a Blueprint from this repository. Render reads
   `render.yaml` and provisions both services. When prompted, supply the secret
   env vars:
   - `SECRET_KEY` — the same strong value as local (`secrets.token_urlsafe(64)`).
   - `GROQ_API_KEY` — your Groq key. Without it the AI endpoints return 503.
   - `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — from Neon.
   - `CORS_ORIGINS` — the static site URL (set after the first deploy, then redeploy the API).
   - `VITE_API_BASE_URL` (static site) — the API URL, e.g. `https://pettwin-api.onrender.com/api`.

`DB_AUTO_CREATE=true` is set for the demo so the schema is built on first boot
(there is still no migration tool). The embedding model is baked into the image
at build time, and the two retrieval indexes (`rag`, `ml`) are **committed**
under `backend/index_cache/`, so neither the build nor the first request has to
embed anything.

### Regenerating the committed indexes

Run this whenever a PDF under `rag/documents/` or the case CSV changes, then
commit the result:

```bash
cd backend
python -m app.scripts.build_indexes
```

`tests/test_index_cache.py` fails if the committed files are missing or stale
relative to the corpus.

### Seeding demo data

To land on a populated Digital Twin rather than an empty account, run once:

```bash
# from the backend directory, against the hosted database
.venv\Scripts\python -m app.scripts.seed_demo
```

Idempotent. Creates a demo owner (`demo@pettwin.example` / `Demo12345!`) with a
dog carrying verified symptoms.

### Demo caveats

- **Free web services sleep** after ~15 minutes idle. Waking takes ~1 minute.
  Hit the API once before presenting. The frontend reports an unreachable API
  when the first request lands during that window; reload once it is awake.
- **Ephemeral disk**: nothing is written to disk at runtime. The indexes are
  committed to the repo and loaded read-only from the image.
- **No migrations**: schema comes from `create_all()`. Fine for a demo; a real
  deployment needs Alembic.

---

## Project structure

```
PetTwin-AI/
|-- .env                        # local secrets - git-ignored, never commit
|-- .env.example                # placeholder names only
|-- .gitignore
|-- pytest.ini                  # pythonpath = backend
|-- README.md
|-- DATASET_ANALYSIS.md         # Phase 1 findings, immutable
|-- frontend/                   # React + Vite + Tailwind + React Router
|   |-- index.html
|   |-- package.json
|   |-- vite.config.js
|   |-- .env                    # VITE_API_BASE_URL only, never a secret
|   |-- dist/                   # build output (git-ignored)
|   `-- src/
|       |-- main.jsx            # router + AuthProvider
|       |-- App.jsx             # route table (routes live here, no router.jsx)
|       |-- context/            # AuthContext provider + useAuth hook
|       |-- hooks/              # useAsyncData
|       |-- lib/                # api, endpoints, format
|       |-- components/         # AppLayout, ProtectedRoute, ui, petFormOptions
|       `-- pages/              # Dashboard, MyPets, AddPet, PetDetails,
|                               # DigitalTwin, HealthTimeline, ClinicalReference,
|                               # Patients, NotFound, auth/{Login,Register}
|-- backend/
|   |-- .venv/                  # git-ignored
|   |-- .cache/                 # fastembed ONNX model (git-ignored)
|   |-- requirements.txt
|   `-- app/
|       |-- api/                # deps, auth, users, pets, clinical, access,
|       |                       # digital_twin, rag, agents, ml
|       |-- core/               # config, database, security, jwt
|       |-- models/             # 12 SQLAlchemy models + base.py enums
|       |-- schemas/            # Pydantic request/response models
|       |-- services/           # auth, authorization, access, pet, clinical,
|       |                       # digital_twin, timeline
|       |-- ingestion/          # Phase 1 dataset normalisation (stdlib only)
|       |-- rag/                # Phase 5: corpus, embeddings, store, answer
|       |-- agents/             # Phase 6: tools, graph, service
|       |-- ml/                 # Phase 7: dataset, features, similar, service
|       `-- main.py
|-- data/
|   |-- raw/                    # IMMUTABLE source datasets
|   |-- external/               # Phase 7 case table (431 rows)
|   |-- processed/              # ingestion outputs (regenerable)
|   |   `-- review/             # alias candidates awaiting sign-off
|   `-- sample/                 # 25-row slices for inspection
|-- ml/                         # (top-level placeholder)
|-- rag/
|   |-- documents/              # 7 verified veterinary PDFs (840 chunks)
|   |-- processing/
|   `-- vectorstore/
`-- tests/                      # 279 backend tests
```

---

## Development phases

### Phase 1 — Inspection and scaffolding: **COMPLETE**

Full detail in [DATASET_ANALYSIS.md](./DATASET_ANALYSIS.md). Found 2 real
datasets (`Animal_Vet.xlsx` 610×16, `veterinary_clinical_data.csv` 10000×10) and
7 verified veterinary PDFs (91 pages). **Neither dataset has a disease label**, so
supervised disease-risk training is blocked pending a labelled dataset. That
finding is unchanged and is why Phase 7 is retrieval, not a classifier.

### Phase 2 — Database + authentication foundation: **COMPLETE**

PostgreSQL provisioned, 11 SQLAlchemy models, bcrypt with a 72-byte guard, JWT
with a pinned algorithm, `SECRET_KEY` validation, `PetAccess` authorization with
404-not-403 enumeration protection, CORS allowlist.

### Phase 3 — pet management, clinical records, Digital Twin, frontend: **COMPLETE**

Full pet CRUD, allergy CRUD, all seven clinical record types, the **Digital Twin
assembly service**, the **health timeline service**, the **ingestion pipeline**,
and a complete React frontend. The 12th table (`pet_allergies`) was added here.

#### Dataset ingestion

| Input | Output |
|---|---|
| `veterinary_clinical_data.csv` — 10,000 rows, 925 distinct raw symptom labels | 865 canonical labels (60 collapsed), plus a full mapping table |
| `Animal_Vet.xlsx` — 610 rows, `Labrador` / `Labrador Retriever` split | single `Labrador Retriever` covering 45 rows, dates as ISO 8601 |

Normalisation is **three-tiered and deliberately conservative**: mechanical
unicode/case/punctuation folding; **reviewer-approved aliases** from
`aliases.csv` (ships empty of clinical synonym merges by design); and
**candidate suggestions** written to the review queue as `PENDING_REVIEW`, never
applied automatically. The pipeline cannot invent a clinical vocabulary.

#### Verification filtering

The twin and the verified-only timeline include a record only when it is
verified. The provenance block reports `verified_counts` and `total_counts`
separately, so exclusions are visible rather than silent. **Allergies** are
safety-critical: an allergy enters the twin only when `verification_status` is
`verified`.

### Phase 4 — roles and veterinarian access: **COMPLETE**

- Account roles (`pet_owner`, `veterinarian`, `clinic_staff`, `admin`) with
  `clinic_staff`/`admin` rejected at self-signup.
- Pet-level capabilities enforced per role; a **veterinarian can verify** records
  but cannot purge the pet or edit its identity profile.
- Owner-invited sharing: `POST`/`GET`/`DELETE` under
  `/api/pets/{pet_id}/access`.
- Frontend: role-filtered navigation, a `ProtectedRoute` that accepts a `roles`
  prop, a **Patients** page for veterinarians, and sharing controls on the pet
  detail page.

### Phase 5 — retrieval-augmented generation: **COMPLETE**

840 chunks from 7 PDFs, embedded locally with fastembed, queried by cosine
similarity, answered by Groq **only from retrieved passages** with page citations.
A relevance threshold means an uncovered question never reaches the model.
Startup warm-up keeps the first query fast. Frontend: a **Clinical Reference**
page at `/reference`, available to all signed-in users.

### Phase 6 — minimal LangGraph agent: **COMPLETE**

A two-node plan/act graph with two read-only tools (read the pet's verified twin;
search the corpus), bounded by `max_steps`, ending in a forced prose `finalize`.
Guardrails forbid diagnosis and prescription. Access is checked before the twin is
read. Frontend: an **Ask about this pet** section on the pet detail page.

### Phase 7 — similar-case retrieval: **COMPLETE**

Parses the external 431-row case table, builds a comparable feature string for
both cases and the pet's twin, embeds the cases once, and returns the most similar
recorded cases with a resemblance score and a disclaimer. **No model is trained.**
On top of that retrieval, an **evidence-based condition ranking** groups the
nearest cases by the diagnosis recorded for them and ranks by
`case_count × avg_similarity` — a relative ranking weight, not a probability.
Frontend: a **Similar recorded cases** card and a **Possible conditions from
recorded cases** card on the Digital Twin page.

---

## Known limitations

These are deliberate boundaries, stated so a later phase can decide whether to
lift them.

### Similar cases are retrieval, not prediction

The external table is 431 rows across 139 diseases with a largest class of 15.
No classifier is trained on it, and the resemblance score is **not** a
probability. A case's label is what was recorded for that case.

### `is_alive` is overloaded

`Pet.is_alive` means both "the animal is physically alive" and "appears in the
owner's active list". Soft-deleting a pet sets `is_alive=false`, which the
response renders as though the animal died. Separating the two needs either a
new column on `pets` or a removal table. Left as-is and documented here.

### `viewer_role` is only on two endpoints

`viewer_role` appears on `GET /api/pets` (list) and on the Digital Twin
response, but **not** on `POST /api/pets` or `GET /api/pets/{id}`. The frontend
derives the role from the list endpoint. A contract blemish, not a defect.

### RAG does not roll back through dialogue

`POST /api/rag/query` is stateless: each question is answered independently with
no conversation history, so a follow-up question cannot rely on the previous one.

### Weak-signal grounding

A vague or off-topic question can still retrieve a handful of weakly-related
passages and be answered as "grounded". The relevance floor filters the worst
cases only; a stronger grounding check is future work.

### 39 symptom merges await veterinary sign-off

`data/processed/review/symptom_alias_candidates.csv` lists 39 near-miss pairs
(for example `Pnemonia` → `Pneumonia`, `Abdminal pain` → `Abdominal pain`).
They are **suggestions only**. To adopt one, add a row to
`backend/app/ingestion/aliases.csv` naming an approver, then rerun the pipeline.

### Dataset species exceed the application enum

The ingested workbook covers cows, goats, pigs and horses. The `Species` enum
supports only `dog`, `cat`, `horse`, `rabbit`, `bird`, `reptile`,
`small_mammal`, `other`, so livestock would map to `other`.

### No migration history

`pet_allergies` was created by `create_all()`, so there is no incremental
migration path. Alembic was recommended in Phase 2 and remains unadopted.

### No frontend tests

All 279 tests are backend. There is no test runner in `frontend/package.json`,
so the React app is verified by build and lint only.

---

## Project rules

These constraints are binding and apply to every later phase:

1. **Software only.** No hardware, sensors, wearables, IoT, or physical devices.
2. **No 3D animal model.** The Digital Twin is data, not geometry.
3. **No invented data.** Do not fabricate datasets, research results, model
   accuracy, or medical information. If a result has not been measured, it is
   not stated.
4. **`data/raw/` is immutable.** Never modify or overwrite source datasets.
5. **No plaintext secrets.** Never hard-code credentials or API keys. Never
   expose them to the frontend.
6. **Respect the planned structure.** No random duplicate folders; no frontend
   files under `backend/` and no backend files under `frontend/`.
7. **Every clinical claim must be traceable.** RAG output cites its source
   document and page.
8. **Original records are immutable.** AI-derived output must reference, never
   overwrite, a source clinical record.
9. **Assistive, not autonomous.** The system supports a veterinarian; it does not
   diagnose or prescribe.
10. **No compliance claims.** Do not assert HIPAA or GDPR compliance.

---

## Team

- V S Mekha — PRC23CA053
- Aleena Anil — PRC23CA012
- Ayana S Sethu — PRC23CA021
- Alan Mathew — PRC23CA010
