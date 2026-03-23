import { useState, useCallback } from 'react'

interface PaginationState {
  offset: number
  limit: number
  currentPage: number
  totalPages: number
  hasMore: boolean
}

interface UsePaginationReturn {
  pagination: PaginationState
  goToPage: (page: number) => void
  nextPage: () => void
  prevPage: () => void
  reset: () => void
}

export function usePagination(
  itemsPerPage: number,
  totalItems: number
): UsePaginationReturn {
  const [offset, setOffset] = useState(0)

  const totalPages = Math.ceil(totalItems / itemsPerPage)
  const currentPage = Math.floor(offset / itemsPerPage) + 1
  const hasMore = (offset + itemsPerPage) < totalItems

  const goToPage = useCallback((page: number) => {
    setOffset((page - 1) * itemsPerPage)
  }, [itemsPerPage])

  const nextPage = useCallback(() => {
    if (hasMore) {
      setOffset(prev => prev + itemsPerPage)
    }
  }, [hasMore, itemsPerPage])

  const prevPage = useCallback(() => {
    setOffset(prev => Math.max(0, prev - itemsPerPage))
  }, [itemsPerPage])

  const reset = useCallback(() => {
    setOffset(0)
  }, [])

  return {
    pagination: {
      offset,
      limit: itemsPerPage,
      currentPage,
      totalPages,
      hasMore,
    },
    goToPage,
    nextPage,
    prevPage,
    reset,
  }
}
