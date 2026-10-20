/**
 * Human-readable labels and helpers for API values.
 *
 * The backend sends enum values as lowercase snake_case strings
 * (`"patellar luxation"` style titles are built server-side; enums are
 * `wellness_exam`, `male`, `dog`). These helpers keep that translation in one
 * place instead of scattering string literals through the pages.
 */

export const SPECIES_LABELS = {
  dog: 'Dog',
  cat: 'Cat',
  horse: 'Horse',
  rabbit: 'Rabbit',
  bird: 'Bird',
  reptile: 'Reptile',
  small_mammal: 'Small mammal',
  other: 'Other',
}

export const SEX_LABELS = {
  male: 'Male',
  female: 'Female',
  unknown: 'Unknown',
}

export const RECORD_TYPE_LABELS = {
  consultation: 'Consultation',
  vaccination: 'Vaccination',
  lab_work: 'Lab work',
  treatment: 'Treatment',
  telehealth: 'Telehealth',
  surgery: 'Surgery',
  wellness_exam: 'Wellness exam',
  other: 'Other',
}

export const VISIT_TYPE_LABELS = {
  wellness: 'Wellness',
  sick: 'Sick',
  emergency: 'Emergency',
  follow_up: 'Follow-up',
  vaccination: 'Vaccination',
  surgery: 'Surgery',
}

export const VISIT_STATUS_LABELS = {
  scheduled: 'Scheduled',
  in_progress: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

export const DIAGNOSIS_STATUS_LABELS = {
  active: 'Active',
  resolved: 'Resolved',
  chronic: 'Chronic',
  ruled_out: 'Ruled out',
}

export const EVENT_TYPE_LABELS = {
  pet_registered: 'Pet registered',
  visit: 'Veterinary visit',
  diagnosis: 'Diagnosis',
  symptom: 'Symptom',
  medication_started: 'Medication started',
  medication_stopped: 'Medication stopped',
  vaccination: 'Vaccination',
  lab_result: 'Lab result',
  weight_change: 'Weight change',
  note: 'Note',
}

export const VACCINATION_STATUS_LABELS = {
  up_to_date: 'Up to date',
  overdue: 'Overdue',
  none_recorded: 'None recorded',
  recorded_no_due_date: 'Recorded, no due date',
}

/** "4 yr 2 mo" from the twin's age block, or a dash when unknown. */
export function formatAge(age) {
  if (!age) return 'Unknown'
  if (age.years === 0 && age.months === 0) return 'Under 1 month'
  const years = age.years > 0 ? `${age.years} yr` : null
  const months = age.months > 0 ? `${age.months} mo` : null
  const parts = [years, months].filter(Boolean).join(' ')
  return age.approximate ? `~${parts}` : parts
}

/**
 * Age for a pet in a list.
 *
 * `PetSummary` deliberately carries the raw `date_of_birth` /
 * `estimated_age_months` rather than a precomputed age, because an age stored on
 * the pet would silently drift as time passes. The list view therefore derives
 * it the same way the Digital Twin does, and marks an estimate with `~`.
 */
export function formatPetAge(pet) {
  if (pet.date_of_birth) {
    const birth = new Date(pet.date_of_birth)
    if (!Number.isNaN(birth.getTime())) {
      const now = new Date()
      let months =
        (now.getFullYear() - birth.getFullYear()) * 12 + (now.getMonth() - birth.getMonth())
      if (now.getDate() < birth.getDate()) months -= 1
      if (months < 0) months = 0
      return formatAge({
        years: Math.floor(months / 12),
        months: months % 12,
        approximate: false,
      })
    }
  }
  if (pet.estimated_age_months !== null && pet.estimated_age_months !== undefined) {
    return formatAge({
      years: Math.floor(pet.estimated_age_months / 12),
      months: pet.estimated_age_months % 12,
      approximate: true,
    })
  }
  return 'Unknown'
}

export function formatDate(value) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(value) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWeight(kg) {
  if (kg === null || kg === undefined) return '—'
  return `${Number(kg).toFixed(1)} kg`
}

export function titleCase(value) {
  if (!value) return '—'
  return String(value)
    .split(/[_\s-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function speciesLabel(value) {
  return SPECIES_LABELS[value] ?? titleCase(value)
}

export function sexLabel(value) {
  return SEX_LABELS[value] ?? titleCase(value)
}
