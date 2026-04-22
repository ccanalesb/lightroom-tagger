import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MatchGroupTile } from '../MatchGroupTile'
import { MATCH_VALIDATED } from '../../../constants/strings'
import type { CatalogImage, InstagramImage, MatchGroup } from '../../../services/api'

function instagramFixture(overrides: Partial<InstagramImage> = {}): InstagramImage {
  return {
    key: 'ig-key-1',
    local_path: '/media/ig',
    filename: 'instagram-thumb',
    instagram_folder: 'folder',
    source_folder: 'posts',
    date_folder: '202401',
    crawled_at: '2024-01-01T00:00:00Z',
    image_index: 0,
    total_in_post: 1,
    ...overrides,
  }
}

function catalogFixture(filename: string, key = 'cat-key'): CatalogImage {
  return {
    id: null,
    key,
    filename,
    filepath: '/cat',
    date_taken: '2024-01-01',
    rating: 0,
    pick: false,
    color_label: '',
    keywords: [],
    title: '',
    caption: '',
    copyright: '',
    width: 100,
    height: 100,
    instagram_posted: false,
  }
}

describe('MatchGroupTile', () => {
  it('shows catalog filename and validated badge when group is validated', () => {
    const group: MatchGroup = {
      instagram_key: 'ig-key-1',
      instagram_image: instagramFixture(),
      candidates: [
        {
          instagram_key: 'ig-key-1',
          catalog_key: 'cat-key',
          score: 0.9,
          rank: 1,
          catalog_image: catalogFixture('foo.jpg'),
        },
      ],
      best_score: 0.9,
      candidate_count: 1,
      has_validated: true,
    }
    render(<MatchGroupTile group={group} onOpenReview={vi.fn()} />)
    expect(screen.getByTestId('image-tile')).toBeInTheDocument()
    expect(screen.getByText('foo.jpg')).toBeInTheDocument()
    expect(screen.getByText(MATCH_VALIDATED)).toBeInTheDocument()
  })

  it('shows candidate count only when not validated (no catalog filename)', () => {
    const secretCatalog = 'secret-catalog.jpg'
    const group: MatchGroup = {
      instagram_key: 'ig-key-1',
      instagram_image: instagramFixture(),
      candidates: [
        {
          instagram_key: 'ig-key-1',
          catalog_key: 'c1',
          score: 0.8,
          rank: 1,
          catalog_image: catalogFixture(secretCatalog, 'c1'),
        },
      ],
      best_score: 0.8,
      candidate_count: 3,
      has_validated: false,
    }
    render(<MatchGroupTile group={group} onOpenReview={vi.fn()} />)
    expect(screen.getByText('3 candidates')).toBeInTheDocument()
    expect(screen.queryByText(secretCatalog)).not.toBeInTheDocument()
  })
})
