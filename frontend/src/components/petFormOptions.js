/**
 * Select options shared by the pet form and the pet editor.
 *
 * These are declared here rather than inline so the add and edit forms cannot
 * drift apart, and so the values can be checked against the backend enums
 * (`app.models.base.Species` and `Sex`) in one place.
 */
import { SPECIES_LABELS, SEX_LABELS } from '../lib/format'

export const SPECIES_OPTIONS = Object.entries(SPECIES_LABELS).map(([value, label]) => ({
  value,
  label,
}))

export const SEX_OPTIONS = Object.entries(SEX_LABELS).map(([value, label]) => ({
  value,
  label,
}))
