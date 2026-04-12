import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { UnpostedCatalogPanel } from './UnpostedCatalogPanel'
import { AnalyticsAPI, ImagesAPI } from '../../services/api'
import {
  ANALYTICS_NOT_POSTED_EMPTY_ALL_POSTED,
} from '../../constants/strings'

const emptyPagination = {
  offset: 0,
  limit: 50,
  current_page: 1,
  total_pages: 0,
  has_more: false,
}

describe('UnpostedCatalogPanel', () => {
  beforeEach(() => {
    vi.spyOn(ImagesAPI, 'getCatalogMonths').mockResolvedValue({ months: [] })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows empty-all-posted copy when API returns no rows', async () => {
    vi.spyOn(AnalyticsAPI, 'getUnpostedCatalog').mockResolvedValue({
      total: 0,
      images: [],
      pagination: emptyPagination,
    })

    render(<UnpostedCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByText(ANALYTICS_NOT_POSTED_EMPTY_ALL_POSTED)).toBeInTheDocument()
    })
  })

  it('renders filename when one unposted image is returned', async () => {
    vi.spyOn(AnalyticsAPI, 'getUnpostedCatalog').mockResolvedValue({
      total: 1,
      images: [
        {
          key: 'k1',
          filename: 'unique-test-filename.jpg',
          date_taken: '2024-01-15',
          rating: 3,
        },
      ],
      pagination: {
        offset: 0,
        limit: 50,
        current_page: 1,
        total_pages: 1,
        has_more: false,
      },
    })

    render(<UnpostedCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByText('unique-test-filename.jpg')).toBeInTheDocument()
    })
  })
})
