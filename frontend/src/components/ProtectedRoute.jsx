/**
 * Gate for authenticated routes, with optional role restriction.
 *
 * While the stored token is being revalidated the router waits rather than
 * redirecting, otherwise a refresh on a deep link would bounce the user to the
 * login screen for a moment before the token turns out to be valid.
 *
 * The optional `roles` prop restricts a route to specific account roles. This is
 * a usability guard only: the API enforces every real permission, so a user who
 * bypassed it would still be refused by the server.
 */
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/authContext'
import { PageLoader } from './ui'

export default function ProtectedRoute({ children, roles = null }) {
  const { user, isAuthenticated, isChecking } = useAuth()
  const location = useLocation()

  if (isChecking) {
    return <PageLoader label="Checking your session" />
  }

  if (!isAuthenticated) {
    // Remember where the user was headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (roles !== null && !roles.includes(user?.role)) {
    // Signed in, but this area is not for their role. Send them somewhere real.
    return <Navigate to="/" replace />
  }

  return children
}
