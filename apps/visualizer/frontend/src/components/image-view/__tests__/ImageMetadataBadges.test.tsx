import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ImageView } from '../../../services/api'
import { ImageMetadataBadges } from '../ImageMetadataBadges'

function baseImage(overrides: Partial<ImageView> = {}): ImageView {
  return {
    image_type: 'catalog',
    key: 'k',
    ...overrides,
  }
}

describe('ImageMetadataBadges', () => {
  it('renders rating, pick, posted, AI chips when flags are set', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({
          rating: 4,
          pick: true,
          instagram_posted: true,
          ai_analyzed: true,
        })}
        primaryScoreSource="none"
      />,
    )
    expect(screen.getByText('Posted')).toBeInTheDocument()
    expect(screen.getByText('4★')).toBeInTheDocument()
    expect(screen.getByText('Pick')).toBeInTheDocument()
    expect(screen.getByText('AI')).toBeInTheDocument()
  })

  it('omits rating chip when rating is 0 or missing', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({ rating: 0 })}
        primaryScoreSource="none"
      />,
    )
    expect(screen.queryByText(/★/)).toBeNull()
  })

  it('identity source shows aggregate pill when identity score is present', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({ identity_aggregate_score: 7.3 })}
        primaryScoreSource="identity"
      />,
    )
    expect(screen.getByLabelText('Aggregate score 7.3')).toBeInTheDocument()
  })

  it('identity source omits pill entirely when no identity score', () => {
    const { container } = render(
      <ImageMetadataBadges
        image={baseImage({ identity_aggregate_score: null })}
        primaryScoreSource="identity"
      />,
    )
    expect(container.querySelector('[aria-label^="Aggregate score"]')).toBeNull()
  })

  it('catalog source prefers catalog_perspective_score with slug label', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({
          catalog_perspective_score: 8,
          catalog_score_perspective: 'street',
        })}
        primaryScoreSource="catalog"
      />,
    )
    expect(screen.getByLabelText('street score 8')).toBeInTheDocument()
  })

  it('catalog source falls back to description best-perspective score', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({
          description_best_perspective: 'street',
          description_perspectives: {
            street: { analysis: '', score: 6 },
          },
        })}
        primaryScoreSource="catalog"
      />,
    )
    expect(screen.getByLabelText(/score 6$/)).toBeInTheDocument()
  })

  it('Instagram tile (source=none) shows no primary score pill', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({
          image_type: 'instagram',
          identity_aggregate_score: 7,
          catalog_perspective_score: 7,
        })}
        primaryScoreSource="none"
      />,
    )
    expect(screen.queryByLabelText(/score/)).toBeNull()
  })

  it('hidePrimaryScore suppresses the pill even when source would render one', () => {
    render(
      <ImageMetadataBadges
        image={baseImage({ identity_aggregate_score: 9 })}
        primaryScoreSource="identity"
        hidePrimaryScore
      />,
    )
    expect(screen.queryByLabelText(/score/)).toBeNull()
  })
})
