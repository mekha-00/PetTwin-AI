import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { LogIn } from 'lucide-react'

import { useAuth } from '../../context/authContext'
import { describeError } from '../../lib/api'
import { ErrorMessage } from '../../components/ui'
import AuthShell, { AuthLink } from './AuthShell'

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signIn({ email: email.trim(), password })
      // Return the user to whatever page sent them here.
      navigate(location.state?.from || '/', { replace: true })
    } catch (err) {
      // The backend returns one message for both an unknown email and a wrong
      // password, so nothing here reveals whether the account exists.
      setError(describeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Access your pets and their Digital Twin records."
      footer={
        <>
          No account yet? <AuthLink to="/register">Create one</AuthLink>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <ErrorMessage>{error}</ErrorMessage>

        <div>
          <label className="field-label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            className="field-input"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div>
          <label className="field-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="field-input"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={submitting}>
          <LogIn className="h-4 w-4" aria-hidden="true" />
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthShell>
  )
}
