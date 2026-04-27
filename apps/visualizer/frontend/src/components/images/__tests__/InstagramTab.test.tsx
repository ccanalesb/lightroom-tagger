import { Suspense } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { InstagramTab } from '../InstagramTab'
import { deleteMatching } from '../../../data/cache'
import { BADGE_MATCHED } from '../../../constants/strings'

const listInstagramMock = vi.fn()
const getInstagramMonthsMock = vi.fn()

vi.mock('../../../services/api', () => ({
  ImagesAPI: {
    listInstagram: (...args: unknown[]) => listInstagramMock(...args),
    getInstagramMonths: (...args: unknown[]) => getInstagramMonthsMock(...args),
  },
}))

describe('InstagramTab', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
    listInstagramMock.mockResolvedValue({
      images: [],
      total: 0,
      pagination: { current_page: 1, total_pages: 1, has_more: false },
    })
    getInstagramMonthsMock.mockResolvedValue({ months: [] })
  })

  it('calls listInstagram with pagination defaults and no date_folder at baseline', async () => {
    render(
      <Suspense fallback={null}>
        <InstagramTab />
      </Suspense>,
    )

    await waitFor(() => {
      expect(listInstagramMock).toHaveBeenCalled()
    })
    const firstCall = listInstagramMock.mock.calls[0]?.[0] ?? {}
    expect(firstCall.limit).toBeGreaterThan(0)
    expect(firstCall.offset).toBe(0)
    expect(firstCall).not.toHaveProperty('date_folder')
  })

  it('renders the Date filter label once schema mounts', async () => {
    render(
      <Suspense fallback={null}>
        <InstagramTab />
      </Suspense>,
    )
    await waitFor(() => {
      expect(screen.getAllByText('Date').length).toBeGreaterThan(0)
    })
  })

  it('shows inline AI chip from ImageMetadataBadges for description-backed rows, not Described', async () => {
    listInstagramMock.mockResolvedValue({
      images: [
        {
          key: 'ig-1',
          local_path: '/p',
          filename: 'a.jpg',
          instagram_folder: 'f',
          source_folder: 'posts',
          date_folder: '202401',
          crawled_at: '2024-01-01T00:00:00Z',
          image_index: 0,
          total_in_post: 1,
          description: 'A scene description for search.',
        },
      ],
      total: 1,
      pagination: { current_page: 1, total_pages: 1, has_more: false },
    })
    render(
      <Suspense fallback={null}>
        <InstagramTab />
      </Suspense>,
    )
    await waitFor(() => {
      expect(screen.getByText('AI')).toBeInTheDocument()
    })
    expect(screen.queryByText('Described')).not.toBeInTheDocument()
  })

  it('shows Matched and match percent in the footer for catalog-linked images', async () => {
    listInstagramMock.mockResolvedValue({
      images: [
        {
          key: 'ig-2',
          local_path: '/p',
          filename: 'b.jpg',
          instagram_folder: 'f',
          source_folder: 'posts',
          date_folder: '202401',
          crawled_at: '2024-01-01T00:00:00Z',
          image_index: 0,
          total_in_post: 1,
          description: 'has text',
          matched_catalog_key: 'cat/k',
          match_score: 0.82,
        },
      ],
      total: 1,
      pagination: { current_page: 1, total_pages: 1, has_more: false },
    })
    render(
      <Suspense fallback={null}>
        <InstagramTab />
      </Suspense>,
    )
    await waitFor(() => {
      expect(screen.getByText(BADGE_MATCHED)).toBeInTheDocument()
    })
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('AI')).toBeInTheDocument()
  })
})
