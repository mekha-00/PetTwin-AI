/**
 * Shared data-loading hook.
 *
 * Wraps the request/loading/error cycle that every Phase 3 page needs. There is a
 * single fetch path: the effect runs the loader, and `reload` just bumps a nonce
 * that the effect depends on. Having both an effect and a hand-written retry
 * callback meant two copies of the same logic to keep in step.
 */
import { useCallback, useEffect, useState } from 'react'

import { describeError } from '../lib/api'

export function useAsyncData(loader, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    // Guards against setting state after the user has navigated away, which
    // otherwise produces a React warning and a wasted render.
    let active = true

    setIsLoading(true)
    setError(null)

    loader()
      .then((result) => {
        if (active) setData(result)
      })
      .catch((err) => {
        if (active) setError(describeError(err))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
    }
    // `loader` is an inline closure at every call site, so it cannot be a
    // dependency without refetching on each render. Callers pass an explicit
    // `deps` array instead, and must list everything the loader closes over.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { data, error, isLoading, reload, setData }
}
