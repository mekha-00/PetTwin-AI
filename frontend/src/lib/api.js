/**
 * Axios client for the PetTwin API.
 *
 * Security notes:
 * - The base URL comes from `VITE_API_BASE_URL`. Only the URL is ever exposed
 *   to the browser; no API key, signing secret, or database credential is
 *   referenced anywhere in this file or any other frontend file.
 * - The access token is read from localStorage per request rather than baked in
 *   at build time, so it is never captured in the compiled bundle.
 * - A 401 response clears the stored session and redirects to login, so a
 *   revoked or expired token cannot leave the UI in a half-authenticated state.
 */
import axios from 'axios'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const TOKEN_KEY = 'pettwin.accessToken'
const USER_KEY = 'pettwin.user'

/** Where a 401 handler sends the browser. Read lazily to avoid a circular import. */
function redirectToLogin() {
  if (window.location.pathname === '/login') return
  const next = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.assign(`/login?next=${next}`)
}

export const tokenStore = {
  get() {
    return window.localStorage.getItem(TOKEN_KEY)
  },
  set(token) {
    window.localStorage.setItem(TOKEN_KEY, token)
  },
  clear() {
    window.localStorage.removeItem(TOKEN_KEY)
    window.localStorage.removeItem(USER_KEY)
  },
  getUser() {
    const raw = window.localStorage.getItem(USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch {
      // Corrupt value: drop it rather than letting it break every render.
      window.localStorage.removeItem(USER_KEY)
      return null
    }
  },
  setUser(user) {
    window.localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      tokenStore.clear()
      redirectToLogin()
    }
    return Promise.reject(error)
  },
)

/**
 * Turn a FastAPI error into a single readable sentence.
 *
 * FastAPI returns `detail` as a string for HTTPException and as a list of
 * field-error objects for validation failures, so both shapes are handled.
 */
export function describeError(error) {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
        const message = item.msg || 'Invalid value'
        return field ? `${field}: ${message}` : message
      })
      .join('; ')
  }

  if (error?.code === 'ECONNABORTED') {
    return 'The request timed out. Please try again.'
  }

  if (error?.response === undefined) {
    return 'Cannot reach the API. Is the backend running on port 8000?'
  }

  return 'Something went wrong. Please try again.'
}

export default api
