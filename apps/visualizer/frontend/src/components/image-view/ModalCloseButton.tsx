interface ModalCloseButtonProps {
  onClick: () => void
  ariaLabel?: string
}

/**
 * Standard "close" (×) button used by modal shells. Extracted from
 * `ImageDetailModal` so other modal shells can reuse the exact same
 * chrome + focus ring instead of re-inlining the SVG path.
 */
export function ModalCloseButton({ onClick, ariaLabel = 'Close' }: ModalCloseButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="shrink-0 rounded-base border border-border bg-surface/80 p-2 backdrop-blur-sm transition-all hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-accent"
    >
      <svg
        className="h-5 w-5 text-text"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    </button>
  )
}
