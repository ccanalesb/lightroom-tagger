import { Suspense } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { InstagramTab } from '../InstagramTab'
import { deleteMatching } from '../../../data/cache'

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
})
