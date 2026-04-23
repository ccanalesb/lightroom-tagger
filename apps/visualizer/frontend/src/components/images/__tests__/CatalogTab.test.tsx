import { Suspense, act } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CatalogTab } from '../CatalogTab'
import {
  CATALOG_FILTER_LABEL_KEYWORD,
  FILTER_DESCRIPTION_SEARCH_ARIA,
} from '../../../constants/strings'
import { deleteMatching } from '../../../data/cache'

const listCatalogMock = vi.fn()
const getCatalogMonthsMock = vi.fn()
const perspectivesListMock = vi.fn()

vi.mock('../../../services/api', () => ({
  ImagesAPI: {
    listCatalog: (...args: unknown[]) => listCatalogMock(...args),
    getCatalogMonths: (...args: unknown[]) => getCatalogMonthsMock(...args),
  },
  PerspectivesAPI: {
    list: (...args: unknown[]) => perspectivesListMock(...args),
  },
}))

describe('CatalogTab', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
    listCatalogMock.mockResolvedValue({ images: [], total: 0 })
    getCatalogMonthsMock.mockResolvedValue({ months: [] })
    perspectivesListMock.mockResolvedValue([])
  })

  it('renders catalog filter labels and calls listCatalog with pagination defaults', async () => {
    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    // Keyword filter label is rendered once schema mounts.
    await waitFor(() => {
      expect(screen.getAllByText(CATALOG_FILTER_LABEL_KEYWORD).length).toBeGreaterThan(0)
    })

    // Initial load fires listCatalog with limit + offset only (no filters set).
    await waitFor(() => {
      expect(listCatalogMock).toHaveBeenCalled()
    })
    const firstCall = listCatalogMock.mock.calls[0]?.[0] ?? {}
    expect(firstCall.limit).toBe(50)
    expect(firstCall.offset).toBe(0)
    expect(firstCall).not.toHaveProperty('posted')
    expect(firstCall).not.toHaveProperty('analyzed')
    expect(firstCall).not.toHaveProperty('keyword')
  })

  it('sends description_search in listCatalog after debounce when description search is committed', async () => {
    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getAllByText(CATALOG_FILTER_LABEL_KEYWORD).length).toBeGreaterThan(0)
    })
    listCatalogMock.mockClear()

    vi.useFakeTimers()
    const input = screen.getByLabelText(FILTER_DESCRIPTION_SEARCH_ARIA)
    act(() => {
      fireEvent.change(input, { target: { value: 'sunset' } })
    })
    act(() => {
      vi.advanceTimersByTime(350)
    })

    const withDesc = listCatalogMock.mock.calls.find(
      (call) => (call[0] as Record<string, unknown>)?.description_search === 'sunset',
    )
    expect(withDesc).toBeDefined()
    vi.useRealTimers()
  })
})
