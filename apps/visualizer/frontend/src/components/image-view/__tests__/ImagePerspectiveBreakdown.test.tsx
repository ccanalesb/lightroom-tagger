import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { IdentityPerPerspectiveScore } from '../../../services/api'
import { ImagePerspectiveBreakdown } from '../ImagePerspectiveBreakdown'

const sample: IdentityPerPerspectiveScore[] = [
  {
    perspective_slug: 'street',
    display_name: 'Street',
    score: 8,
    prompt_version: 'v1',
    model_used: 'm1',
    scored_at: '',
    rationale_preview: '',
  },
  {
    perspective_slug: 'documentary',
    display_name: 'Documentary',
    score: 6,
    prompt_version: '',
    model_used: '',
    scored_at: '',
    rationale_preview: '',
  },
]

describe('ImagePerspectiveBreakdown', () => {
  it('renders nothing when perspectives is empty or undefined', () => {
    const { container: c1 } = render(
      <ImagePerspectiveBreakdown perspectives={undefined} />,
    )
    expect(c1.firstChild).toBeNull()

    const { container: c2 } = render(<ImagePerspectiveBreakdown perspectives={[]} />)
    expect(c2.firstChild).toBeNull()
  })

  it('renders a row per perspective with display_name and score', () => {
    render(
      <ImagePerspectiveBreakdown
        perspectives={sample}
        aggregateScore={7}
        perspectivesCovered={2}
      />,
    )
    expect(screen.getByText('Street')).toBeInTheDocument()
    expect(screen.getByText('Documentary')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByLabelText('Aggregate score 7')).toBeInTheDocument()
    expect(screen.getByText('Perspectives scored: 2')).toBeInTheDocument()
  })

  it('falls back to perspectives.length when perspectivesCovered is omitted', () => {
    render(<ImagePerspectiveBreakdown perspectives={sample} aggregateScore={7} />)
    expect(screen.getByText('Perspectives scored: 2')).toBeInTheDocument()
  })

  it('shows em-dash placeholders for empty prompt_version / model_used', () => {
    render(<ImagePerspectiveBreakdown perspectives={sample} aggregateScore={7} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('hideSummary omits the aggregate + perspectives-scored row', () => {
    render(
      <ImagePerspectiveBreakdown
        perspectives={sample}
        aggregateScore={7}
        perspectivesCovered={2}
        hideSummary
      />,
    )
    expect(screen.queryByLabelText(/Aggregate score/)).toBeNull()
    expect(screen.queryByText(/Perspectives scored/)).toBeNull()
    expect(screen.getByText('Street')).toBeInTheDocument()
  })
})
