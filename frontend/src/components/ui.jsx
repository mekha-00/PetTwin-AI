/**
 * Small presentational pieces shared across pages.
 *
 * Phase 3 deliberately has no AI output components. `StatusNote` exists to be
 * explicit about what is *not* implemented, so a placeholder is never
 * mistaken for a working feature.
 */
import { AlertCircle, Info, Loader2 } from 'lucide-react'

export function Spinner({ label = 'Loading' }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-soft" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  )
}

export function PageLoader({ label = 'Loading' }) {
  return (
    <div className="flex min-h-64 items-center justify-center p-8">
      <Spinner label={label} />
    </div>
  )
}

export function ErrorMessage({ children, onRetry }) {
  if (!children) return null
  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-stop/20 bg-stop-soft px-3 py-2 text-sm text-stop"
      role="alert"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="flex-1">{children}</div>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="font-semibold underline">
          Retry
        </button>
      ) : null}
    </div>
  )
}

export function Notice({ tone = 'info', children }) {
  const tones = {
    info: 'border-brand/20 bg-brand-soft text-brand-dark',
    good: 'border-good/20 bg-good-soft text-good',
    warn: 'border-warn/20 bg-warn-soft text-warn',
  }
  return (
    <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${tones[tone]}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="card flex flex-col items-center gap-2 p-8 text-center">
      {Icon ? <Icon className="h-8 w-8 text-ink-soft" aria-hidden="true" /> : null}
      <h3 className="text-base font-semibold">{title}</h3>
      {description ? <p className="max-w-md text-sm text-ink-soft">{description}</p> : null}
      {action}
    </div>
  )
}

const BADGE_TONES = {
  neutral: 'bg-canvas text-ink-soft',
  good: 'bg-good-soft text-good',
  warn: 'bg-warn-soft text-warn',
  stop: 'bg-stop-soft text-stop',
  brand: 'bg-brand-soft text-brand-dark',
}

export function Badge({ tone = 'neutral', children }) {
  return <span className={`badge ${BADGE_TONES[tone]}`}>{children}</span>
}

export function SectionCard({ title, description, actions, children }) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description ? <p className="mt-0.5 text-sm text-ink-soft">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}

/** Labelled value used in the profile and twin detail grids. */
export function DetailItem({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm break-words">{children ?? '—'}</dd>
    </div>
  )
}
