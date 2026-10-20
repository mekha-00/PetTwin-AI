/**
 * Shared markup for the two unauthenticated screens.
 */
import { PawPrint } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2">
          <PawPrint className="h-6 w-6 text-brand" aria-hidden="true" />
          <span className="text-lg font-semibold">PetTwin AI</span>
          <span className="badge bg-surface text-ink-soft">Phase 3</span>
        </div>

        <div className="card p-6">
          <h1 className="text-xl font-semibold">{title}</h1>
          {subtitle ? <p className="mt-1 text-sm text-ink-soft">{subtitle}</p> : null}
          <div className="mt-6">{children}</div>
        </div>

        {footer ? <div className="mt-4 text-center text-sm text-ink-soft">{footer}</div> : null}

        <p className="mt-8 text-center text-xs leading-relaxed text-ink-soft">
          PetTwin AI is assistive software. It does not diagnose or prescribe, and no
          AI analysis is available in this phase.
        </p>
      </div>
    </div>
  )
}

export function AuthLink({ to, children }) {
  return (
    <Link to={to} className="font-semibold text-brand hover:underline">
      {children}
    </Link>
  )
}
