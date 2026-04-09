interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  disabled?: boolean
}

export function Pagination({ currentPage, totalPages, onPageChange, disabled }: PaginationProps) {
  if (totalPages <= 1) return null

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)

  // Show max 7 pages: [1] ... [n-1] [n] [n+1] ... [total]
  let visiblePages = pages
  if (totalPages > 7) {
    if (currentPage <= 3) {
      visiblePages = [...pages.slice(0, 5), -1, totalPages]
    } else if (currentPage >= totalPages - 2) {
      visiblePages = [1, -1, ...pages.slice(totalPages - 5)]
    } else {
      visiblePages = [1, -1, currentPage - 1, currentPage, currentPage + 1, -1, totalPages]
    }
  }

  return (
    <div className="flex items-center space-x-2">
      <button
        type="button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1 || disabled}
        className="px-3 py-2 rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        aria-label="Previous page"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {visiblePages.map((page, index) =>
        page === -1 ? (
          <span key={`ellipsis-${index}`} className="px-3 py-2 text-text-tertiary">
            ...
          </span>
        ) : (
          <button
            type="button"
            key={page}
            onClick={() => onPageChange(page)}
            disabled={disabled}
            className={`px-3 py-2 rounded-base border transition-all ${
              page === currentPage
                ? 'bg-accent-light text-accent border-accent font-medium'
                : 'border-border bg-bg text-text-secondary hover:bg-surface hover:text-text'
            }`}
          >
            {page}
          </button>
        )
      )}

      <button
        type="button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages || disabled}
        className="px-3 py-2 rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        aria-label="Next page"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  )
}
