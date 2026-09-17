import { create } from 'zustand'

interface BackendHealthState {
  /** True after an API request timed out; cleared on the next success. */
  httpBusy: boolean
  reportHttpTimeout: () => void
  reportHttpSuccess: () => void
}

export const useBackendHealthStore = create<BackendHealthState>((set) => ({
  httpBusy: false,
  reportHttpTimeout: () => set({ httpBusy: true }),
  reportHttpSuccess: () => set({ httpBusy: false }),
}))
