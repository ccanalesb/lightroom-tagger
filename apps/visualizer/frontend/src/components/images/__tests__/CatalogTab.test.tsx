import { Suspense, act } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CatalogTab } from '../CatalogTab'
import {
  ACTION_UNDO,
  CATALOG_FILTER_LABEL_KEYWORD,
  CATALOG_STACK_SHOW,
  CATALOG_STACK_SPLIT_OUT,
  CATALOG_STACK_MAKE_REPRESENTATIVE,
  CATALOG_STACK_CONFIRM_SPLIT_TITLE,
  CATALOG_STACK_CONFIRM_REP_TITLE,
  FILTER_DESCRIPTION_SEARCH_ARIA,
} from '../../../constants/strings'
import type { CatalogImage } from '../../../services/api'
import { deleteMatching } from '../../../data/cache'

const apiMocks = vi.hoisted(() => ({
  listCatalogMock: vi.fn(),
  getCatalogMonthsMock: vi.fn(),
  getStackMembersMock: vi.fn(),
  splitStackMemberMock: vi.fn(),
  setStackRepresentativeMock: vi.fn(),
  mergeStacksMock: vi.fn(),
  perspectivesListMock: vi.fn(),
}))

vi.mock('../../../services/api', () => ({
  ImagesAPI: {
    listCatalog: (...args: unknown[]) => apiMocks.listCatalogMock(...args),
    getCatalogMonths: (...args: unknown[]) => apiMocks.getCatalogMonthsMock(...args),
    getStackMembers: (...args: unknown[]) => apiMocks.getStackMembersMock(...args),
    splitStackMember: (...args: unknown[]) => apiMocks.splitStackMemberMock(...args),
    setStackRepresentative: (...args: unknown[]) => apiMocks.setStackRepresentativeMock(...args),
    mergeStacks: (...args: unknown[]) => apiMocks.mergeStacksMock(...args),
  },
  PerspectivesAPI: {
    list: (...args: unknown[]) => apiMocks.perspectivesListMock(...args),
  },
}))

function stackRepAndMember(): { rep: CatalogImage; member: CatalogImage } {
  const rep: CatalogImage = {
    id: 1,
    key: 'a/b/seed.jpg',
    filename: 'seed.jpg',
    filepath: '/a/b/seed.jpg',
    date_taken: '2024-01-01',
    rating: 3,
    pick: false,
    color_label: 'none',
    keywords: [],
    title: '',
    caption: '',
    copyright: '',
    width: 1000,
    height: 1000,
    instagram_posted: false,
    stack_id: 42,
    stack_member_count: 3,
    is_stack_representative: true,
  }
  const member: CatalogImage = {
    ...rep,
    id: 2,
    key: 'a/b/member.jpg',
    filename: 'member.jpg',
    is_stack_representative: false,
  }
  return { rep, member }
}

describe('CatalogTab', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
    apiMocks.listCatalogMock.mockResolvedValue({ images: [], total: 0 })
    apiMocks.getCatalogMonthsMock.mockResolvedValue({ months: [] })
    apiMocks.getStackMembersMock.mockResolvedValue({ items: [] })
    apiMocks.perspectivesListMock.mockResolvedValue([])
    apiMocks.splitStackMemberMock.mockResolvedValue({
      split_out_key: 'a/b/member.jpg',
      remaining_stack: {
        stack_id: 42,
        representative_key: 'a/b/seed.jpg',
        stack_member_count: 2,
        member_keys: ['a/b/seed.jpg', 'a/b/other.jpg'],
      },
      dissolved: false,
    })
    apiMocks.setStackRepresentativeMock.mockResolvedValue({
      stack: {
        stack_id: 42,
        representative_key: 'a/b/member.jpg',
        stack_member_count: 2,
        member_keys: [],
      },
    })
    apiMocks.mergeStacksMock.mockResolvedValue({
      stack: {
        stack_id: 42,
        representative_key: 'a/b/seed.jpg',
        stack_member_count: 4,
        member_keys: [],
      },
      merged_stack_id: 7,
    })
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
      expect(apiMocks.listCatalogMock).toHaveBeenCalled()
    })
    const firstCall = apiMocks.listCatalogMock.mock.calls[0]?.[0] ?? {}
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
    apiMocks.listCatalogMock.mockClear()

    vi.useFakeTimers()
    const input = screen.getByLabelText(FILTER_DESCRIPTION_SEARCH_ARIA)
    act(() => {
      fireEvent.change(input, { target: { value: 'sunset' } })
    })
    act(() => {
      vi.advanceTimersByTime(350)
    })

    const withDesc = apiMocks.listCatalogMock.mock.calls.find(
      (call) => (call[0] as Record<string, unknown>)?.description_search === 'sunset',
    )
    expect(withDesc).toBeDefined()
    vi.useRealTimers()
  })

  it('offers Show stack and fetches members when a stack representative row is present', async () => {
    const { rep, member } = stackRepAndMember()
    apiMocks.listCatalogMock.mockResolvedValue({ images: [rep], total: 1 })
    apiMocks.getStackMembersMock.mockResolvedValue({ items: [rep, member] })

    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    const show = await screen.findByRole('button', { name: CATALOG_STACK_SHOW })
    fireEvent.click(show)

    await waitFor(() => {
      expect(apiMocks.getStackMembersMock).toHaveBeenCalledWith(42)
    })
  })

  it('shows stack split/representative controls only in expanded stack strip', async () => {
    const { rep, member } = stackRepAndMember()
    apiMocks.listCatalogMock.mockResolvedValue({ images: [rep], total: 1 })
    apiMocks.getStackMembersMock.mockResolvedValue({ items: [rep, member] })

    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: CATALOG_STACK_SPLIT_OUT })).toBeNull()

    fireEvent.click(await screen.findByRole('button', { name: CATALOG_STACK_SHOW }))

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: CATALOG_STACK_SPLIT_OUT }).length).toBeGreaterThan(0)
    })
    expect(screen.getByRole('button', { name: CATALOG_STACK_MAKE_REPRESENTATIVE })).toBeTruthy()
  })

  it('confirm modal gates split: confirms before splitStackMember runs', async () => {
    const { rep, member } = stackRepAndMember()
    apiMocks.listCatalogMock.mockResolvedValue({ images: [rep], total: 1 })
    apiMocks.getStackMembersMock.mockResolvedValue({ items: [rep, member] })

    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: CATALOG_STACK_SHOW }))

    const splitStripButtons = await screen.findAllByRole('button', { name: CATALOG_STACK_SPLIT_OUT })
    fireEvent.click(splitStripButtons[0]!)

    expect(await screen.findByText(CATALOG_STACK_CONFIRM_SPLIT_TITLE)).toBeTruthy()
    expect(apiMocks.splitStackMemberMock).not.toHaveBeenCalled()

    const splitAll = screen.getAllByRole('button', { name: CATALOG_STACK_SPLIT_OUT })
    fireEvent.click(splitAll[splitAll.length - 1]!)

    await waitFor(() => {
      expect(apiMocks.splitStackMemberMock).toHaveBeenCalledWith(42, 'a/b/seed.jpg')
    })
  })

  it('representative change uses shared undo toast and undo calls setStackRepresentative again', async () => {
    const { rep, member } = stackRepAndMember()
    apiMocks.listCatalogMock.mockResolvedValue({ images: [rep], total: 1 })
    apiMocks.getStackMembersMock.mockResolvedValue({ items: [rep, member] })

    render(
      <MemoryRouter>
        <Suspense fallback={null}>
          <CatalogTab />
        </Suspense>
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: CATALOG_STACK_SHOW }))

    fireEvent.click(await screen.findByRole('button', { name: CATALOG_STACK_MAKE_REPRESENTATIVE }))

    expect(await screen.findByText(CATALOG_STACK_CONFIRM_REP_TITLE)).toBeTruthy()

    const makeRepButtons = screen.getAllByRole('button', { name: CATALOG_STACK_MAKE_REPRESENTATIVE })
    fireEvent.click(makeRepButtons[makeRepButtons.length - 1]!)

    await waitFor(() => {
      expect(apiMocks.setStackRepresentativeMock).toHaveBeenNthCalledWith(1, 42, 'a/b/member.jpg')
    })

    fireEvent.click(await screen.findByRole('button', { name: ACTION_UNDO }))

    await waitFor(() => {
      expect(apiMocks.setStackRepresentativeMock).toHaveBeenNthCalledWith(2, 42, 'a/b/seed.jpg')
    })
  })
})
