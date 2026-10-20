/**
 * Redirects an already-authenticated visitor away from the login and register
 * screens, honouring the `from` location captured by `ProtectedRoute` so a
 * refresh on a deep link returns the user to where they were going.
 */
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/authContext'
import { PageLoader } from './ui'

export default function RequireAuth({ children }) {
  const { isAuthenticated, isChecking } = useAuth()
  const location = useLocation()

  if (isChecking) {
    return <PageLoader label="Checking your session" />
  }

  if (isAuthenticated) {
    const destination = location.state?.from || '/'
    return <Navigate to={destination} replace />
  }

  return children
}
