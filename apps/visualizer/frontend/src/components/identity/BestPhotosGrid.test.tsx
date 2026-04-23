import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { BestPhotosGrid } from './BestPhotosGrid'
import { IdentityAPI } from '../../services/api'
import { invalidateAll } from '../../data'
import { IDENTITY_SECTION_BEST_PHOTOS } from '../../constants/strings'

const postedBestPhotoItem = {
  image_key: 'k1',
  aggregate_score: 8,
  perspectives_covered: 3,
  eligible: true,
  per_perspective: [
    {
      perspective_slug: 'street',
      display_name: 'Street',
      score: 9,
      prompt_version: 'v1',
      model_used: 'm',
      scored_at: 't',
      rationale_preview: '',
    },
  ],
  filename: 'k1.jpg',
  date_taken: '2024-01-01',
  rating: 5,
  instagram_posted: true,
}

describe('BestPhotosGrid', () => {
  beforeEach(() => {
    invalidateAll(['identity'])
    vi.spyOn(IdentityAPI, 'getBestPhotos').mockResolvedValue({
      items: [postedBestPhotoItem],
      total: 1,
      meta: {},
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows one Posted badge on posted tiles (overlay only, no duplicate metadata row)', async () => {
    render(<BestPhotosGrid />)

    const section = await screen.findByRole('region', { name: IDENTITY_SECTION_BEST_PHOTOS })

    await waitFor(() => {
      const posted = within(section).getAllByText('Posted')
      expect(posted.length).toBe(1)
    })
  })

  it('shows dominant perspective label and score from per_perspective in the tile footer', async () => {
    render(<BestPhotosGrid />)

    const section = await screen.findByRole('region', { name: IDENTITY_SECTION_BEST_PHOTOS })

    await waitFor(() => {
      expect(within(section).getByText('Street 9')).toBeInTheDocument()
    })
  })
})
