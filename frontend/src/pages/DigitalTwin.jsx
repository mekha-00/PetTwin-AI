import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Activity,
  ArrowLeft,
  Bug,
  CircleDot,
  History,
  Pill,
  Search,
  ShieldAlert,
  Sparkles,
  Syringe,
  TestTube2,
  TriangleAlert,
  Waves,
} from 'lucide-react'

import { useAsyncData } from '../hooks/useAsyncData'
import { fetchDigitalTwin, fetchSimilarCases, fetchSymptomOptions, predictConditions } from '../lib/endpoints'
import {
  DIAGNOSIS_STATUS_LABELS,
  formatAge,
  formatDate,
  formatDateTime,
  formatWeight,
  sexLabel,
  speciesLabel,
  titleCase,
  VACCINATION_STATUS_LABELS,
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

const VACCINATION_TONE = {
  up_to_date: 'good',
  overdue: 'stop',
  recorded_no_due_date: 'warn',
  none_recorded: 'neutral',
}

const CONDITION_TONE = {
  active: 'stop',
  chronic: 'warn',
  resolved: 'good',
  ruled_out: 'neutral',
}

/** Compact list used for the several "possibly empty" status sections. */
function StatusList({ icon: Icon, items, emptyText, render }) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-soft">{emptyText}</p>
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
        >
          <div className="flex min-w-0 items-start gap-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden="true" />
            {render(item)}
          </div>
        </li>
      ))}
    </ul>
  )
}

function VaccinationStatus({ status }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={VACCINATION_TONE[status.status] ?? 'neutral'}>
          {VACCINATION_STATUS_LABELS[status.status] ?? titleCase(status.status)}
        </Badge>
        <span className="text-sm text-ink-soft">
          {status.vaccines_tracked} vaccine{status.vaccines_tracked === 1 ? '' : 's'}{' '}
          tracked
        </span>
      </div>

      {status.overdue.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            Overdue
          </p>
          <ul className="mt-1 flex flex-col gap-1">
            {status.overdue.map((item) => (
              <li key={item.vaccine} className="text-sm">
                <span className="font-medium">{item.vaccine}</span>{' '}
                <span className="text-ink-soft">
                  given {formatDate(item.last_given)}, due{' '}
                  {formatDate(item.next_due)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {status.upcoming.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            Upcoming
          </p>
          <ul className="mt-1 flex flex-col gap-1">
            {status.upcoming.map((item) => (
              <li key={item.vaccine} className="text-sm">
                <span className="font-medium">{item.vaccine}</span>{' '}
                <span className="text-ink-soft">due {formatDate(item.next_due)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

/** Candidate conditions ranked from similar recorded cases. Evidence, not a
 * probability and not a diagnosis. */
function ConditionPredictionSection({ petId }) {
  const [options, setOptions] = useState(null)
  const [optionsError, setOptionsError] = useState(null)
  const [selected, setSelected] = useState([])
  const [species, setSpecies] = useState('')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState(null)

  // Load the vocabulary and this pet's twin-derived defaults once.
  useEffect(() => {
    let cancelled = false
    fetchSymptomOptions(petId)
      .then((data) => {
        if (cancelled) return
        setOptions(data)
        setSelected(data.default_symptoms ?? [])
        setSpecies(data.default_species ?? '')
      })
      .catch((err) => {
        if (!cancelled) setOptionsError(err?.message ?? 'Options unavailable.')
      })
    return () => {
      cancelled = true
    }
  }, [petId])

  const toggle = useCallback((label) => {
    setSelected((prev) =>
      prev.includes(label) ? prev.filter((s) => s !== label) : [...prev, label],
    )
  }, [])

  const run = useCallback(async () => {
    setRunning(true)
    setRunError(null)
    try {
      const data = await predictConditions(petId, {
        symptoms: selected,
        species: species || undefined,
      })
      setResult(data)
    } catch (err) {
      setRunError(err?.message ?? 'Prediction unavailable.')
    } finally {
      setRunning(false)
    }
  }, [petId, selected, species])

  const candidates = result?.candidates ?? []

  return (
    <SectionCard
      title="Possible conditions from recorded cases"
      description="Ranked by how many recorded cases with similar symptoms carried each diagnosis. This is evidence from a small external dataset — not a probability and not a diagnosis."
    >
      {optionsError ? (
        <p className="text-sm text-ink-soft">Symptom options are unavailable right now.</p>
      ) : !options ? (
        <p className="text-sm text-ink-soft">Loading symptom options…</p>
      ) : (
        <>
          <p className="mb-2 text-sm text-ink-soft">
            Prefilled from this pet&rsquo;s recorded symptoms. Adjust and re-run to explore.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {options.vocabulary.map((label) => {
              const active = selected.includes(label)
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => toggle(label)}
                  className={
                    active
                      ? 'rounded-full border border-brand bg-brand/10 px-3 py-1 text-xs font-medium text-brand'
                      : 'rounded-full border border-line px-3 py-1 text-xs text-ink-soft hover:border-brand'
                  }
                  aria-pressed={active}
                >
                  {label}
                </button>
              )
            })}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="text-sm text-ink-soft">
              {selected.length} symptom{selected.length === 1 ? '' : 's'} selected
              {species ? ` · species ${species}` : ''}
            </span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={run}
              disabled={running || selected.length === 0}
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {running ? 'Ranking…' : 'Rank possible conditions'}
            </button>
          </div>

          {selected.length === 0 ? (
            <p className="mt-3 text-sm text-ink-soft">
              Select at least one symptom to rank possible conditions.
            </p>
          ) : null}

          {runError ? <p className="mt-3 text-sm text-red-600">{runError}</p> : null}

          {result ? (
            <div className="mt-4">
              {candidates.length === 0 ? (
                <p className="text-sm text-ink-soft">
                  No recorded cases matched these symptoms closely enough.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {candidates.map((item) => (
                    <li
                      key={item.disease}
                      className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
                    >
                      <div className="flex min-w-0 items-start gap-2">
                        <Search
                          className="mt-0.5 h-4 w-4 shrink-0 text-ink-soft"
                          aria-hidden="true"
                        />
                        <div>
                          <p className="font-medium">{item.disease}</p>
                          <p className="text-sm text-ink-soft">
                            {item.case_count} similar recorded case
                            {item.case_count === 1 ? '' : 's'} carried this diagnosis
                          </p>
                          {item.supporting_symptoms?.length > 0 ? (
                            <p className="text-sm text-ink-soft">
                              shared symptoms: {item.supporting_symptoms.join(', ')}
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <Badge tone="neutral">
                        avg resemblance {Math.round(item.avg_similarity * 100)}%
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-ink-soft">
                Drawn from {result.corpus_size} recorded cases. {result.disclaimer}
              </p>
            </div>
          ) : null}
        </>
      )}
    </SectionCard>
  )
}

/** Recorded cases that resemble this pet. Retrieval, not a prediction. */
function SimilarCasesSection({ petId, hasSymptoms }) {
  const { data, error, isLoading } = useAsyncData(
    () => fetchSimilarCases(petId),
    [petId],
  )

  const cases = data?.cases ?? []

  return (
    <SectionCard
      title="Similar recorded cases"
      description="Cases from a small external dataset that resemble this pet's features. This is retrieval, not a diagnosis — similar symptoms do not mean the same disease."
    >
      {isLoading ? (
        <p className="text-sm text-ink-soft">Searching recorded cases…</p>
      ) : error ? (
        <p className="text-sm text-ink-soft">
          Similar cases are unavailable right now.
        </p>
      ) : cases.length === 0 ? (
        <p className="text-sm text-ink-soft">
          {hasSymptoms
            ? 'No recorded cases matched this pet closely enough.'
            : 'Record some current symptoms to search for similar cases.'}
        </p>
      ) : (
        <>
          {data.query_symptoms?.length > 0 ? (
            <p className="mb-3 text-sm text-ink-soft">
              Matched on:{' '}
              {data.query_symptoms.map((name, index) => (
                <span key={name}>
                  {index > 0 ? ', ' : ''}
                  <span className="text-ink">{name}</span>
                </span>
              ))}
            </p>
          ) : null}
          <ul className="flex flex-col gap-2">
            {cases.map((item, index) => (
              <li
                key={`${item.disease}-${index}`}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
              >
                <div className="flex min-w-0 items-start gap-2">
                  <Search className="mt-0.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden="true" />
                  <div>
                    <p className="font-medium">{item.disease}</p>
                    <p className="text-sm text-ink-soft">
                      {[speciesLabel(item.animal_type), item.breed, item.gender]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    {item.symptoms?.length > 0 ? (
                      <p className="text-sm text-ink-soft">
                        recorded symptoms: {item.symptoms.join(', ')}
                      </p>
                    ) : null}
                  </div>
                </div>
                <Badge tone="neutral">
                  {Math.round(item.similarity * 100)}% similar
                </Badge>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-soft">
            Drawn from {data.corpus_size} recorded cases. {data.disclaimer}
          </p>
        </>
      )}
    </SectionCard>
  )
}

export default function DigitalTwin() {
  const { petId } = useParams()
  const { data: twin, error, isLoading, reload } = useAsyncData(
    () => fetchDigitalTwin(petId),
    [petId],
  )

  if (isLoading) return <PageLoader label="Assembling Digital Twin" />
  if (error || !twin) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorMessage onRetry={reload}>{error ?? 'Digital Twin unavailable.'}</ErrorMessage>
        <Link to="/pets" className="btn btn-secondary">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to my pets
        </Link>
      </div>
    )
  }

  const { profile, current_health_status: status, provenance } = twin
  const hasAnything =
    status.existing_conditions.length > 0 ||
    status.current_symptoms.length > 0 ||
    status.current_medications.length > 0 ||
    status.allergies.length > 0 ||
    twin.vaccinations.length > 0 ||
    twin.medical_history.length > 0

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link to={`/pets/${twin.pet_id}`} className="text-sm text-ink-soft hover:underline">
          <ArrowLeft className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          {profile.name}
        </Link>
        <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold">
          <Activity className="h-6 w-6 text-brand" aria-hidden="true" />
          {profile.name}&rsquo;s Digital Twin
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Assembled {formatDateTime(twin.generated_at)} from recorded veterinary
          information. Software-based, not sensor-based.
        </p>
      </header>

      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      <Notice tone="warn">
        <span className="flex items-start gap-2">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{twin.disclaimer}</span>
        </span>
      </Notice>

      <SectionCard
        title="Profile"
        description="Identity fields, held on the pet record itself."
      >
        <dl className="grid gap-4 sm:grid-cols-4">
          <DetailItem label="Species">{speciesLabel(profile.species)}</DetailItem>
          <DetailItem label="Breed">{profile.breed}</DetailItem>
          <DetailItem label="Sex">
            {sexLabel(profile.sex)}
            {profile.is_neutered ? ' · neutered' : ''}
          </DetailItem>
          <DetailItem label="Age">{formatAge(profile.age)}</DetailItem>
          <DetailItem label="Date of birth">{formatDate(profile.date_of_birth)}</DetailItem>
          <DetailItem label="Weight">{formatWeight(profile.current_weight_kg)}</DetailItem>
          <DetailItem label="Microchip">{profile.microchip_id}</DetailItem>
          <DetailItem label="Last visit">
            {status.last_visit_at ? formatDate(status.last_visit_at) : 'None verified'}
          </DetailItem>
        </dl>
      </SectionCard>

      {!hasAnything ? (
        <EmptyState
          icon={Activity}
          title="No verified health records yet"
          description={`Once records for ${profile.name} are marked verified, this page fills in automatically. Unverified entries stay off the twin by design.`}
          action={
            <Link to={`/pets/${twin.pet_id}`} className="btn btn-primary mt-2">
              Add health records
            </Link>
          }
        />
      ) : null}

      <SectionCard
        title="Existing conditions"
        description="Diagnoses recorded as ongoing."
      >
        <StatusList
          icon={CircleDot}
          items={status.existing_conditions}
          emptyText="No ongoing conditions recorded."
          render={(condition) => (
            <>
              <div>
                <p className="font-medium">{condition.name}</p>
                <p className="text-sm text-ink-soft">
                  diagnosed {formatDate(condition.diagnosed_at)}
                  {condition.icd10_code ? ` · ${condition.icd10_code}` : ''}
                </p>
              </div>
              <div className="flex gap-1.5">
                <Badge tone={CONDITION_TONE[condition.status] ?? 'neutral'}>
                  {DIAGNOSIS_STATUS_LABELS[condition.status] ?? titleCase(condition.status)}
                </Badge>
                {condition.is_confirmed ? <Badge tone="good">confirmed</Badge> : null}
              </div>
            </>
          )}
        />
      </SectionCard>

      <SectionCard title="Current symptoms" description="Unresolved symptoms.">
        <StatusList
          icon={Waves}
          items={status.current_symptoms}
          emptyText="No current symptoms recorded."
          render={(symptom) => (
            <div>
              <p className="font-medium">{symptom.name}</p>
              <p className="text-sm text-ink-soft">
                onset {symptom.onset_at ? formatDate(symptom.onset_at) : 'unknown'}
                {symptom.severity ? ` · severity ${symptom.severity}` : ''}
                {symptom.is_chronic ? ' · chronic' : ''}
              </p>
            </div>
          )}
        />
      </SectionCard>

      <ConditionPredictionSection petId={twin.pet_id} />

      <SimilarCasesSection
        petId={twin.pet_id}
        hasSymptoms={status.current_symptoms.length > 0}
      />

      <SectionCard
        title="Current medications"
        description="Medications still running."
      >
        <StatusList
          icon={Pill}
          items={status.current_medications}
          emptyText="No active medications recorded."
          render={(medication) => (
            <div>
              <p className="font-medium">{medication.name}</p>
              <p className="text-sm text-ink-soft">
                {[medication.dose, medication.route, medication.frequency]
                  .filter(Boolean)
                  .join(' · ') || 'No dosing detail recorded'}
              </p>
              <p className="text-sm text-ink-soft">
                started {formatDate(medication.started_at)}
              </p>
            </div>
          )}
        />
      </SectionCard>

      <SectionCard
        title="Allergies"
        description="Verified, active sensitivities."
      >
        <StatusList
          icon={Bug}
          items={status.allergies}
          emptyText="No verified active allergies."
          render={(allergy) => (
            <div>
              <p className="font-medium">{allergy.allergen}</p>
              <p className="text-sm text-ink-soft">
                {[allergy.reaction, allergy.severity ? `severity ${allergy.severity}` : null]
                  .filter(Boolean)
                  .join(' · ') || 'No reaction described'}
              </p>
            </div>
          )}
        />
      </SectionCard>

      <SectionCard
        title="Vaccination status"
        description="Derived by comparing each vaccine's latest dose against its stored due date. Not a clinical judgement."
      >
        <VaccinationStatus status={status.vaccination_status} />
      </SectionCard>

      {twin.laboratory_results.length > 0 ? (
        <SectionCard title="Laboratory results" description="Verified results only.">
          <ul className="flex flex-col gap-2">
            {twin.laboratory_results.map((lab) => (
              <li
                key={lab.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
              >
                <div className="flex min-w-0 items-start gap-2">
                  <TestTube2 className="mt-0.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden="true" />
                  <div>
                    <p className="font-medium">{lab.test_name}</p>
                    <p className="text-sm text-ink-soft">
                      {lab.result || 'No value recorded'} ·{' '}
                      {formatDate(lab.performed_at)}
                    </p>
                  </div>
                </div>
                {lab.is_abnormal === true ? <Badge tone="warn">abnormal</Badge> : null}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Verified medical history"
        description="Latest verified health records, newest first."
        actions={
          <Link to={`/pets/${twin.pet_id}/timeline`} className="btn btn-secondary">
            <History className="h-4 w-4" aria-hidden="true" />
            Full timeline
          </Link>
        }
      >
        {twin.medical_history.length === 0 ? (
          <p className="text-sm text-ink-soft">No verified health records yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {twin.medical_history.map((record) => (
              <li
                key={record.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-line px-3 py-2"
              >
                <div>
                  <p className="font-medium">{record.title}</p>
                  <p className="text-sm text-ink-soft">
                    {titleCase(record.record_type)} · {formatDateTime(record.occurred_at)}
                    {record.clinic_name ? ` · ${record.clinic_name}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard
        title="Recent vaccinations"
        description="Verified doses, newest first."
      >
        <StatusList
          icon={Syringe}
          items={twin.vaccinations}
          emptyText="No verified vaccinations recorded."
          render={(vaccination) => (
            <div>
              <p className="font-medium">{vaccination.vaccine}</p>
              <p className="text-sm text-ink-soft">
                given {formatDate(vaccination.administered_at)}
                {vaccination.next_due_at
                  ? ` · next due ${formatDate(vaccination.next_due_at)}`
                  : ' · no due date'}
                {vaccination.is_booster ? ' · booster' : ''}
              </p>
            </div>
          )}
        />
      </SectionCard>

      <SectionCard
        title="Data provenance"
        description="How much of the record set is verified. Shown so the twin's limits are visible rather than implied."
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="py-2 font-semibold">Record type</th>
              <th className="py-2 text-right font-semibold">Verified</th>
              <th className="py-2 text-right font-semibold">Total</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(provenance.total_counts).map((key) => {
              const verified = provenance.verified_counts[key] ?? 0
              const total = provenance.total_counts[key]
              return (
                <tr key={key} className="border-b border-line last:border-0">
                  <td className="py-2">{titleCase(key)}</td>
                  <td className="py-2 text-right">
                    <Badge tone={verified === total ? 'good' : 'warn'}>{verified}</Badge>
                  </td>
                  <td className="py-2 text-right text-ink-soft">{total}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-ink-soft">
          Excluded source types: {provenance.excluded_source_types.join(', ') || 'none'}.
          Your role for this pet: {twin.viewer_role ?? 'none'}.
        </p>
      </SectionCard>

      <Notice tone="info">
        <span className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            Unverified records are excluded from every section above. They are still
            visible on {profile.name}&rsquo;s{' '}
            <Link to={`/pets/${twin.pet_id}`} className="font-semibold underline">
              record page
            </Link>{' '}
            and on the{' '}
            <Link to={`/pets/${twin.pet_id}/timeline`} className="font-semibold underline">
              full timeline
            </Link>
            .
          </span>
        </span>
      </Notice>

      <div>
        <Link to={`/pets/${twin.pet_id}`} className="btn btn-secondary">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to {profile.name}
        </Link>
      </div>
    </div>
  )
}
