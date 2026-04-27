import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { MatchingTab } from '../MatchingTab'

const mocks = vi.hoisted(() => ({
  createJob: vi.fn(),
}))

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mocks.createJob(...args),
  },
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

function renderMatchingTab() {
  return render(
    <MemoryRouter>
      <MatchingTab />
    </MemoryRouter>,
  )
}

describe('MatchingTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createJob.mockResolvedValue({ id: 'job-vm', type: 'vision_match' })
    vi.spyOn(window, 'alert').mockImplementation(() => {})
  })

  it('sends clip_top_k in metadata', async () => {
    renderMatchingTab()

    fireEvent.click(screen.getByRole('button', { name: 'Start Vision Matching' }))

    await waitFor(() => {
      expect(mocks.createJob).toHaveBeenCalledWith(
        'vision_match',
        expect.objectContaining({ clip_top_k: 50 }),
      )
    })
  })

  it('clips top-k field has min and max bounds', () => {
    renderMatchingTab()

    const spin = screen.getByRole('spinbutton', { name: /clip shortlist size/i })
    expect(spin).toHaveAttribute('min', '1')
    expect(spin).toHaveAttribute('max', '500')
  })

  it('does not render Catalog Discovery Jobs or stack or similarity actions', () => {
    renderMatchingTab()

    expect(screen.queryByText('Catalog Discovery Jobs')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Find Similar Photos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Detect Burst Stacks' })).not.toBeInTheDocument()
  })
})
