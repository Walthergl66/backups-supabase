import { useEffect, useMemo } from 'react'

export function useAbort() {
  const controller = useMemo(() => new AbortController(), [])
  useEffect(() => () => controller.abort(), [controller])
  return controller.signal
}

export function isAbortError(e) {
  return e?.name === 'AbortError'
}