import { Link } from 'react-router-dom'
import { Stethoscope } from 'lucide-react'

import { useAsyncData } from '../hooks/useAsyncData'
import { listPets } from '../lib/endpoints'
import { formatPetAge, formatWeight, sexLabel, speciesLabel } from '../lib/format'
import { Badge, EmptyState, ErrorMessage, Notice, PageLoader } from '../components/ui'

/**
 * A veterinarian's patient list.
 *
 * There is no separate "patients" endpoint: `GET /pets` already returns every
 * pet the caller holds an active grant for, tagged with their role. A vet's
 * patients are simply the pets shared with them, so this page filters that list
 * to exclude anything the vet owns themselves.
 */
function PatientCard({ pet }) {
  return (
    <li className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold">{pet.name}</h3>
          <p className="text-sm text-ink-soft">
            {speciesLabel(pet.species)}
            {pet.breed ? ` · ${pet.breed}` : ''} · {sexLabel(pet.sex)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="brand">{pet.viewer_role}</Badge>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-ink-soft">Age</dt>
          <dd>{formatPetAge(pet)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-soft">Weight</dt>
          <dd>{formatWeight(pet.current_weight_kg)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-soft">Health records</dt>
          <dd>{pet.health_record_count}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-soft">Visits</dt>
          <dd>{pet.visit_count}</dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link to={`/pets/${pet.id}`} className="btn btn-primary">
          Open record
        </Link>
        <Link to={`/pets/${pet.id}/digital-twin`} className="btn btn-secondary">
          Digital Twin
        </Link>
        <Link to={`/pets/${pet.id}/timeline`} className="btn btn-secondary">
          Timeline
        </Link>
      </div>
    </li>
  )
}

export default function Patients() {
  const { data, error, isLoading, reload } = useAsyncData(() => listPets(), [])

  if (isLoading) return <PageLoader label="Loading your patients" />

  const pets = data ?? []
  const patients = pets.filter((pet) => pet.viewer_role !== 'owner')

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <Stethoscope className="h-6 w-6 text-brand" aria-hidden="true" />
          My patients
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Pets whose owners have shared access with you. You can review their
          history, the Digital Twin, and add clinical records.
        </p>
      </header>

      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      {patients.length === 0 ? (
        <EmptyState
          icon={Stethoscope}
          title="No patients yet"
          description="When a pet owner shares a pet with your account, it will appear here."
        />
      ) : (
        <ul className="flex flex-col gap-4">
          {patients.map((pet) => (
            <PatientCard key={pet.id} pet={pet} />
          ))}
        </ul>
      )}

      <Notice tone="info">
        You can add records to a shared patient, but only the owner can edit the
        pet profile, remove the pet, or erase its history.
      </Notice>
    </div>
  )
}
