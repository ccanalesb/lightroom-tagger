import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePageTab } from '../usePageTab'
import { usePageUiStore } from '../../stores/pageUiStore'

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderPageTab(
  initialPath: string,
  storedTab: 'instagram' | 'catalog' | 'matches',
) {
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
        tabIds: ['instagram', 'catalog', 'matches'] as const,
        defaultTab: 'instagram',
        storedTab: usePageUiStore((s) => s.imagesTab),
        setStoredTab: usePageUiStore((s) => s.setImagesTab),
      }),
    { wrapper },
  )
}

describe('usePageTab', () => {
  beforeEach(() => {
    usePageUiStore.setState({
      imagesTab: 'instagram',
      processingTab: 'matching',
      filterStates: {},
    })
  })

  it('restores stored tab when landing without ?tab=', async () => {
    const { result } = renderPageTab('/images', 'catalog')
    await waitFor(() => {
      expect(result.current.activeTab).toBe('catalog')
    })
  })

  it('prefers explicit URL tab over stored tab', () => {
    const { result } = renderPageTab('/images?tab=matches', 'catalog')
    expect(result.current.activeTab).toBe('matches')
    expect(usePageUiStore.getState().imagesTab).toBe('matches')
  })
})
