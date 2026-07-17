import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import type { ImageView } from '../../../services/api'
import { PrimaryScorePill } from '../PrimaryScorePill'

function baseImage(overrides: Partial<ImageView> = {}): ImageView {
  return {
    image_type: 'catalog',
    key: 'k',
    ...overrides,
  }
}

describe('PrimaryScorePill', () => {
  it('catalog source does not fall back to description blob scores', () => {
    const { container } = render(
      <PrimaryScorePill
        image={baseImage({
          description_best_perspective: 'street',
        })}
        source="catalog"
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('catalog source renders image_scores-derived best score', () => {
    const { getByLabelText } = render(
      <PrimaryScorePill
        image={baseImage({
          catalog_perspective_score: 8,
          catalog_score_perspective: 'street',
        })}
        source="catalog"
      />,
    )
    expect(getByLabelText('street score 8')).toBeInTheDocument()
  })
})
