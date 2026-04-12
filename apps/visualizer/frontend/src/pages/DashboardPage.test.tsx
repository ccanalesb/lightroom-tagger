import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import {
  AnalyticsAPI,
  IdentityAPI,
  JobsAPI,
  SystemAPI,
} from '../services/api'
import {
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_SECTION_POSTING,
  INSIGHTS_SECTION_SCORES,
} from '../constants/strings'

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.spyOn(SystemAPI, 'stats').mockResolvedValue({
      catalog_images: 1,
      instagram_images: 2,
      posted_to_instagram: 0,
      matches_found: 0,
      db_path: '/tmp/x.db',
    })
    vi.spyOn(IdentityAPI, 'getStyleFingerprint').mockResolvedValue({
      per_perspective: [
        {
          perspective_slug: 'street',
          mean_score: 7,
          median_score: 7,
          count_scores: 3,
        },
      ],
      aggregate_distribution: { '7-10': 2, '4-6': 1, '1-3': 0 },
      top_rationale_tokens: [],
      evidence: {},
      meta: {},
    })
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockResolvedValue({
      items: [],
      total: 0,
      meta: {},
    })
    vi.spyOn(AnalyticsAPI, 'getPostingFrequency').mockResolvedValue({
      buckets: [{ bucket_start: '2025-01-01', count: 1 }],
      meta: { timezone_assumption: 'UTC' },
    })
    vi.spyOn(JobsAPI, 'list').mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders insights title and section headings', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: INSIGHTS_PAGE_TITLE })).toBeInTheDocument()
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_SCORES }),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_HIGHLIGHTS }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: INSIGHTS_SECTION_EXPLORE }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: INSIGHTS_SECTION_POSTING })).toBeInTheDocument()
  })
})
