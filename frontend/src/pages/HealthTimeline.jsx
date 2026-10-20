import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarClock, ChevronLeft, ChevronRight, History } from 'lucide-react'

import { useAsyncData } from '../hooks/useAsyncData'
import { fetchHealthTimeline } from '../lib/endpoints'
import { EVENT_TYPE_LABELS, formatDateTime, titleCase } from '../lib/format'
import {
  Badge,
  EmptyState,
  ErrorMessage,
  Notice,
  PageLoader,
  SectionCard,
} from '../components/ui'

const PAGE_SIZE = 25

/**
 * Event-type styling.
 *
 * The colours group events by kind rather than by severity: red marks something
 * clinically notable (diagnosis, lab result), teal marks routine care (visit,
 * vaccination), and grey marks narrative notes. This is categorisation of record
 * *types*, not a judgement about the pet's health.
 */
const EVENT_TONE = {
  diagnosis: 'stop',
  symptom: 'warn',
  lab_result: 'stop',
  visit: 'brand',
  vaccination: 'good',
  medication_started: 'brand',
  medication_stopped: 'neutral',
  weight_change: 'neutral',
  pet_registered: 'neutral',
  note: 'neutral',
}

export default function HealthTimeline() {
  const { petId } = useParams()
  const [verifiedOnly, setVerifiedOnly] = useState(true)
  const [offset, setOffset] = useState(0)

  const { data, error, isLoading, reload } = useAsyncData(
    () => fetchHealthTimeline(petId, { verified_only: verifiedOnly, limit: PAGE_SIZE, offset }),
    [petId, verifiedOnly, offset],
  )

  function changeFilter(next) {
    setVerifiedOnly(next)
    setOffset(0)
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + items.length, total)

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link to={`/pets/${petId}`} className="text-sm text-ink-soft hover:underline">
          <ArrowLeft className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          Back to pet
        </Link>
        <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold">
          <History className="h-6 w-6 text-brand" aria-hidden="true" />
          Health timeline
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Every recorded event for this pet, newest first. Derived from the records on
          each request, so it cannot fall out of step with them.
        </p>
      </header>

      <ErrorMessage onRetry={reload}>{error}</ErrorMessage>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={!verifiedOnly}
            onChange={(event) => changeFilter(!event.target.checked)}
          />
          Include unverified entries
        </label>
        {data ? (
          <span className="text-sm text-ink-soft">
            {total === 0
              ? 'No events'
              : `Showing ${from}–${to} of ${total}`}
          </span>
        ) : null}
      </div>

      {isLoading ? (
        <PageLoader label="Building timeline" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title={verifiedOnly ? 'No verified events yet' : 'No events recorded'}
          description={
            verifiedOnly
              ? 'Only records a veterinarian has confirmed are shown here. Turn on "Include unverified entries" to see everything entered so far.'
              : 'Add health records on the pet page and they will appear here automatically.'
          }
        />
      ) : (
        <SectionCard title="Events" description="Newest first.">
          <ol className="relative flex flex-col gap-0">
            {items.map((item, index) => (
              <li key={`${item.source_table}-${item.source_id}-${index}`} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span
                    className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                      EVENT_TONE[item.event_type] === 'stop'
                        ? 'bg-stop'
                        : EVENT_TONE[item.event_type] === 'good'
                          ? 'bg-good'
                          : EVENT_TONE[item.event_type] === 'warn'
                            ? 'bg-warn'
                            : EVENT_TONE[item.event_type] === 'brand'
                              ? 'bg-brand'
                              : 'bg-ink-soft'
                    }`}
                    aria-hidden="true"
                  />
                  {index < items.length - 1 ? (
                    <span className="w-px flex-1 bg-line" aria-hidden="true" />
                  ) : null}
                </div>

                <div className="min-w-0 flex-1 pb-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{item.title}</p>
                    <Badge tone={EVENT_TONE[item.event_type] ?? 'neutral'}>
                      {EVENT_TYPE_LABELS[item.event_type] ?? titleCase(item.event_type)}
                    </Badge>
                  </div>
                  <p className="text-sm text-ink-soft">
                    {formatDateTime(item.occurred_at)}
                    {item.severity ? ` · severity ${item.severity}` : ''}
                  </p>
                  {item.description ? (
                    <p className="mt-1 text-sm">{item.description}</p>
                  ) : null}
                  <p className="mt-0.5 text-xs text-ink-soft">
                    source: {titleCase(item.source_table)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </SectionCard>
      )}

      {total > PAGE_SIZE ? (
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            Newer
          </button>
          <span className="text-sm text-ink-soft">
            Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.ceil(total / PAGE_SIZE)}
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={to >= total}
          >
            Older
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ) : null}

      <Notice tone="info">
        Owner notes and other narrative entries carry no verification flag, so they
        only appear when &ldquo;Include unverified entries&rdquo; is on. Nothing is
        deleted either way — the toggle changes the filter, not the data.
      </Notice>
    </div>
  )
}
