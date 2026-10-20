/**
 * The auth context object and its consumer hook.
 *
 * These live apart from the provider component on purpose. A module that exports
 * both a component and something else defeats React Fast Refresh, so the provider
 * re-exports nothing and the hook is imported from here instead.
 */
import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return context
}
