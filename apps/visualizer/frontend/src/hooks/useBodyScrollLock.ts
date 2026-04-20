import { useEffect } from 'react'

/**
 * Lock body scroll while `active` is true.
 *
 * Preserves the previous `document.body.style.overflow` value and
 * restores it on unmount so stacking modals don't leak the locked
 * style. Mirrors the behavior of the legacy `Modal.tsx` helper while
 * exposing it as a reusable hook.
 */
export function useBodyScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [active])
}
