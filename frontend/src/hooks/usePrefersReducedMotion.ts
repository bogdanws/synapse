import { useSyncExternalStore } from 'react'

/*
 * Subscribe to the user's reduced-motion preference. Uses
 * useSyncExternalStore so the matchMedia value is read during render
 * (no setState-in-effect cascade) and stays in sync if the user toggles
 * the OS preference mid-session. Returns `false` during SSR via the
 * `getServerSnapshot` argument.
 */

const QUERY = '(prefers-reduced-motion: reduce)'

function subscribe(notify: () => void): () => void {
  const mq = window.matchMedia(QUERY)
  mq.addEventListener('change', notify)
  return () => mq.removeEventListener('change', notify)
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches
}

function getServerSnapshot(): boolean {
  return false
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
