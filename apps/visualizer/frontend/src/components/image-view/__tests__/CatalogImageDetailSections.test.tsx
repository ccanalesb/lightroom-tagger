import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Suspense } from 'react'
import { render, screen, fireEvent, waitFor, within, cleanup, act } from '@testing-library/react'
import type { Job } from '../../../types/job'
import { deleteMatching } from '../../../data/cache'
import {
  IMAGE_DETAILS_DESCRIPTIVE_TECHNICAL,
  IMAGE_DETAILS_PERSPECTIVE_ANALYSIS,
} from '../../../constants/strings'
import { CatalogImageDetailSections } from '../CatalogImageDetailSections'
import type { ImageView } from '../../../services/api'

const mockCreate = vi.fn()
const mockGetDescription = vi.fn()
const mockGetDefaults = vi.fn()
const mockListPerspectives = vi.fn()
const mockGetCurrentScores = vi.fn()

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mockCreate(...args),
  },
  DescriptionsAPI: {
    get: (...args: unknown[]) => mockGetDescription(...args),
  },
  ProvidersAPI: {
    getDefaults: (...args: unknown[]) => mockGetDefaults(...args),
  },
  PerspectivesAPI: {
    list: (...args: unknown[]) => mockListPerspectives(...args),
  },
  ScoresAPI: {
    getCurrent: (...args: unknown[]) => mockGetCurrentScores(...args),
    getHistory: vi.fn().mockResolvedValue({ history: [] }),
  },
}))

vi.mock('../../ui/ProviderModelSelect', () => ({
  ProviderModelSelect: () => null,
}))

let capturedOnJobUpdated: ((job: Job) => void) | undefined

vi.mock('../../../hooks/useJobSocket', () => ({
  useJobSocket: (opts: { onJobUpdated?: (job: Job) => void }) => {
    capturedOnJobUpdated = opts.onJobUpdated
    return { connected: true, socket: null }
  },
}))

const BASE_IMAGE: ImageView = {
  image_type: 'catalog',
  key: 'photos/test.jpg',
  filename: 'test.jpg',
}

function renderSections(overrides: Partial<ImageView> = {}) {
  return render(
    <Suspense fallback={null}>
      <CatalogImageDetailSections image={{ ...BASE_IMAGE, ...overrides }} />
    </Suspense>,
  )
}

describe('CatalogImageDetailSections — modal two-section layout', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    capturedOnJobUpdated = undefined
    mockCreate.mockReset()
    mockGetDescription.mockReset()
    mockGetDefaults.mockReset()
    mockListPerspectives.mockReset()
    mockGetCurrentScores.mockReset()

    mockGetDefaults.mockResolvedValue({
      description: { provider: 'ollama', model: 'llava' },
    })
    mockListPerspectives.mockResolvedValue([
      { slug: 'street', display_name: 'Street' },
    ])
    mockGetDescription.mockResolvedValue({
      description: {
        summary: 'A quiet alley at dusk.',
        composition: { techniques: ['leading_lines'] },
        technical: { mood: 'moody' },
        subjects: ['alley'],
        perspectives: {
          street: { analysis: 'blob rationale', score: 9 },
        },
        best_perspective: 'street',
        model_used: 'test-model',
      },
    })
    mockGetCurrentScores.mockResolvedValue({
      current: [
        {
          perspective_slug: 'street',
          score: 7,
          rationale: 'Scores-table rationale',
          model_used: 'score-model',
          prompt_version: 'v1',
          scored_at: '2026-01-01T00:00:00Z',
          is_current: true,
        },
      ],
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders descriptive and perspective sections independently', async () => {
    renderSections()

    expect(await screen.findByRole('heading', { name: IMAGE_DETAILS_DESCRIPTIVE_TECHNICAL })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: IMAGE_DETAILS_PERSPECTIVE_ANALYSIS })).toBeInTheDocument()
  })

  it('shows descriptive content without blob perspective scores', async () => {
    renderSections()

    await screen.findByText('A quiet alley at dusk.')
    expect(screen.getByText(/moody/)).toBeInTheDocument()
    expect(screen.queryByText(/blob rationale/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Street 9/)).not.toBeInTheDocument()
  })

  it('sources perspective analysis from image_scores', async () => {
    renderSections()

    await screen.findByText('Scores-table rationale')
    const perspectiveHeading = screen.getByRole('heading', {
      name: IMAGE_DETAILS_PERSPECTIVE_ANALYSIS,
    })
    const perspectiveSection = perspectiveHeading.parentElement as HTMLElement
    const scoped = within(perspectiveSection)
    expect(scoped.getByText('Street')).toBeInTheDocument()
    expect(scoped.getByText('7 / 10')).toBeInTheDocument()
    expect(scoped.getByText('Scores-table rationale')).toBeInTheDocument()
  })
})

describe('CatalogImageDetailSections — scoring regenerate control', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    capturedOnJobUpdated = undefined
    mockCreate.mockReset()
    mockGetDescription.mockReset()
    mockGetDefaults.mockReset()
    mockListPerspectives.mockReset()
    mockGetCurrentScores.mockReset()

    mockGetDefaults.mockResolvedValue({
      description: { provider: 'ollama', model: 'llava' },
    })
    mockListPerspectives.mockResolvedValue([
      { slug: 'street', display_name: 'Street' },
    ])
    mockGetDescription.mockResolvedValue({ description: null })
    mockGetCurrentScores.mockResolvedValue({
      current: [
        {
          perspective_slug: 'street',
          score: 7,
          rationale: 'Initial rationale',
          model_used: 'score-model',
          prompt_version: 'v1',
          scored_at: '2026-01-01T00:00:00Z',
          is_current: true,
        },
      ],
    })
    mockCreate.mockResolvedValue({ id: 'score-job-1', type: 'single_score', status: 'running' })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('fires single_score with force and refreshes the perspective section', async () => {
    mockGetCurrentScores
      .mockResolvedValueOnce({
        current: [
          {
            perspective_slug: 'street',
            score: 7,
            rationale: 'Initial rationale',
            model_used: 'score-model',
            prompt_version: 'v1',
            scored_at: '2026-01-01T00:00:00Z',
            is_current: true,
          },
        ],
      })
      .mockResolvedValueOnce({
        current: [
          {
            perspective_slug: 'street',
            score: 9,
            rationale: 'Refreshed rationale',
            model_used: 'score-model',
            prompt_version: 'v2',
            scored_at: '2026-01-02T00:00:00Z',
            is_current: true,
          },
        ],
      })

    renderSections()

    await screen.findByText('Initial rationale')
    const perspectiveHeading = screen.getByRole('heading', {
      name: IMAGE_DETAILS_PERSPECTIVE_ANALYSIS,
    })
    const perspectiveSection = perspectiveHeading.parentElement as HTMLElement
    const regenerate = within(perspectiveSection).getByRole('button', { name: 'Regenerate' })
    fireEvent.click(regenerate)

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('single_score', {
        image_key: BASE_IMAGE.key,
        image_type: 'catalog',
        force: true,
        provider_id: 'ollama',
        provider_model: 'llava',
      })
    })

    await act(async () => {
      capturedOnJobUpdated?.({
        id: 'score-job-1',
        type: 'single_score',
        status: 'completed',
      } as Job)
    })

    await waitFor(() => {
      expect(mockGetCurrentScores.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    expect(await within(perspectiveSection).findByText('Refreshed rationale')).toBeInTheDocument()
  })
})
