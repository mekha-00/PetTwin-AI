import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Archive, PawPrint, PlusCircle, Trash2 } from 'lucide-react'

import { useAsyncData } from '../hooks/useAsyncData'
import { listPets, purgePet, softDeletePet } from '../lib/endpoints'
import { describeError } from '../lib/api'
import { formatPetAge, formatWeight, sexLabel, speciesLabel } from '../lib/format'
import {
  Badge,
  EmptyState,
  ErrorMessage,
  Notice,
  PageLoader,
} from '../components/ui'

/**
 * Two deletion modes are offered deliberately.
 *
 * "Remove" is a soft delete: the pet leaves the list and access is revoked, but
 * the clinical history is retained. "Erase permanently" destroys that history
 * and cannot be undone, so it asks for confirmation by name.
 */
function DeleteControls({ pet, onChanged }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSoftDelete() {
    setBusy(true)
    setError(null)
    try {
      await softDeletePet(pet.id)
      onChanged()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handlePurge() {
    setBusy(true)
    setError(null)
    try {
      await purgePet(pet.id)
      onChanged()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  if (confirming) {
    return (
      <div className="w-full rounded-lg border border-stop/30 bg-stop-soft p-3">
        <p className="text-sm text-stop">
          Erase <strong>{pet.name}</strong> and every health record permanently? This
          cannot be undone.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-danger"
            onClick={handlePurge}
            disabled={busy}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {busy ? 'Erasing…' : 'Yes, erase everything'}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setConfirming(false)}
            disabled={busy}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ErrorMessage>{error}</ErrorMessage>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={handleSoftDelete}
        disabled={busy}
        title="Keeps the health history, removes the pet from your list"
      >
        <Archive className="h-4 w-4" aria-hidden="true" />
        Remove
      </button>
      <button
        type="button"
        className="btn btn-secondary text-stop"
        onClick={() => setConfirming(true)}
        disabled={busy}
        title="Permanently deletes the pet and all clinical records"
      >
        <Trash2 className="h-4 w-4" aria-hidden="true" />
        Erase permanently
      </button>
    </div>
  )
}

function PetCard({ pet, onChanged }) {
  return (
    <li className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold">{pet.name}</h3>
          <p className="text-sm text-ink-soft">
            {speciesLabel(pet.species)}
            {pet.breed ? ` · ${pet.breed}` : ''} · {sexLabel(pet.sex)}
            {pet.is_neutered ? ' · neutered' : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {pet.viewer_role ? <Badge tone="brand">{pet.viewer_role}</Badge> : null}
          {!pet.is_alive ? <Badge tone="stop">inactive</Badge> : null}
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
          <dt className="text-xs text-ink-soft">Vet visits</dt>
          <dd>{pet.visit_count}</dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link to={`/pets/${pet.id}`} className="btn btn-primary">
          Open
        </Link>
        <Link to={`/pets/${pet.id}/digital-twin`} className="btn btn-secondary">
          Digital Twin
        </Link>
        <DeleteControls pet={pet} onChanged={onChanged} />
      </div>
    </li>
  )
}

export default function MyPets() {
  const [showInactive, setShowInactive] = useState(false)
  const { data, error, isLoading, reload } = useAsyncData(
    () => listPets({ includeDeceased: showInactive }),
    [showInactive],
  )

  if (isLoading) return <PageLoader label="Loading your pets" />

  const pets = data ?? []

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">My pets</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Every pet you own or have been given access to.
          </p>
        </div>
        <Link to="/pets/new" className="btn btn-primary">
          <PlusCircle className="h-4 w-4" aria-hidden="true" />
          Add pet
        </Link>
      </header>

      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      <label className="flex items-center gap-2 text-sm text-ink-soft">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(event) => setShowInactive(event.target.checked)}
        />
        Show removed pets
      </label>

      {pets.length === 0 ? (
        <EmptyState
          icon={PawPrint}
          title={showInactive ? 'No pets' : 'No active pets'}
          description={
            showInactive
              ? 'You do not have any pets yet, active or removed.'
              : 'Add a pet to begin recording its health history and Digital Twin.'
          }
          action={
            <Link to="/pets/new" className="btn btn-primary mt-2">
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              Add pet
            </Link>
          }
        />
      ) : (
        <ul className="flex flex-col gap-4">
          {pets.map((pet) => (
            <PetCard key={pet.id} pet={pet} onChanged={reload} />
          ))}
        </ul>
      )}

      <Notice tone="warn">
        &ldquo;Remove&rdquo; hides the pet and revokes access but keeps its medical
        history. &ldquo;Erase permanently&rdquo; deletes the pet and every record
        attached to it, and cannot be undone.
      </Notice>
    </div>
  )
}
