import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePageTab } from '../usePageTab'
import { usePageUiStore } from '../../stores/pageUiStore'
import { deleteMatching } from '../../data/cache'

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderPageTab(initialPath: string, storedTab: 'catalog') {
  usePageUiStore.setState({ imagesTab: storedTab })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/images"
          element={
            <>
              {children}
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )

  return renderHook(
    () =>
      usePageTab({
        pagePath: '/images',
        tabIds: ['catalog'] as const,
        defaultTab: 'catalog',
        storedTab: usePageUiStore((s) => s.imagesTab),
        setStoredTab: usePageUiStore((s) => s.setImagesTab),
      }),
    { wrapper },
  )
}

describe('usePageTab', () => {
  beforeEach(() => {
    usePageUiStore.setState({
      imagesTab: 'catalog',
      processingTab: 'analyze',
      filterStates: {},
    })
  })

  afterEach(() => {
    cleanup()
    deleteMatching(() => true)
    usePageUiStore.setState({
      imagesTab: 'catalog',
      processingTab: 'analyze',
      filterStates: {},
    })
  })

  it('uses catalog as the default images tab', async () => {
    const { result } = renderPageTab('/images', 'catalog')
    await waitFor(() => {
      expect(result.current.activeTab).toBe('catalog')
    })
  })

  it('redirects away from deleted tab query params', async () => {
    const { result } = renderPageTab('/images?tab=instagram', 'catalog')
    await waitFor(() => {
      expect(result.current.activeTab).toBe('catalog')
    })
    expect(usePageUiStore.getState().imagesTab).toBe('catalog')
  })
})
