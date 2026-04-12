import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { IdentityPage } from './IdentityPage'
import { IdentityAPI } from '../services/api'
import {
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  IDENTITY_FINGERPRINT_EMPTY,
  IDENTITY_PAGE_TITLE,
  IDENTITY_POST_NEXT_EMPTY_FALLBACK,
  IDENTITY_SECTION_BEST_PHOTOS,
  IDENTITY_SECTION_POST_NEXT,
  IDENTITY_SECTION_STYLE_FINGERPRINT,
} from '../constants/strings'

describe('IdentityPage', () => {
  beforeEach(() => {
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockResolvedValue({
      items: [],
      total: 0,
      meta: {},
    })
    vi.spyOn(IdentityAPI, 'getStyleFingerprint').mockResolvedValue({
      per_perspective: [
        {
          perspective_slug: 'street',
          mean_score: null,
          median_score: null,
          count_scores: 0,
        },
      ],
      aggregate_distribution: { '1-3': 0, '4-6': 0, '7-10': 0 },
      top_rationale_tokens: [],
      evidence: {},
      meta: {},
    })
    vi.spyOn(IdentityAPI, 'getSuggestions').mockResolvedValue({
      candidates: [],
      meta: {},
      empty_state: null,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders page title and section headings', async () => {
    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: IDENTITY_PAGE_TITLE })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: IDENTITY_SECTION_BEST_PHOTOS }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: IDENTITY_SECTION_STYLE_FINGERPRINT }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: IDENTITY_SECTION_POST_NEXT }),
    ).toBeInTheDocument()
  })

  it('shows empty-state copy when APIs return no data', async () => {
    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText(IDENTITY_FINGERPRINT_EMPTY)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText(IDENTITY_POST_NEXT_EMPTY_FALLBACK)).toBeInTheDocument()
    })
  })

  it('prefers coverage_note for best photos when total is zero', async () => {
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockResolvedValue({
      items: [],
      total: 0,
      meta: { coverage_note: 'Custom coverage note from server.' },
    })

    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Custom coverage note from server.')).toBeInTheDocument()
    })
  })
})
