import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus } from 'lucide-react'

import { useAuth } from '../../context/authContext'
import { describeError } from '../../lib/api'
import { ErrorMessage, Notice } from '../../components/ui'
import AuthShell, { AuthLink } from './AuthShell'

/**
 * Matches the backend's rule: bcrypt ignores anything past 72 bytes, so the API
 * rejects longer passwords. The hint says so rather than letting a user
 * discover it as a validation error after filling the whole form.
 */
const MIN_PASSWORD_LENGTH = 8
const MAX_PASSWORD_BYTES = 72

export default function Register() {
  const { signUp } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'pet_owner',
    clinic_name: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const passwordBytes = new TextEncoder().encode(form.password).length
  const tooLong = passwordBytes > MAX_PASSWORD_BYTES
  const tooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD_LENGTH

  function update(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signUp({
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim() || undefined,
        role: form.role,
        clinic_name: form.role === 'veterinarian' ? form.clinic_name.trim() || undefined : undefined,
      })
      navigate('/', { replace: true })
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit =
    form.email.trim().length > 0 && form.password.length >= MIN_PASSWORD_LENGTH && !tooLong

  return (
    <AuthShell
      title="Create your account"
      subtitle="Only an email address and a password are required. No personal details are collected."
      footer={
        <>
          Already registered? <AuthLink to="/login">Sign in</AuthLink>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <ErrorMessage>{error}</ErrorMessage>

        <fieldset>
          <legend className="field-label">I am signing up as</legend>
          <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[
              {
                value: 'pet_owner',
                label: 'Pet parent',
                hint: 'Track your own pets and their health records.',
              },
              {
                value: 'veterinarian',
                label: 'Veterinarian',
                hint: 'Review and add records for pets shared with you.',
              },
            ].map((option) => {
              const selected = form.role === option.value
              return (
                <label
                  key={option.value}
                  className={`cursor-pointer rounded-lg border p-3 text-sm transition ${
                    selected
                      ? 'border-brand bg-brand/5 ring-1 ring-brand'
                      : 'border-line hover:border-brand/40'
                  }`}
                >
                  <span className="flex items-center gap-2 font-medium">
                    <input
                      type="radio"
                      name="role"
                      value={option.value}
                      checked={selected}
                      onChange={() => setForm((prev) => ({ ...prev, role: option.value }))}
                      className="accent-brand"
                    />
                    {option.label}
                  </span>
                  <span className="mt-1 block text-xs text-ink-soft">{option.hint}</span>
                </label>
              )
            })}
          </div>
        </fieldset>

        {form.role === 'veterinarian' ? (
          <div>
            <label className="field-label" htmlFor="clinic_name">
              Clinic name <span className="font-normal">(optional)</span>
            </label>
            <input
              id="clinic_name"
              name="clinic_name"
              type="text"
              autoComplete="organization"
              className="field-input"
              value={form.clinic_name}
              onChange={update('clinic_name')}
            />
          </div>
        ) : null}

        <div>
          <label className="field-label" htmlFor="full_name">
            Name <span className="font-normal">(optional)</span>
          </label>
          <input
            id="full_name"
            name="full_name"
            type="text"
            autoComplete="name"
            className="field-input"
            value={form.full_name}
            onChange={update('full_name')}
          />
        </div>

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
            value={form.email}
            onChange={update('email')}
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
            autoComplete="new-password"
            required
            className="field-input"
            value={form.password}
            onChange={update('password')}
            aria-describedby="password-hint"
          />
          <p id="password-hint" className="mt-1 text-xs text-ink-soft">
            At least {MIN_PASSWORD_LENGTH} characters.
            {tooLong
              ? ` Currently ${passwordBytes} bytes — the maximum is ${MAX_PASSWORD_BYTES}.`
              : ''}
          </p>
        </div>

        {tooShort ? <Notice tone="warn">Password is too short.</Notice> : null}
        {tooLong ? (
          <Notice tone="warn">
            Password is too long. Anything past {MAX_PASSWORD_BYTES} bytes would be
            silently ignored by the hashing algorithm, so it is rejected instead.
          </Notice>
        ) : null}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={submitting || !canSubmit}
        >
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
