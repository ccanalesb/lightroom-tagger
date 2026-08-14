import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Suspense } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import { invalidateAll } from '../data'
import {
  IdentityAPI,
  SystemAPI,
} from '../services/api'
import {
  EMPTY_BEST_PHOTOS_META,
} from '../__test-utils__/identityFixtures'
import {
  INSIGHTS_KPI_SCORING_9_PLUS,
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_SECTION_NEXT_ACTIONS,
  INSIGHTS_SECTION_PERSPECTIVE_COVERAGE,
} from '../constants/strings'

describe('DashboardPage', () => {
  beforeEach(() => {
    invalidateAll(['dashboard'])
    vi.spyOn(SystemAPI, 'insightsSummary').mockResolvedValue({
      catalog_images: 1,
      scoring_9_plus: 2,
      burst_stacks: 3,
      pending_stack_suggestions: 6,
      unscored_on_active_perspectives: 4,
      no_current_score: 5,
      perspective_coverage: [
        {
          slug: 'framing',
          display_name: 'Framing',
          active: true,
          scored_images: 1,
        },
      ],
    })
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockImplementation(() =>
      Promise.resolve({
        items: [],
        total: 0,
        meta: EMPTY_BEST_PHOTOS_META,
      }),
    )
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
    expect(SystemAPI.insightsSummary).toHaveBeenCalled()
    expect(screen.getByRole('link', { name: new RegExp(INSIGHTS_KPI_SCORING_9_PLUS) })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_HIGHLIGHTS }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_NEXT_ACTIONS }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_PERSPECTIVE_COVERAGE }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_EXPLORE }),
    ).toBeInTheDocument()
  })
})
