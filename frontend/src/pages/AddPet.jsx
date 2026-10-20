import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle } from 'lucide-react'

import { createHealthRecord, createPet, createVisit } from '../lib/endpoints'
import { describeError } from '../lib/api'
import { RECORD_TYPE_LABELS, VISIT_TYPE_LABELS } from '../lib/format'
import { ErrorMessage, Notice, SectionCard } from '../components/ui'
import { SPECIES_OPTIONS, SEX_OPTIONS } from '../components/petFormOptions'

/** `datetime-local` needs `YYYY-MM-DDTHH:mm`, not an ISO string with a zone. */
function toLocalInputValue(date) {
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

const EMPTY_PET = {
  name: '',
  species: 'dog',
  breed: '',
  sex: 'unknown',
  date_of_birth: '',
  estimated_age_months: '',
  microchip_id: '',
  color: '',
  current_weight_kg: '',
  is_neutered: false,
  notes: '',
}

/**
 * Pre-fill the record timestamp with the current moment.
 *
 * `Date` is impure, so this runs inside a lazy `useState` initialiser: it is
 * evaluated once when the form mounts and then never again, rather than on every
 * render. That is a deliberate one-time default, not a value derived from props.
 */
function defaultRecordDraft() {
  const now = toLocalInputValue(new Date())
  return {
    title: '',
    record_type: 'wellness_exam',
    occurred_at: now,
    visit_type: 'wellness',
    visit_at: now,
    reason_for_visit: '',
  }
}

/**
 * Age can be given as a date of birth or as an estimate in months. The backend
 * rejects both together when they disagree, so the form offers one or the other
 * rather than letting the user fill in both and hit an error.
 */
function usesDateOfBirth(form) {
  return Boolean(form.date_of_birth)
}

export default function AddPet() {
  const navigate = useNavigate()

  const [form, setForm] = useState(EMPTY_PET)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // Optional first record, created in the same flow.
  const [includeFirstRecord, setIncludeFirstRecord] = useState(false)
  const [firstRecord, setFirstRecord] = useState(defaultRecordDraft)

  function update(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function updateFirstRecord(field) {
    return (event) =>
      setFirstRecord((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function buildPayload() {
    const payload = {
      name: form.name.trim(),
      species: form.species,
      breed: form.breed.trim() || null,
      sex: form.sex,
      is_neutered: form.is_neutered,
      microchip_id: form.microchip_id.trim() || null,
      color: form.color.trim() || null,
      current_weight_kg: form.current_weight_kg
        ? Number(form.current_weight_kg)
        : null,
      notes: form.notes.trim() || null,
    }

    if (usesDateOfBirth(form)) {
      payload.date_of_birth = form.date_of_birth
    } else if (form.estimated_age_months) {
      payload.estimated_age_months = Number(form.estimated_age_months)
    } else {
      payload.date_of_birth = null
      payload.estimated_age_months = null
    }
    return payload
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const pet = await createPet(buildPayload())

      if (includeFirstRecord && firstRecord.title.trim()) {
        // A visit first, then a health record attached to it, so the timeline
        // has a properly linked entry from the very beginning.
        const visit = await createVisit(pet.id, {
          visit_at: new Date(firstRecord.visit_at).toISOString(),
          visit_type: firstRecord.visit_type,
          status: 'completed',
          reason_for_visit: firstRecord.reason_for_visit.trim() || null,
          verification_status: 'unverified',
        })
        await createHealthRecord(pet.id, {
          title: firstRecord.title.trim(),
          record_type: firstRecord.record_type,
          occurred_at: new Date(firstRecord.occurred_at).toISOString(),
          visit_id: visit.id,
          verification_status: 'unverified',
        })
      }

      navigate(`/pets/${pet.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = form.name.trim().length > 0

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold">Add a pet</h1>
        <p className="mt-1 text-sm text-ink-soft">
          You will be recorded as this pet&rsquo;s owner. Only the pet&rsquo;s own details
          are collected here.
        </p>
      </header>

      <ErrorMessage>{error}</ErrorMessage>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
        <SectionCard title="Identity" description="Who this pet is.">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                required
                className="field-input"
                value={form.name}
                onChange={update('name')}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="species">
                Species
              </label>
              <select
                id="species"
                className="field-input"
                value={form.species}
                onChange={update('species')}
              >
                {SPECIES_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="field-label" htmlFor="breed">
                Breed <span className="font-normal">(optional)</span>
              </label>
              <input
                id="breed"
                className="field-input"
                value={form.breed}
                onChange={update('breed')}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="sex">
                Sex
              </label>
              <select
                id="sex"
                className="field-input"
                value={form.sex}
                onChange={update('sex')}
              >
                {SEX_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="field-label" htmlFor="color">
                Colour <span className="font-normal">(optional)</span>
              </label>
              <input
                id="color"
                className="field-input"
                value={form.color}
                onChange={update('color')}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="microchip_id">
                Microchip ID <span className="font-normal">(optional)</span>
              </label>
              <input
                id="microchip_id"
                className="field-input"
                value={form.microchip_id}
                onChange={update('microchip_id')}
              />
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="Age and weight"
          description="Give either a date of birth or an age estimate, not both."
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="field-label" htmlFor="date_of_birth">
                Date of birth
              </label>
              <input
                id="date_of_birth"
                type="date"
                className="field-input"
                value={form.date_of_birth}
                onChange={(event) => {
                  const value = event.target.value
                  setForm((prev) => ({
                    ...prev,
                    date_of_birth: value,
                    // Clear the conflicting estimate rather than submitting both.
                    estimated_age_months: value ? '' : prev.estimated_age_months,
                  }))
                }}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="estimated_age_months">
                Age in months
              </label>
              <input
                id="estimated_age_months"
                type="number"
                min="0"
                max="360"
                disabled={usesDateOfBirth(form)}
                className="field-input"
                value={form.estimated_age_months}
                onChange={update('estimated_age_months')}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="current_weight_kg">
                Weight (kg)
              </label>
              <input
                id="current_weight_kg"
                type="number"
                step="0.1"
                min="0"
                className="field-input"
                value={form.current_weight_kg}
                onChange={update('current_weight_kg')}
              />
            </div>
          </div>

          <label className="mt-4 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_neutered}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, is_neutered: event.target.checked }))
              }
            />
            Neutered or spayed
          </label>
        </SectionCard>

        <SectionCard title="Notes" description="Anything worth remembering.">
          <textarea
            className="field-input min-h-24"
            rows={3}
            value={form.notes}
            onChange={update('notes')}
            placeholder="Temperament, handling notes, anything a vet should know."
          />
        </SectionCard>

        <SectionCard
          title="First health record (optional)"
          description="Add a starting record now, or skip this and add records later."
        >
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeFirstRecord}
              onChange={(event) => setIncludeFirstRecord(event.target.checked)}
            />
            I have a visit or exam to record now
          </label>

          {includeFirstRecord ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="fr_title">
                  Record title
                </label>
                <input
                  id="fr_title"
                  className="field-input"
                  value={firstRecord.title}
                  onChange={updateFirstRecord('title')}
                  placeholder="Annual wellness exam"
                />
              </div>

              <div>
                <label className="field-label" htmlFor="fr_type">
                  Record type
                </label>
                <select
                  id="fr_type"
                  className="field-input"
                  value={firstRecord.record_type}
                  onChange={updateFirstRecord('record_type')}
                >
                  {Object.entries(RECORD_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="field-label" htmlFor="fr_occurred">
                  Occurred at
                </label>
                <input
                  id="fr_occurred"
                  type="datetime-local"
                  className="field-input"
                  value={firstRecord.occurred_at}
                  onChange={updateFirstRecord('occurred_at')}
                />
              </div>

              <div>
                <label className="field-label" htmlFor="fr_visit_type">
                  Visit type
                </label>
                <select
                  id="fr_visit_type"
                  className="field-input"
                  value={firstRecord.visit_type}
                  onChange={updateFirstRecord('visit_type')}
                >
                  {Object.entries(VISIT_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="field-label" htmlFor="fr_visit_at">
                  Visit date
                </label>
                <input
                  id="fr_visit_at"
                  type="datetime-local"
                  className="field-input"
                  value={firstRecord.visit_at}
                  onChange={updateFirstRecord('visit_at')}
                />
              </div>

              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="fr_reason">
                  Reason for visit
                </label>
                <input
                  id="fr_reason"
                  className="field-input"
                  value={firstRecord.reason_for_visit}
                  onChange={updateFirstRecord('reason_for_visit')}
                />
              </div>
            </div>
          ) : null}
        </SectionCard>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || !canSubmit}
          >
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            {submitting ? 'Creating…' : 'Create pet'}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/pets')}
            disabled={submitting}
          >
            Cancel
          </button>
        </div>

        <Notice tone="info">
          New records start as <strong>unverified</strong>. The Digital Twin reports
          verified records as established history and keeps unverified ones
          retrievable but not presented as confirmed.
        </Notice>
      </form>
    </div>
  )
}
