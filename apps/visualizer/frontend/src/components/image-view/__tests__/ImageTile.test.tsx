import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { ImageView } from '../../../services/api'
import { ImageTile } from '../ImageTile'
import { Badge } from '../../ui/Badge'

function baseImage(overrides: Partial<ImageView> = {}): ImageView {
  return {
    image_type: 'catalog',
    key: 'abc',
    filename: 'img.jpg',
    date_taken: '2024-05-01T00:00:00Z',
    ...overrides,
  }
}

describe('ImageTile', () => {
  it('renders filename, falling back to key', () => {
    render(
      <ImageTile
        image={baseImage({ filename: undefined })}
        variant="grid"
        primaryScoreSource="none"
        onClick={() => {}}
      />,
    )
    expect(screen.getByText('abc')).toBeInTheDocument()
  })

  it('thumbnail src uses image_type and encoded key', () => {
    render(
      <ImageTile
        image={baseImage({ image_type: 'instagram', key: 'a b/c' })}
        variant="grid"
        primaryScoreSource="none"
        onClick={() => {}}
      />,
    )
    const img = screen.getByRole('img') as HTMLImageElement
    expect(img.src).toContain('/api/images/instagram/a%20b%2Fc/thumbnail')
  })

  it('invokes onClick when the thumbnail button is clicked', () => {
    const onClick = vi.fn()
    render(
      <ImageTile
        image={baseImage()}
        variant="grid"
        primaryScoreSource="none"
        onClick={onClick}
      />,
    )
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('renders subtitle prop over image.title when both present', () => {
    render(
      <ImageTile
        image={baseImage({ title: 'Img title' })}
        subtitle="explicit subtitle"
        variant="grid"
        primaryScoreSource="none"
        onClick={() => {}}
      />,
    )
    expect(screen.getByText('explicit subtitle')).toBeInTheDocument()
    expect(screen.queryByText('Img title')).toBeNull()
  })

  it('renders identity aggregate pill when source=identity', () => {
    render(
      <ImageTile
        image={baseImage({ identity_aggregate_score: 8.2 })}
        variant="compact"
        primaryScoreSource="identity"
        onClick={() => {}}
      />,
    )
    expect(screen.getByLabelText('Aggregate score 8.2')).toBeInTheDocument()
  })

  it('overlayBadges slot renders on top-right of thumbnail', () => {
    render(
      <ImageTile
        image={baseImage({ image_type: 'instagram' })}
        variant="grid"
        primaryScoreSource="none"
        overlayBadges={<Badge variant="success">Matched</Badge>}
        onClick={() => {}}
      />,
    )
    expect(screen.getByText('Matched')).toBeInTheDocument()
  })

  it('footer slot renders beneath metadata badges', () => {
    render(
      <ImageTile
        image={baseImage()}
        variant="list"
        primaryScoreSource="identity"
        footer={<div data-testid="reasons">reason bullets</div>}
        onClick={() => {}}
      />,
    )
    expect(screen.getByTestId('reasons')).toBeInTheDocument()
  })

  it('strip variant applies fixed width root class', () => {
    const { container } = render(
      <ImageTile
        image={baseImage()}
        variant="strip"
        primaryScoreSource="identity"
        onClick={() => {}}
      />,
    )
    expect((container.firstChild as HTMLElement).className).toContain('w-[200px]')
  })

  it('grid variant uses aspect-square thumb', () => {
    const { container } = render(
      <ImageTile
        image={baseImage()}
        variant="grid"
        primaryScoreSource="none"
        onClick={() => {}}
      />,
    )
    const thumb = container.querySelector('.aspect-square')
    expect(thumb).not.toBeNull()
  })

  it('falls back to created_at for date display when date_taken missing', () => {
    render(
      <ImageTile
        image={baseImage({
          date_taken: undefined,
          created_at: '2024-06-15T00:00:00Z',
        })}
        variant="grid"
        primaryScoreSource="none"
        onClick={() => {}}
      />,
    )
    const expected = new Date('2024-06-15T00:00:00Z').toLocaleDateString()
    expect(screen.getByText(expected)).toBeInTheDocument()
  })
})
