import { Link } from 'react-router-dom'
import { Activity, PawPrint, PlusCircle, Syringe } from 'lucide-react'

import { useAuth } from '../context/authContext'
import { useAsyncData } from '../hooks/useAsyncData'
import { listPets } from '../lib/endpoints'
import { formatPetAge, formatWeight, sexLabel, speciesLabel } from '../lib/format'
import {
  Badge,
  EmptyState,
  ErrorMessage,
  PageLoader,
  SectionCard,
} from '../components/ui'

function PetRow({ pet }) {
  return (
    <li>
      <Link
        to={`/pets/${pet.id}`}
        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-4 transition-colors hover:bg-canvas"
      >
        <div className="min-w-0">
          <p className="font-semibold">{pet.name}</p>
          <p className="text-sm text-ink-soft">
            {speciesLabel(pet.species)}
            {pet.breed ? ` · ${pet.breed}` : ''} · {sexLabel(pet.sex)}
          </p>
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <div>
            <dt className="text-xs text-ink-soft">Age</dt>
            <dd>{formatPetAge(pet)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-soft">Weight</dt>
            <dd>{formatWeight(pet.current_weight_kg)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-soft">Records</dt>
            <dd>{pet.health_record_count}</dd>
          </div>
          {pet.viewer_role ? (
            <div>
              <dt className="text-xs text-ink-soft">Access</dt>
              <dd>
                <Badge tone="brand">{pet.viewer_role}</Badge>
              </dd>
            </div>
          ) : null}
        </dl>
      </Link>
    </li>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, isLoading, reload } = useAsyncData(() => listPets(), [])

  if (isLoading) return <PageLoader label="Loading your pets" />

  const pets = data ?? []
  const totalRecords = pets.reduce((sum, pet) => sum + (pet.health_record_count || 0), 0)
  const totalVisits = pets.reduce((sum, pet) => sum + (pet.visit_count || 0), 0)
  const greeting = user?.full_name ? user.full_name.split(' ')[0] : null

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold">
          {greeting ? `Welcome back, ${greeting}` : 'Dashboard'}
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Your pets and their software-based Digital Twin records.
        </p>
      </header>

      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card p-4">
          <p className="flex items-center gap-2 text-xs font-semibold tracking-wide text-ink-soft uppercase">
            <PawPrint className="h-3.5 w-3.5" aria-hidden="true" />
            Pets
          </p>
          <p className="mt-1 text-2xl font-semibold">{pets.length}</p>
        </div>
        <div className="card p-4">
          <p className="flex items-center gap-2 text-xs font-semibold tracking-wide text-ink-soft uppercase">
            <Syringe className="h-3.5 w-3.5" aria-hidden="true" />
            Health records
          </p>
          <p className="mt-1 text-2xl font-semibold">{totalRecords}</p>
        </div>
        <div className="card p-4">
          <p className="flex items-center gap-2 text-xs font-semibold tracking-wide text-ink-soft uppercase">
            <Activity className="h-3.5 w-3.5" aria-hidden="true" />
            Vet visits
          </p>
          <p className="mt-1 text-2xl font-semibold">{totalVisits}</p>
        </div>
      </div>

      <SectionCard
        title="My pets"
        description="Open a pet to see its full record set and Digital Twin."
        actions={
          <Link to="/pets/new" className="btn btn-primary">
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            Add pet
          </Link>
        }
      >
        {pets.length === 0 ? (
          <EmptyState
            icon={PawPrint}
            title="No pets yet"
            description="Add your first pet to start building its health record and Digital Twin."
            action={
              <Link to="/pets/new" className="btn btn-primary mt-2">
                <PlusCircle className="h-4 w-4" aria-hidden="true" />
                Add pet
              </Link>
            }
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {pets.map((pet) => (
              <PetRow key={pet.id} pet={pet} />
            ))}
          </ul>
        )}
      </SectionCard>


    </div>
  )
}
