import { create } from 'zustand'

export const IMAGES_TAB_IDS = ['instagram', 'catalog', 'matches'] as const
export type ImagesTabId = (typeof IMAGES_TAB_IDS)[number]

export const PROCESSING_TAB_IDS = [
  'matching',
  'analyze',
  'perspectives',
  'cache',
  'jobs',
  'providers',
  'settings',
] as const
export type ProcessingTabId = (typeof PROCESSING_TAB_IDS)[number]

export const FILTER_PERSIST_KEYS = {
  imagesInstagram: 'images.instagram',
  imagesCatalog: 'images.catalog',
  imagesMatches: 'images.matches',
} as const

export type PersistedFilterState = {
  raw: Record<string, unknown>
  committed: Record<string, unknown>
}

type PageUiState = {
  imagesTab: ImagesTabId
  processingTab: ProcessingTabId
  filterStates: Record<string, PersistedFilterState>
  setImagesTab: (tab: ImagesTabId) => void
  setProcessingTab: (tab: ProcessingTabId) => void
  getFilterState: (key: string) => PersistedFilterState | undefined
  setFilterState: (key: string, state: PersistedFilterState) => void
  clearFilterState: (key: string) => void
}

export const usePageUiStore = create<PageUiState>((set, get) => ({
  imagesTab: 'instagram',
  processingTab: 'matching',
  filterStates: {},
  setImagesTab: (tab) => set({ imagesTab: tab }),
  setProcessingTab: (tab) => set({ processingTab: tab }),
  getFilterState: (key) => get().filterStates[key],
  setFilterState: (key, state) =>
    set((prev) => ({
      filterStates: { ...prev.filterStates, [key]: state },
    })),
  clearFilterState: (key) =>
    set((prev) => {
      const { [key]: _removed, ...rest } = prev.filterStates
      return { filterStates: rest }
    }),
}))
