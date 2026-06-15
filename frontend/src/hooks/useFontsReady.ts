import { useEffect, useState } from 'react'

/*
 * Returns true once document.fonts.ready resolves — i.e. all @font-face
 * fonts referenced by the current document have either loaded or failed.
 * Use this to gate animations that depend on correct glyph metrics so they
 * don't fire while fallback system fonts are still in place.
 *
 * document.fonts.ready always resolves (never rejects), so no error branch
 * is needed. The `alive` flag prevents a setState call after the effect has
 * cleaned up in React Strict Mode's double-invoke cycle.
 */
export function useFontsReady(): boolean {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let alive = true
    document.fonts.ready.then(() => {
      if (alive) setReady(true)
    })
    return () => {
      alive = false
    }
  }, [])

  return ready
}
