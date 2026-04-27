import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchingTab } from '../MatchingTab'

const mocks = vi.hoisted(() => ({
  createJob: vi.fn(),
  invalidateAll: vi.fn(),
}))

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mocks.createJob(...args),
  },
  ImagesAPI: {
    listCatalogSimilarityGroups: vi.fn(),
  },
}))

vi.mock('../../../data', () => ({
  useQuery: () => ({ items: [], total: 0 }),
  invalidateAll: (...args: unknown[]) => mocks.invalidateAll(...args),
}))

vi.mock('../../../stores/matchOptionsContext', () => ({
  useMatchOptions: () => ({
    options: {
      threshold: 0.7,
      phashWeight: 0,
      descWeight: 0,
      visionWeight: 1,
      maxWorkers: 4,
      skipUndescribed: true,
      providerId: null,
      providerModel: null,
    },
    updateOption: vi.fn(),
    resetOptions: vi.fn(),
    weightsError: null,
  }),
}))

vi.mock('../../matching/AdvancedOptions', () => ({
  AdvancedOptions: () => <div data-testid="advanced-options" />,
}))

vi.mock('../../image-view', () => ({
  ImageTile: () => <div data-testid="image-tile" />,
  fromCatalogListRow: (row: unknown) => row,
}))

describe('MatchingTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createJob.mockResolvedValue({ id: 'job-sim', type: 'batch_catalog_similarity' })
    vi.spyOn(window, 'alert').mockImplementation(() => {})
  })

  it('enqueues catalog similarity as a batch job', async () => {
    render(<MatchingTab />)

    fireEvent.click(screen.getByRole('button', { name: 'Find Similar Photos' }))

    await waitFor(() => {
      expect(mocks.createJob).toHaveBeenCalledWith('batch_catalog_similarity', {
        min_similarity: 0.9,
        limit_per_seed: 8,
      })
    })
    expect(mocks.invalidateAll).toHaveBeenCalledWith(['catalog.similarity.groups'])
  })

  it('enqueues stack detection as a batch job', async () => {
    render(<MatchingTab />)

    fireEvent.click(screen.getByRole('button', { name: 'Detect Burst Stacks' }))

    await waitFor(() => {
      expect(mocks.createJob).toHaveBeenCalledWith('batch_stack_detect', { force: true })
    })
  })
})
