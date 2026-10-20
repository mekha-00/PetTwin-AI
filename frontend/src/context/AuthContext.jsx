/**
 * Auth provider: holds the signed-in user and the access token.
 *
 * The token lives in localStorage so a page refresh does not sign the user out.
 * That is acceptable here because the token is a short-lived bearer credential
 * and this is a local development build; a production deployment should prefer an
 * httpOnly cookie. Nothing secret is stored in JavaScript source.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'

import { fetchCurrentUser, login as loginRequest, register as registerRequest } from '../lib/endpoints'
import { tokenStore } from '../lib/api'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  // Seeded from storage so a refresh on a protected route stays signed in.
  const [token, setToken] = useState(() => tokenStore.get())
  const [user, setUser] = useState(() => tokenStore.getUser())
  const [isChecking, setIsChecking] = useState(Boolean(tokenStore.get()))

  /** Re-read the profile from the API to confirm the stored token is still valid. */
  const refreshUser = useCallback(async () => {
    const fresh = await fetchCurrentUser()
    tokenStore.setUser(fresh)
    setUser(fresh)
    return fresh
  }, [])

  const signIn = useCallback(async (credentials) => {
    const result = await loginRequest(credentials)
    tokenStore.set(result.access_token)
    tokenStore.setUser(result.user)
    setToken(result.access_token)
    setUser(result.user)
    return result.user
  }, [])

  const signUp = useCallback(async (payload) => {
    const result = await registerRequest(payload)
    tokenStore.set(result.access_token)
    tokenStore.setUser(result.user)
    setToken(result.access_token)
    setUser(result.user)
    return result.user
  }, [])

  const signOut = useCallback(() => {
    tokenStore.clear()
    setToken(null)
    setUser(null)
  }, [])

  /**
   * Revalidate a stored token once on mount.
   *
   * Without this, a refresh on a protected route would leave `isChecking` true
   * forever and the router would never settle. If the API rejects the token the
   * interceptor has already cleared storage, so all that is left is to drop the
   * in-memory copy and stop blocking the router.
   */
  useEffect(() => {
    let active = true
    ;(async () => {
      if (!tokenStore.get()) {
        if (active) setIsChecking(false)
        return
      }
      try {
        const fresh = await fetchCurrentUser()
        if (!active) return
        tokenStore.setUser(fresh)
        setUser(fresh)
      } catch {
        // The 401 interceptor has already cleared storage.
        if (!active) return
        setToken(null)
        setUser(null)
      } finally {
        if (active) setIsChecking(false)
      }
    })()

    return () => {
      active = false
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token),
      isChecking,
      signIn,
      signUp,
      signOut,
      refreshUser,
    }),
    [user, token, isChecking, signIn, signUp, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
