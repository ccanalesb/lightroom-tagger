import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TopPhotosStrip } from '../TopPhotosStrip'
import type { IdentityBestPhotoItem } from '../../../services/api'

const item: IdentityBestPhotoItem = {
  image_key: 'k-dash',
  aggregate_score: 8,
  perspectives_covered: 1,
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
  filename: 'k.jpg',
  date_taken: '2024-01-01',
  rating: 0,
  instagram_posted: false,
}

describe('TopPhotosStrip', () => {
  it('renders dominant perspective label and score in the tile footer', () => {
    render(
      <TopPhotosStrip items={[item]} loading={false} error={null} emptyMessage={null} />,
    )
    expect(screen.getByText('Street 9')).toBeInTheDocument()
  })
})
