import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="card max-w-md p-8 text-center">
        <Compass className="mx-auto h-10 w-10 text-ink-soft" aria-hidden="true" />
        <h1 className="mt-3 text-xl font-semibold">Page not found</h1>
        <p className="mt-2 text-sm text-ink-soft">
          That address does not match any screen in this app.
        </p>
        <Link to="/" className="btn btn-primary mt-6">
          Go to dashboard
        </Link>
      </div>
    </div>
  )
}
