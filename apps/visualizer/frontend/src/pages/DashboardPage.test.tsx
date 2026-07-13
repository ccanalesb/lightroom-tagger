import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Suspense } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import { invalidateAll } from '../data'
import {
  AnalyticsAPI,
  IdentityAPI,
  JobsAPI,
  SystemAPI,
} from '../services/api'
import {
  EMPTY_BEST_PHOTOS_META,
  EMPTY_STYLE_FINGERPRINT_RESPONSE,
} from '../__test-utils__/identityFixtures'
import {
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_SECTION_POSTING,
  INSIGHTS_SECTION_SCORES,
} from '../constants/strings'

describe('DashboardPage', () => {
  beforeEach(() => {
    invalidateAll(['dashboard'])
    vi.spyOn(SystemAPI, 'stats').mockResolvedValue({
      catalog_images: 1,
      instagram_images: 2,
      posted_to_instagram: 0,
      matches_found: 0,
      db_path: '/tmp/x.db',
    })
    vi.spyOn(IdentityAPI, 'getStyleFingerprint').mockResolvedValue({
      ...EMPTY_STYLE_FINGERPRINT_RESPONSE,
      per_perspective: [
        {
          perspective_slug: 'street',
          mean_score: 7,
          median_score: 7,
          count_scores: 3,
        },
      ],
      aggregate_distribution: { '7-10': 2, '4-6': 1, '1-3': 0 },
    })
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockImplementation(() =>
      Promise.resolve({
        items: [],
        total: 0,
        meta: EMPTY_BEST_PHOTOS_META,
      }),
    )
    vi.spyOn(AnalyticsAPI, 'getPostingFrequency').mockResolvedValue({
      buckets: [{ bucket_start: '2025-01-01', count: 1 }],
      meta: {
        timestamp_source: null,
        granularity: 'day',
        timezone_assumption: 'UTC',
        date_from: null,
        date_to: null,
        bucket_expression: null,
      },
    })
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
      expect(
        screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_SCORES }),
      ).toBeInTheDocument()
    })
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
    expect(screen.getByRole('heading', { level: 3, name: INSIGHTS_SECTION_POSTING })).toBeInTheDocument()
  })
})
