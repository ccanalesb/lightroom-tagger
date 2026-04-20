import { useEffect, type RefObject } from 'react';

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

function isEditableTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  if (EDITABLE_TAGS.has(el.tagName)) return true;
  return el.isContentEditable;
}

/**
 * Bind ←/→ arrow keys to step through the candidate carousel while the
 * modal is active. The listener is gated on `containerRef.contains(
 * document.activeElement)` so arrow-key usage anywhere outside the modal
 * (adjacent grids, filter bars, page-level hotkeys) is never intercepted.
 * Editable targets (`<input>`, `<textarea>`, `<select>`, `contenteditable`)
 * pass through so text-field navigation still works inside the modal.
 *
 * When no element inside the modal currently has focus, the handler is a
 * no-op -- the outer modal shell is responsible for moving focus into the
 * dialog when it opens.
 */
export function useCandidateKeyboardNav(
  enabled: boolean,
  containerRef: RefObject<HTMLElement | null>,
  onStep: (delta: -1 | 1) => void,
) {
  useEffect(() => {
    if (!enabled) return;
    function onKey(e: KeyboardEvent) {
      const container = containerRef.current;
      if (!container) return;
      if (!container.contains(document.activeElement)) return;
      if (isEditableTarget(e.target)) return;
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
  }, [enabled, containerRef, onStep]);
}
