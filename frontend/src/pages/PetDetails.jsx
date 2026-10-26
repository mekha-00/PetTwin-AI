import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Activity,
  ArrowLeft,
  Bug,
  History,
  Pencil,
  Pill,
  Plus,
  Share2,
  Sparkles,
  Stethoscope,
  Syringe,
  TestTube2,
  TriangleAlert,
  UserPlus,
} from 'lucide-react'

import { useAsyncData } from '../hooks/useAsyncData'
import {
  askAboutPet,
  createAllergy,
  createChildRecord,
  createHealthRecord,
  createVisit,
  deleteAllergy,
  fetchPet,
  grantPetAccess,
  listAllergies,
  listHealthRecords,
  listPetAccess,
  listVisits,
  revokePetAccess,
  updateHealthRecord,
  updatePet,
} from '../lib/endpoints'
import { describeError } from '../lib/api'
import {
  formatDate,
  formatDateTime,
  formatPetAge,
  formatWeight,
  RECORD_TYPE_LABELS,
  sexLabel,
  speciesLabel,
  titleCase,
  VISIT_STATUS_LABELS,
  VISIT_TYPE_LABELS,
} from '../lib/format'
import {
  Badge,
  DetailItem,
  EmptyState,
  ErrorMessage,
  Notice,
  PageLoader,
  SectionCard,
} from '../components/ui'
import { SEX_OPTIONS, SPECIES_OPTIONS } from '../components/petFormOptions'

/** `datetime-local` needs `YYYY-MM-DDTHH:mm`, not an ISO string with a zone. */
function toLocalInputValue(date = new Date()) {
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

const VERIFICATION_TONE = {
  verified: 'good',
  unverified: 'warn',
  disputed: 'stop',
}

/** Timeline-style icon for a health record type. */
function RecordIcon({ type }) {
  const Icon =
    {
      vaccination: Syringe,
      lab_work: TestTube2,
      surgery: Stethoscope,
      treatment: Pill,
      wellness_exam: Stethoscope,
    }[type] ?? Stethoscope
  return <Icon className="h-4 w-4" aria-hidden="true" />
}

// ---------------------------------------------------------------------------
// Allergy editor
// ---------------------------------------------------------------------------
function AllergySection({ petId, isReadOnly, onChanged }) {
  const { data, error, isLoading, reload } = useAsyncData(
    () => listAllergies(petId),
    [petId],
  )
  const [draft, setDraft] = useState({
    allergen: '',
    reaction: '',
    severity: '',
    verified: false,
  })
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState(null)

  async function handleAdd(event) {
    event.preventDefault()
    setBusy(true)
    setFormError(null)
    try {
      await createAllergy(petId, {
        allergen: draft.allergen.trim(),
        reaction: draft.reaction.trim() || null,
        severity: draft.severity ? Number(draft.severity) : null,
        // Unverified allergies stay off the Digital Twin, so the choice is
        // offered up front rather than discovered later.
        verification_status: draft.verified ? 'verified' : 'unverified',
      })
      setDraft({ allergen: '', reaction: '', severity: '', verified: false })
      reload()
      onChanged?.()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRemove(allergy) {
    setBusy(true)
    setFormError(null)
    try {
      await deleteAllergy(petId, allergy.id)
      reload()
      onChanged?.()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  const allergies = data ?? []

  return (
    <SectionCard
      title="Allergies"
      description="Recorded sensitivities. The Digital Twin carries active ones forward."
    >
      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>
      <ErrorMessage>{formError}</ErrorMessage>

      {isLoading ? (
        <PageLoader label="Loading allergies" />
      ) : allergies.length === 0 ? (
        <EmptyState
          icon={Bug}
          title="No allergies recorded"
          description="Record known sensitivities so they appear in the pet's health status."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {allergies.map((allergy) => (
            <li
              key={allergy.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2"
            >
              <div>
                <p className="font-medium">{allergy.allergen}</p>
                <p className="text-sm text-ink-soft">
                  {allergy.reaction || 'No reaction described'}
                  {allergy.severity ? ` · severity ${allergy.severity}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={allergy.is_active ? 'stop' : 'neutral'}>
                  {allergy.is_active ? 'active' : 'inactive'}
                </Badge>
                <Badge tone={VERIFICATION_TONE[allergy.verification_status] ?? 'neutral'}>
                  {allergy.verification_status}
                </Badge>
                {!isReadOnly ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleRemove(allergy)}
                    disabled={busy}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {!isReadOnly ? (
        <form onSubmit={handleAdd} className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-3">
          <div>
            <label className="field-label" htmlFor="allergen">
              Allergen
            </label>
            <input
              id="allergen"
              required
              className="field-input"
              value={draft.allergen}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, allergen: event.target.value }))
              }
            />
          </div>
          <div>
            <label className="field-label" htmlFor="reaction">
              Reaction
            </label>
            <input
              id="reaction"
              className="field-input"
              value={draft.reaction}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, reaction: event.target.value }))
              }
            />
          </div>
          <div>
            <label className="field-label" htmlFor="severity">
              Severity (1&ndash;5)
            </label>
            <input
              id="severity"
              type="number"
              min="1"
              max="5"
              className="field-input"
              value={draft.severity}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, severity: event.target.value }))
              }
            />
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-3">
            <input
              type="checkbox"
              checked={draft.verified}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, verified: event.target.checked }))
              }
            />
            A veterinarian has confirmed this allergy
          </label>
          <div className="sm:col-span-3">
            <button
              type="submit"
              className="btn btn-secondary"
              disabled={busy || draft.allergen.trim().length === 0}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add allergy
            </button>
            <p className="mt-2 text-xs text-ink-soft">
              Only verified allergies appear in the pet&rsquo;s Digital Twin health
              status. Unverified ones stay listed here.
            </p>
          </div>
        </form>
      ) : null}
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------
// Health record + visit entry
// ---------------------------------------------------------------------------
function RecordEntryForm({ petId, onChanged, canVerify }) {
  const [form, setForm] = useState({
    title: '',
    record_type: 'wellness_exam',
    occurred_at: toLocalInputValue(),
    symptoms: '',
    diagnosis: '',
    medication: '',
    vaccine: '',
    verified: false,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function update(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)

    // A veterinarian recording something they observed can mark it verified at
    // the point of entry; it then reaches the Digital Twin immediately.
    const verificationStatus = form.verified ? 'verified' : 'unverified'

    const visit = await createVisit(petId, {
      visit_at: new Date(form.occurred_at).toISOString(),
      visit_type: 'wellness',
      status: 'completed',
      reason_for_visit: form.title.trim(),
      verification_status: verificationStatus,
    })

    try {
      const record = await createHealthRecord(petId, {
        title: form.title.trim(),
        record_type: form.record_type,
        occurred_at: new Date(form.occurred_at).toISOString(),
        visit_id: visit.id,
        verification_status: verificationStatus,
      })

      // Child records are attached to the health record that created them, so
      // each is added only when the owner actually supplied a value.
      const children = [
        ['symptoms', 'name', form.symptoms],
        ['diagnoses', 'name', form.diagnosis],
        ['medications', 'name', form.medication],
        ['vaccinations', 'vaccine', form.vaccine],
      ]

      for (const [kind, field, value] of children) {
        if (!value.trim()) continue
        const payload = {
          health_record_id: record.id,
          [field]: value.trim(),
          verification_status: verificationStatus,
        }
        if (kind === 'symptoms') payload.onset_at = new Date(form.occurred_at).toISOString()
        if (kind === 'diagnoses') {
          payload.diagnosed_at = new Date(form.occurred_at).toISOString()
          payload.status = 'active'
          payload.is_confirmed = false
        }
        if (kind === 'medications') {
          payload.started_at = new Date(form.occurred_at).toISOString()
          payload.is_active = true
        }
        if (kind === 'vaccinations') {
          payload.administered_at = new Date(form.occurred_at).toISOString()
          payload.is_booster = false
        }
        await createChildRecord(petId, kind, payload)
      }

      setForm((prev) => ({ ...prev, title: '', symptoms: '', diagnosis: '', medication: '', vaccine: '' }))
      onChanged?.()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
      <ErrorMessage>{error}</ErrorMessage>
      <p className="text-sm text-ink-soft">
        A completed visit is created alongside the record so the new entry is properly
        linked on the timeline. Records start <strong>unverified</strong>; owners and
        veterinarians can mark them verified below.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="hr_title">
            Title
          </label>
          <input
            id="hr_title"
            required
            className="field-input"
            value={form.title}
            onChange={update('title')}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="hr_type">
            Record type
          </label>
          <select id="hr_type" className="field-input" value={form.record_type} onChange={update('record_type')}>
            {Object.entries(RECORD_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="hr_occurred">
            Occurred at
          </label>
          <input
            id="hr_occurred"
            type="datetime-local"
            className="field-input"
            value={form.occurred_at}
            onChange={update('occurred_at')}
          />
        </div>
      </div>

      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="field-label">Optional details</legend>
        <div>
          <label className="field-label" htmlFor="hr_symptom">
            Symptom
          </label>
          <input id="hr_symptom" className="field-input" value={form.symptoms} onChange={update('symptoms')} />
        </div>
        <div>
          <label className="field-label" htmlFor="hr_diagnosis">
            Diagnosis
          </label>
          <input id="hr_diagnosis" className="field-input" value={form.diagnosis} onChange={update('diagnosis')} />
        </div>
        <div>
          <label className="field-label" htmlFor="hr_medication">
            Medication
          </label>
          <input id="hr_medication" className="field-input" value={form.medication} onChange={update('medication')} />
        </div>
        <div>
          <label className="field-label" htmlFor="hr_vaccine">
            Vaccine
          </label>
          <input id="hr_vaccine" className="field-input" value={form.vaccine} onChange={update('vaccine')} />
        </div>
      </fieldset>

      {canVerify ? (
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={form.verified}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, verified: event.target.checked }))
          }
        />
        <span>
          Mark this record as <strong>verified</strong>. Only do this when a
          veterinarian has confirmed the details; an unverified record stays off
          the Digital Twin.
        </span>
      </label>
      ) : null}

      <div>
        <button
          type="submit"
          className="btn btn-secondary"
          disabled={busy || form.title.trim().length === 0}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {busy ? 'Saving…' : 'Add health record'}
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Inline profile editor
// ---------------------------------------------------------------------------
function EditProfileForm({ pet, onSaved, onCancel }) {
  const [form, setForm] = useState({
    name: pet.name ?? '',
    species: pet.species ?? 'dog',
    breed: pet.breed ?? '',
    sex: pet.sex ?? 'unknown',
    current_weight_kg: pet.current_weight_kg ?? '',
    notes: pet.notes ?? '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function update(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      // Only the changed, non-empty fields are sent: the backend's PATCH treats
      // an absent field as "leave unchanged" and rejects a fully empty body.
      const payload = { name: form.name.trim() }
      if (form.breed.trim()) payload.breed = form.breed.trim()
      if (form.current_weight_kg) payload.current_weight_kg = Number(form.current_weight_kg)
      if (form.notes.trim()) payload.notes = form.notes.trim()
      if (form.species !== pet.species) payload.species = form.species
      if (form.sex !== pet.sex) payload.sex = form.sex

      await updatePet(pet.id, payload)
      onSaved()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <ErrorMessage>{error}</ErrorMessage>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="edit_name">
            Name
          </label>
          <input id="edit_name" required className="field-input" value={form.name} onChange={update('name')} />
        </div>
        <div>
          <label className="field-label" htmlFor="edit_species">
            Species
          </label>
          <select id="edit_species" className="field-input" value={form.species} onChange={update('species')}>
            {SPECIES_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="edit_breed">
            Breed
          </label>
          <input id="edit_breed" className="field-input" value={form.breed} onChange={update('breed')} />
        </div>
        <div>
          <label className="field-label" htmlFor="edit_sex">
            Sex
          </label>
          <select id="edit_sex" className="field-input" value={form.sex} onChange={update('sex')}>
            {SEX_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label" htmlFor="edit_weight">
            Weight (kg)
          </label>
          <input
            id="edit_weight"
            type="number"
            step="0.1"
            min="0"
            className="field-input"
            value={form.current_weight_kg}
            onChange={update('current_weight_kg')}
          />
        </div>
      </div>

      <div>
        <label className="field-label" htmlFor="edit_notes">
          Notes
        </label>
        <textarea
          id="edit_notes"
          rows={3}
          className="field-input"
          value={form.notes}
          onChange={update('notes')}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy || !form.name.trim()}>
          {busy ? 'Saving…' : 'Save changes'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Sharing (owner-only)
// ---------------------------------------------------------------------------
const GRANT_ROLE_OPTIONS = [
  { value: 'veterinarian', label: 'Veterinarian', hint: 'Can review history and add records' },
  { value: 'caregiver', label: 'Caregiver', hint: 'Can add records for this pet' },
  { value: 'clinic', label: 'Clinic', hint: 'Practice-level access' },
]

/**
 * Owner-only panel for inviting a veterinarian or caregiver by email.
 *
 * The invite is addressed to an existing account: the API resolves the address
 * server-side and reports an unknown one as a 404, so there is no public way to
 * discover which emails are registered.
 */
function ShareSection({ petId }) {
  const { data, error, isLoading, reload } = useAsyncData(
    () => listPetAccess(petId),
    [petId],
  )
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('veterinarian')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState(null)

  const grants = data ?? []
  const collaborators = grants.filter((grant) => grant.role !== 'owner')

  async function handleInvite(event) {
    event.preventDefault()
    setBusy(true)
    setFormError(null)
    try {
      await grantPetAccess(petId, { email: email.trim(), role })
      setEmail('')
      reload()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRevoke(userId) {
    setBusy(true)
    setFormError(null)
    try {
      await revokePetAccess(petId, userId)
      reload()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      title="Shared access"
      description="Invite a veterinarian or caregiver to this pet's records."
      actions={<Share2 className="h-4 w-4 text-ink-soft" aria-hidden="true" />}
    >
      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      {isLoading ? (
        <p className="text-sm text-ink-soft">Loading who has access…</p>
      ) : collaborators.length === 0 ? (
        <EmptyState
          icon={Stethoscope}
          title="Not shared with anyone"
          description="Only you can see this pet right now. Invite a vet below to share its records."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {collaborators.map((grant) => (
            <li
              key={grant.user_id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2"
            >
              <div className="min-w-0">
                <p className="font-medium">{grant.full_name || grant.email}</p>
                <p className="text-sm text-ink-soft">
                  {grant.email} · {titleCase(grant.role)}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-secondary text-stop"
                onClick={() => handleRevoke(grant.user_id)}
                disabled={busy}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleInvite} className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
        <ErrorMessage>{formError}</ErrorMessage>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <div>
            <label className="field-label" htmlFor="share-email">
              Their account email
            </label>
            <input
              id="share-email"
              type="email"
              required
              className="field-input"
              placeholder="vet@clinic.example"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="share-role">
              Access level
            </label>
            <select
              id="share-role"
              className="field-input"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {GRANT_ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy || !email.trim()}>
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            {busy ? 'Working…' : 'Invite'}
          </button>
        </div>
        <p className="text-xs text-ink-soft">
          {GRANT_ROLE_OPTIONS.find((option) => option.value === role)?.hint}
        </p>
      </form>

      <Notice tone="info">
        A shared vet can review this pet and add clinical records, but cannot edit
        the profile, remove the pet, or erase its history. Revoking takes effect
        immediately.
      </Notice>
    </SectionCard>
  )
}

/**
 * Ask the assistant a question about this pet.
 *
 * The answer comes from the pet's verified records and the indexed veterinary
 * documents; the panel names which of the two the agent used, so the source of
 * an answer is never a mystery. The request runs on submit, not on mount, since
 * each call is an LLM round trip.
 */
function AskAgentSection({ petId, petName }) {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const trimmed = question.trim()
  const canAsk = trimmed.length >= 3 && !busy

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canAsk) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const answer = await askAboutPet(petId, trimmed)
      setResult(answer)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  function toolLabel(tool) {
    if (tool === 'read_pet_twin') return 'this pet’s records'
    if (tool === 'search_literature') return 'the veterinary documents'
    return tool
  }

  return (
    <SectionCard
      title="Ask about this pet"
      description={`Answers use ${petName}'s verified records and the indexed veterinary documents.`}
      actions={<Sparkles className="h-4 w-4 text-ink-soft" aria-hidden="true" />}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <label className="field-label" htmlFor="agent-question">
            Your question
          </label>
          <textarea
            id="agent-question"
            className="field-input min-h-20 resize-y"
            placeholder={`e.g. Is ${petName} up to date on vaccinations?`}
            value={question}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={!canAsk}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {busy ? 'Thinking…' : 'Ask'}
          </button>
          <span className="text-xs text-ink-soft">{trimmed.length}/500</span>
        </div>
      </form>

      <ErrorMessage>{error}</ErrorMessage>

      {result ? (
        <div className="mt-4 rounded-lg border border-line bg-canvas px-3 py-3">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</p>
          </div>

          {result.tools_used?.length > 0 ? (
            <p className="mt-3 text-xs text-ink-soft">
              Looked at {result.tools_used.map(toolLabel).join(' and ')}.
            </p>
          ) : null}

          <p className="mt-3 border-t border-line pt-2 text-xs text-ink-soft">
            {result.disclaimer}
          </p>
        </div>
      ) : null}
    </SectionCard>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function PetDetails() {
  const { petId } = useParams()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [verifyingId, setVerifyingId] = useState(null)
  const [verifyError, setVerifyError] = useState(null)

  const { data: pet, error, isLoading, reload } = useAsyncData(
    () => fetchPet(petId),
    [petId],
  )
  const { data: records, error: recordsError, reload: reloadRecords } = useAsyncData(
    () => listHealthRecords(petId, { limit: 10 }),
    [petId],
  )
  const { data: visits, error: visitsError, reload: reloadVisits } = useAsyncData(
    () => listVisits(petId, { limit: 5 }),
    [petId],
  )

  const refreshAll = useCallback(() => {
    reload()
    reloadRecords()
    reloadVisits()
  }, [reload, reloadRecords, reloadVisits])

  // Verification is what moves a record onto the Digital Twin, so it is a
  // first-class action here rather than something only the API can do.
  const toggleVerification = useCallback(
    async (record) => {
      const next =
        record.verification_status === 'verified' ? 'unverified' : 'verified'
      setVerifyingId(record.id)
      setVerifyError(null)
      try {
        await updateHealthRecord(petId, record.id, {
          verification_status: next,
        })
        reloadRecords()
      } catch (err) {
        setVerifyError(describeError(err))
      } finally {
        setVerifyingId(null)
      }
    },
    [petId, reloadRecords],
  )

  if (isLoading) return <PageLoader label="Loading pet" />
  if (error || !pet) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorMessage onRetry={reload}>{error ?? 'Pet not found.'}</ErrorMessage>
        <Link to="/pets" className="btn btn-secondary">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to my pets
        </Link>
      </div>
    )
  }

  const healthRecords = records?.items ?? []
  const visitRows = visits?.items ?? []
  // `GET /pets/{id}` now reports the caller's role, so no second list call is
  // needed. Owners may change everything; every other role may add records but
  // not edit the profile. Mirrors the backend's WRITE_ROLES / owner-only split.
  const viewerRole = pet.viewer_role
  const isOwner = viewerRole === 'owner'
  const canWrite =
    isOwner ||
    viewerRole === 'caregiver' ||
    viewerRole === 'veterinarian' ||
    viewerRole === 'clinic'
  // Verification promotes an entry onto the Digital Twin, so it is narrower
  // than write access: caregivers and clinics may add records but not confirm
  // them. Mirrors the backend's VERIFY_ROLES.
  const canVerify = isOwner || viewerRole === 'veterinarian'

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/pets" className="text-sm text-ink-soft hover:underline">
            <ArrowLeft className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
            My pets
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">{pet.name}</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {speciesLabel(pet.species)}
            {pet.breed ? ` · ${pet.breed}` : ''} · {sexLabel(pet.sex)}
            {pet.is_neutered ? ' · neutered' : ''}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Link to={`/pets/${pet.id}/digital-twin`} className="btn btn-primary">
            <Activity className="h-4 w-4" aria-hidden="true" />
            Digital Twin
          </Link>
          <Link to={`/pets/${pet.id}/timeline`} className="btn btn-secondary">
            <History className="h-4 w-4" aria-hidden="true" />
            Timeline
          </Link>
        </div>
      </header>

      <ErrorMessage onRetry={refreshAll}>{error}</ErrorMessage>

      <SectionCard
        title="Profile"
        description={`Verification: ${pet.verification_status} · source: ${pet.source_type}`}
        actions={
          isOwner && !editing ? (
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              Edit
            </button>
          ) : null
        }
      >
        {editing ? (
          <EditProfileForm pet={pet} onSaved={() => { setEditing(false); reload() }} onCancel={() => setEditing(false)} />
        ) : (
          <dl className="grid gap-4 sm:grid-cols-3">
            <DetailItem label="Age">{formatPetAge(pet)}</DetailItem>
            <DetailItem label="Date of birth">{formatDate(pet.date_of_birth)}</DetailItem>
            <DetailItem label="Weight">{formatWeight(pet.current_weight_kg)}</DetailItem>
            <DetailItem label="Colour">{pet.color}</DetailItem>
            <DetailItem label="Microchip">{pet.microchip_id}</DetailItem>
            <DetailItem label="Registered">{formatDate(pet.created_at)}</DetailItem>
            {pet.notes ? (
              <div className="sm:col-span-3">
                <DetailItem label="Notes">{pet.notes}</DetailItem>
              </div>
            ) : null}
          </dl>
        )}
      </SectionCard>

      <AllergySection petId={pet.id} isReadOnly={false} onChanged={reload} />

      <AskAgentSection petId={pet.id} petName={pet.name} />

      <SectionCard
        title="Recent health records"
        description={records ? `${records.total} record${records.total === 1 ? '' : 's'} in total` : undefined}
      >
        <ErrorMessage onRetry={reloadRecords}>{recordsError}</ErrorMessage>
        <ErrorMessage>{verifyError}</ErrorMessage>

        {healthRecords.length === 0 ? (
          <EmptyState
            icon={Stethoscope}
            title="No health records yet"
            description="Add the first record below to start building this pet's history."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {healthRecords.map((record) => (
              <li
                key={record.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    <RecordIcon type={record.record_type} />
                    {record.title}
                  </p>
                  <p className="text-sm text-ink-soft">
                    {RECORD_TYPE_LABELS[record.record_type] ?? titleCase(record.record_type)} ��{' '}
                    {formatDateTime(record.occurred_at)}
                    {record.clinic_name ? ` �� ${record.clinic_name}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={VERIFICATION_TONE[record.verification_status] ?? 'neutral'}>
                    {record.verification_status}
                  </Badge>
                  {canVerify ? (
                    <button
                      type="button"
                      className="btn btn-secondary px-2 py-1 text-xs"
                      onClick={() => toggleVerification(record)}
                      disabled={verifyingId === record.id}
                    >
                      {record.verification_status === 'verified' ? 'Unverify' : 'Verify'}
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}

        {canWrite ? (
          <RecordEntryForm petId={pet.id} onChanged={refreshAll} canVerify={canVerify} />
        ) : null}
      </SectionCard>

      {isOwner ? <ShareSection petId={pet.id} /> : null}

      <SectionCard
        title="Recent veterinary visits"
        description={visits ? `${visits.total} visit${visits.total === 1 ? '' : 's'} in total` : undefined}
      >
        <ErrorMessage onRetry={reloadVisits}>{visitsError}</ErrorMessage>

        {visitRows.length === 0 ? (
          <EmptyState
            icon={Stethoscope}
            title="No visits recorded"
            description="Visits are created automatically when you add a health record."
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {visitRows.map((visit) => (
              <li key={visit.id} className="rounded-lg border border-line px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    {VISIT_TYPE_LABELS[visit.visit_type] ?? titleCase(visit.visit_type)}
                  </p>
                  <Badge tone="neutral">
                    {VISIT_STATUS_LABELS[visit.status] ?? titleCase(visit.status)}
                  </Badge>
                </div>
                <p className="text-sm text-ink-soft">
                  {formatDateTime(visit.visit_at)}
                  {visit.reason_for_visit ? ` · ${visit.reason_for_visit}` : ''}
                </p>
                {visit.veterinarian_name || visit.clinic_name ? (
                  <p className="text-sm text-ink-soft">
                    {[visit.veterinarian_name, visit.clinic_name].filter(Boolean).join(' · ')}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <Notice tone="info">
        <span className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            Records you add are marked <strong>unverified</strong> until someone
            allowed to verify confirms them; use <strong>Verify</strong> on a record
            once it is confirmed. Only verified records appear on the Digital Twin.
          </span>
        </span>
      </Notice>

      <div>
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/pets')}>
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to my pets
        </button>
      </div>
    </div>
  )
}
