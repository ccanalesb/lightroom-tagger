import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { IdentityPage } from './IdentityPage'
import { IdentityAPI } from '../services/api'
import { invalidateAll } from '../data'
import {
  EMPTY_BEST_PHOTOS_META,
  EMPTY_POST_NEXT_META,
  EMPTY_STYLE_FINGERPRINT_RESPONSE,
} from '../__test-utils__/identityFixtures'
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
    invalidateAll(['identity'])
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockResolvedValue({
      items: [],
      total: 0,
      meta: EMPTY_BEST_PHOTOS_META,
    })
    vi.spyOn(IdentityAPI, 'getStyleFingerprint').mockResolvedValue({
      ...EMPTY_STYLE_FINGERPRINT_RESPONSE,
      per_perspective: [
        {
          perspective_slug: 'street',
          mean_score: null,
          median_score: null,
          count_scores: 0,
        },
      ],
    })
    vi.spyOn(IdentityAPI, 'getSuggestions').mockResolvedValue({
      candidates: [],
      total: 0,
      meta: EMPTY_POST_NEXT_META,
      empty_state: null,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders page title and section headings in narrative order', async () => {
    render(
      <MemoryRouter>
        <IdentityPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: IDENTITY_PAGE_TITLE })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 2, name: IDENTITY_SECTION_STYLE_FINGERPRINT }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 2, name: IDENTITY_SECTION_BEST_PHOTOS }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 2, name: IDENTITY_SECTION_POST_NEXT }),
    ).toBeInTheDocument()

    const body = document.body.innerHTML
    expect(
      body.indexOf(IDENTITY_SECTION_STYLE_FINGERPRINT) < body.indexOf(IDENTITY_SECTION_BEST_PHOTOS),
    ).toBe(true)
    expect(
      body.indexOf(IDENTITY_SECTION_BEST_PHOTOS) < body.indexOf(IDENTITY_SECTION_POST_NEXT),
    ).toBe(true)
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
      meta: { ...EMPTY_BEST_PHOTOS_META, coverage_note: 'Custom coverage note from server.' },
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
