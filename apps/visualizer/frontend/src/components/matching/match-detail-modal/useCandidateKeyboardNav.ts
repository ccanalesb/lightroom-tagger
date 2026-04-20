import { useEffect } from 'react';

/**
 * Bind ←/→ arrow keys to step through the candidate carousel while
 * the modal has focus. Ignores keypresses when the user is typing in
 * an input or textarea.
 */
export function useCandidateKeyboardNav(
  enabled: boolean,
  onStep: (delta: -1 | 1) => void,
) {
  useEffect(() => {
    if (!enabled) return;
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        onStep(1);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onStep(-1);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled, onStep]);
}
