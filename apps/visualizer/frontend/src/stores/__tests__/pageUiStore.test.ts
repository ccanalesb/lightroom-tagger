import { describe, it, expect, beforeEach } from 'vitest'
import { usePageUiStore } from '../pageUiStore'

describe('pageUiStore', () => {
  beforeEach(() => {
    usePageUiStore.setState({
      imagesTab: 'instagram',
      processingTab: 'matching',
      filterStates: {},
    })
  })

  it('stores and restores tab selections', () => {
    usePageUiStore.getState().setImagesTab('catalog')
    usePageUiStore.getState().setProcessingTab('jobs')
    expect(usePageUiStore.getState().imagesTab).toBe('catalog')
    expect(usePageUiStore.getState().processingTab).toBe('jobs')
  })

  it('stores and clears filter state by key', () => {
    const state = {
      raw: { posted: true },
      committed: { posted: true },
    }
    usePageUiStore.getState().setFilterState('images.catalog', state)
    expect(usePageUiStore.getState().getFilterState('images.catalog')).toEqual(state)
    usePageUiStore.getState().clearFilterState('images.catalog')
    expect(usePageUiStore.getState().getFilterState('images.catalog')).toBeUndefined()
  })
})
