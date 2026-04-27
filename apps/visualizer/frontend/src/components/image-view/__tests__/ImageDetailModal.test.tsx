import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { CatalogImage, ImageDetailResponse } from '../../../services/api'
import { deleteMatching } from '../../../data/cache'
import {
  CATALOG_STACK_CONFIRM_REP_TITLE,
  CATALOG_STACK_MAKE_REPRESENTATIVE,
} from '../../../constants/strings'

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

function buildCatalogImage(overrides: Partial<CatalogImage> = {}): CatalogImage {
  return {
    id: 1,
    key: 'k1',
    filename: 'one.jpg',
    filepath: '/one.jpg',
    date_taken: '2026-01-01',
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

  it('does not expose on-demand visual similarity from the detail modal', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(buildDetail())
    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="catalog"
        onClose={() => {}}
      />,
    )
    await waitFor(() => {
      expect(screen.getByTestId('catalog-sections')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /more like this/i })).toBeNull()
  })

  it('lets the representative choose another stack member in the modal', async () => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(
      buildDetail({ stack_id: 42, stack_member_count: 2, is_stack_representative: true }),
    )
    vi.spyOn(ImagesAPI, 'getStackMembers').mockResolvedValue({
      items: [
        buildCatalogImage({
          key: 'k1',
          filename: 'one.jpg',
          stack_id: 42,
          stack_member_count: 2,
          is_stack_representative: true,
        }),
        buildCatalogImage({
          id: 2,
          key: 'k2',
          filename: 'two.jpg',
          stack_id: 42,
          stack_member_count: 2,
          is_stack_representative: false,
        }),
      ],
    })
    const repSpy = vi.spyOn(ImagesAPI, 'setStackRepresentative').mockResolvedValue({
      stack: {
        stack_id: 42,
        representative_key: 'k2',
        stack_member_count: 2,
        member_keys: ['k1', 'k2'],
      },
    })

    render(
      <ImageDetailModal
        imageType="catalog"
        imageKey="k1"
        primaryScoreSource="catalog"
        onClose={() => {}}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: CATALOG_STACK_MAKE_REPRESENTATIVE }))
    expect(await screen.findByText(CATALOG_STACK_CONFIRM_REP_TITLE)).toBeInTheDocument()
    const confirmButtons = screen.getAllByRole('button', { name: CATALOG_STACK_MAKE_REPRESENTATIVE })
    fireEvent.click(confirmButtons[confirmButtons.length - 1]!)

    await waitFor(() => {
      expect(repSpy).toHaveBeenCalledWith(42, 'k2')
    })
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
