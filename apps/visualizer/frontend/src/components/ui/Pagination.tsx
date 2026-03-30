import { PAGINATION_PREVIOUS, PAGINATION_NEXT } from '../../constants/strings'

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  disabled?: boolean
}

export function Pagination({ currentPage, totalPages, onPageChange, disabled }: PaginationProps) {
  if (totalPages <= 1) return null

  return (
    <div className="flex justify-center items-center gap-4 pt-4">
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        disabled={currentPage <= 1 || disabled}
        className="px-3 py-1 rounded text-sm border disabled:opacity-30"
      >
        {PAGINATION_PREVIOUS}
      </button>
      <span className="text-sm text-gray-600">
        Page {currentPage} of {totalPages}
      </span>
      <button
        type="button"
        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage >= totalPages || disabled}
        className="px-3 py-1 rounded text-sm border disabled:opacity-30"
      >
        {PAGINATION_NEXT}
      </button>
    </div>
  )
}
