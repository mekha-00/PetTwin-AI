/**
 * Typed wrappers around the Phase 3 API endpoints.
 *
 * Each function returns the parsed body directly so page components deal in
 * data, not in axios response envelopes. Errors propagate for the caller to
 * render via `describeError`.
 */
import api from './api'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export async function register({ email, password, full_name, role, clinic_name }) {
  const { data } = await api.post('/auth/register', {
    email,
    password,
    full_name,
    role,
    clinic_name,
  })
  return data
}

export async function login({ email, password }) {
  const { data } = await api.post('/auth/login', { email, password })
  return data
}

export async function fetchCurrentUser() {
  const { data } = await api.get('/auth/me')
  return data
}

// ---------------------------------------------------------------------------
// Pets
// ---------------------------------------------------------------------------
export async function listPets({ includeDeceased = false } = {}) {
  const { data } = await api.get('/pets', {
    params: { include_deceased: includeDeceased },
  })
  return data
}

export async function fetchPet(petId) {
  const { data } = await api.get(`/pets/${petId}`)
  return data
}

export async function createPet(payload) {
  const { data } = await api.post('/pets', payload)
  return data
}

export async function updatePet(petId, payload) {
  const { data } = await api.patch(`/pets/${petId}`, payload)
  return data
}

/** Soft delete: the pet leaves the list, clinical history is preserved. */
export async function softDeletePet(petId) {
  const { data } = await api.delete(`/pets/${petId}`)
  return data
}

/** Permanent erase, owner-only. Destroys the clinical history. */
export async function purgePet(petId) {
  const { data } = await api.post(`/pets/${petId}/purge`)
  return data
}

// ---------------------------------------------------------------------------
// Access grants (Phase 4) — who else can see a pet. Owner-only.
// ---------------------------------------------------------------------------
export async function listPetAccess(petId) {
  const { data } = await api.get(`/pets/${petId}/access`)
  return data
}

export async function grantPetAccess(petId, { email, role, reason }) {
  const { data } = await api.post(`/pets/${petId}/access`, { email, role, reason })
  return data
}

export async function revokePetAccess(petId, userId) {
  const { data } = await api.delete(`/pets/${petId}/access/${userId}`)
  return data
}

// ---------------------------------------------------------------------------
// Allergies
// ---------------------------------------------------------------------------
export async function listAllergies(petId, { activeOnly = true } = {}) {
  const { data } = await api.get(`/pets/${petId}/allergies`, {
    params: { active_only: activeOnly },
  })
  return data
}

export async function createAllergy(petId, payload) {
  const { data } = await api.post(`/pets/${petId}/allergies`, payload)
  return data
}

export async function updateAllergy(petId, allergyId, payload) {
  const { data } = await api.patch(`/pets/${petId}/allergies/${allergyId}`, payload)
  return data
}

export async function deleteAllergy(petId, allergyId) {
  const { data } = await api.delete(`/pets/${petId}/allergies/${allergyId}`)
  return data
}

// ---------------------------------------------------------------------------
// Clinical records
// ---------------------------------------------------------------------------
export async function listVisits(petId, params = {}) {
  const { data } = await api.get(`/pets/${petId}/visits`, { params })
  return data
}

export async function listHealthRecords(petId, params = {}) {
  const { data } = await api.get(`/pets/${petId}/health-records`, { params })
  return data
}

export async function createHealthRecord(petId, payload) {
  const { data } = await api.post(`/pets/${petId}/health-records`, payload)
  return data
}

export async function createVisit(petId, payload) {
  const { data } = await api.post(`/pets/${petId}/visits`, payload)
  return data
}

/** Creates a child record (symptom, diagnosis, …) under a health record. */
export async function createChildRecord(petId, kind, payload) {
  const { data } = await api.post(`/pets/${petId}/${kind}`, payload)
  return data
}

/** Paginated list for any of the five child record types. */
export async function listChildRecords(petId, kind, params = {}) {
  const { data } = await api.get(`/pets/${petId}/${kind}`, { params })
  return data
}

// ---------------------------------------------------------------------------
// Digital Twin
// ---------------------------------------------------------------------------
export async function fetchDigitalTwin(petId) {
  const { data } = await api.get(`/pets/${petId}/digital-twin`)
  return data
}

export async function fetchHealthTimeline(petId, params = {}) {
  const { data } = await api.get(`/pets/${petId}/health-timeline`, { params })
  return data
}

// ---------------------------------------------------------------------------
// RAG (Phase 5) — ask a question against the indexed veterinary documents.
//
// These override the client's 20s timeout. The server warms the index at
// startup, but the very first query on a cold or just-restarted server still
// includes an LLM round trip, so a default timeout would be too tight.
// ---------------------------------------------------------------------------
const RAG_TIMEOUT_MS = 90000

export async function fetchRagStatus() {
  const { data } = await api.get('/rag/status', { timeout: RAG_TIMEOUT_MS })
  return data
}

export async function askRag({ question, topK = 4 }) {
  const { data } = await api.post(
    '/rag/query',
    { question, top_k: topK },
    { timeout: RAG_TIMEOUT_MS },
  )
  return data
}

// ---------------------------------------------------------------------------
// Agent (Phase 6) — ask a question about one pet.
//
// The agent reads the pet's verified twin and searches the corpus, so this is
// slower than a plain RAG query: it may make several model round trips.
// ---------------------------------------------------------------------------
const AGENT_TIMEOUT_MS = 120000

export async function askAboutPet(petId, question) {
  const { data } = await api.post(
    `/pets/${petId}/ask`,
    { question },
    { timeout: AGENT_TIMEOUT_MS },
  )
  return data
}

// ---------------------------------------------------------------------------
// Similar cases (Phase 7) — recorded cases that resemble this pet.
//
// Retrieval only: the server embeds the pet's twin features and returns the
// closest recorded cases. It is not a prediction, and the label on each case is
// the diagnosis that was recorded for that case.
// ---------------------------------------------------------------------------
export async function fetchSimilarCases(petId, { topK = 5 } = {}) {
  const { data } = await api.get(`/pets/${petId}/similar-cases`, {
    params: { top_k: topK },
  })
  return data
}

// ---------------------------------------------------------------------------
// Candidate conditions (Phase 7) — evidence-based ranking, NOT a probability.
//
// The server aggregates similar recorded cases into ranked candidate diseases.
// It is not a trained classifier: each candidate reports how many retrieved
// cases carried that recorded diagnosis. Never present this as a confidence.
// ---------------------------------------------------------------------------
export async function fetchSymptomOptions(petId) {
  const { data } = await api.get(`/pets/${petId}/symptom-options`)
  return data
}

export async function predictConditions(petId, { symptoms, species, topK = 5 } = {}) {
  const body = {}
  if (symptoms !== undefined) body.symptoms = symptoms
  if (species !== undefined) body.species = species
  const { data } = await api.post(`/pets/${petId}/predict-conditions`, body, {
    params: { top_k: topK },
  })
  return data
}
