import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ImageDetailResponse } from '../../../services/api'
import { deleteMatching } from '../../../data/cache'

vi.mock('../CatalogImageDetailSections', () => ({
  CatalogImageDetailSections: ({
    image,
    onDataChanged,
  }: {
    image: { key: string }
    onDataChanged?: () => void
  }) => (
    <div data-testid="catalog-sections" data-key={image.key}>
      <button type="button" onClick={() => onDataChanged?.()}>
        refetch
      </button>
    </div>
  ),
}))

vi.mock('../InstagramImageDetailSections', () => ({
  InstagramImageDetailSections: ({ image }: { image: { key: string } }) => (
    <div data-testid="instagram-sections" data-key={image.key} />
  ),
}))

import { ImageDetailModal } from '../ImageDetailModal'
import { ImagesAPI } from '../../../services/api'

function buildDetail(overrides: Partial<ImageDetailResponse> = {}): ImageDetailResponse {
  return {
    image_type: 'catalog',
    key: 'k1',
    filename: 'one.jpg',
    rating: 3,
    identity_aggregate_score: 7.2,
    identity_per_perspective: [],
    ...overrides,
  }
}

describe('ImageDetailModal', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.restoreAllMocks()
  })

  it('fetches detail on mount and renders catalog sections', async () => {
    const spy = vi
      .spyOn(ImagesAPI, 'getImageDetail')
      .mockResolvedValue(buildDetail())

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )

    expect(spy).toHaveBeenCalledWith('catalog', 'k1', undefined)
    await waitFor(() => {
      expect(screen.getByTestId('catalog-sections')).toBeInTheDocument()
    })
    expect(screen.getByTestId('catalog-sections').dataset.key).toBe('k1')
  })

  it('passes score_perspective query when provided', async () => {
    const spy = vi
      .spyOn(ImagesAPI, 'getImageDetail')
      .mockResolvedValue(buildDetail({ catalog_perspective_score: 8 }))

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="catalog"
        scorePerspectiveSlug="street"
        onClose={() => {}}
      />,
    )

    expect(spy).toHaveBeenCalledWith('catalog', 'k1', { score_perspective: 'street' })
    await waitFor(() => {
      expect(screen.getByTestId('catalog-sections')).toBeInTheDocument()
    })
  })

  it('routes instagram image_type to InstagramImageDetailSections', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(
      buildDetail({ image_type: 'instagram', key: 'ig1' }),
    )

    render(
      <ImageDetailModal
        imageType="instagram"
        imageKey="ig1"
        primaryScoreSource="none"
        onClose={() => {}}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('instagram-sections')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('catalog-sections')).toBeNull()
  })

  it('shows loading state while detail is in flight', () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockReturnValue(new Promise(() => {}))
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading image details')
  })

  it('renders an error message when detail fetch rejects', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockRejectedValue(new Error('boom'))

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    expect(await screen.findByText('boom')).toBeInTheDocument()
  })

  it('uses initialImage so header renders before detail resolves', async () => {
    let resolveFn: (v: ImageDetailResponse) => void = () => {}
    vi.spyOn(ImagesAPI, 'getImageDetail').mockReturnValue(
      new Promise<ImageDetailResponse>((r) => {
        resolveFn = r
      }),
    )

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        initialImage={{
          image_type: 'catalog',
          key: 'k1',
          filename: 'one.jpg',
          identity_aggregate_score: 9,
        }}
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    expect(screen.getByLabelText('Aggregate score 9')).toBeInTheDocument()

    resolveFn(buildDetail({ identity_aggregate_score: 7.2 }))
    await waitFor(() => {
      expect(screen.getByLabelText('Aggregate score 7.2')).toBeInTheDocument()
    })
  })

  it('has dialog role with aria-modal and a labelled title', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-labelledby')
  })

  it('ESC closes the modal', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    const onClose = vi.fn()
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={onClose}
      />,
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('backdrop click closes; inner click does not', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    const onClose = vi.fn()
    const { container } = render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={onClose}
      />,
    )
    const backdrop = container.querySelector('.fixed.inset-0') as HTMLElement
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(dialog)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Close button triggers onClose', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    const onClose = vi.fn()
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={onClose}
      />,
    )
    fireEvent.click(await screen.findByLabelText('Close'))
    expect(onClose).toHaveBeenCalled()
  })

  it('locks body scroll while mounted and restores on unmount', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    document.body.style.overflow = 'auto'
    const { unmount } = render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('auto')
  })

  it('dialog container uses the responsive sheet classes (mobile full-height, md centered)', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    const dialog = await screen.findByRole('dialog')
    expect(dialog.className).toContain('h-[100dvh]')
    expect(dialog.className).toContain('md:h-auto')
    expect(dialog.className).toContain('md:max-w-4xl')
  })

  it('re-fetches when a section reports data changed', async () => {
    const spy = vi
      .spyOn(ImagesAPI, 'getImageDetail')
      .mockResolvedValue(buildDetail())

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="identity"
        onClose={() => {}}
      />,
    )
    await waitFor(() => {
      expect(screen.getByTestId('catalog-sections')).toBeInTheDocument()
    })
    expect(spy).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('refetch'))
    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(2)
    })
  })
})
