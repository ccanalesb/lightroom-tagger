import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Suspense } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import { invalidateAll } from '../data'
import {
  IdentityAPI,
  JobsAPI,
  SystemAPI,
} from '../services/api'
import {
  EMPTY_BEST_PHOTOS_META,
} from '../__test-utils__/identityFixtures'
import {
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
} from '../constants/strings'

describe('DashboardPage', () => {
  beforeEach(() => {
    invalidateAll(['dashboard'])
    vi.spyOn(SystemAPI, 'stats').mockResolvedValue({
      catalog_images: 1,
      posted_to_instagram: 0,
      db_path: '/tmp/x.db',
    })
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockImplementation(() =>
      Promise.resolve({
        items: [],
        total: 0,
        meta: EMPTY_BEST_PHOTOS_META,
      }),
    )
    vi.spyOn(JobsAPI, 'list').mockResolvedValue({
      total: 0,
      data: [],
      pagination: { offset: 0, limit: 50, current_page: 1, total_pages: 0, has_more: false },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders insights title and section headings', async () => {
    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <DashboardPage />
        </Suspense>
      </MemoryRouter>,
    )

    expect(
      await screen.findByRole('heading', { level: 1, name: INSIGHTS_PAGE_TITLE }),
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Unposted' })).toBeInTheDocument()
    })
    expect(screen.getByRole('tab', { name: 'Posted' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'All' })).toBeInTheDocument()
    expect(IdentityAPI.getBestPhotos).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 8, posted: false }),
    )
    expect(IdentityAPI.getBestPhotos).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 8, posted: true }),
    )
    expect(IdentityAPI.getBestPhotos).toHaveBeenCalledWith({ limit: 8 })
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_HIGHLIGHTS }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_EXPLORE }),
    ).toBeInTheDocument()
  })
})
