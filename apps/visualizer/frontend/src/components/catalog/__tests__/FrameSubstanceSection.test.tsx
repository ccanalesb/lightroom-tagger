import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Suspense } from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { deleteMatching } from '../../../data/cache'
import { FrameSubstanceSection } from '../FrameSubstanceSection'
import type { FrameSubstanceResponse } from '../../../services/api'

const mockGet = vi.fn()
const mockCreateOverride = vi.fn()
const mockDeleteOverride = vi.fn()
const mockAddCull = vi.fn()
const mockRemoveCull = vi.fn()

vi.mock('../../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/api')>()
  return {
    ...actual,
    FrameSubstanceAPI: {
      get: (...args: unknown[]) => mockGet(...args),
      createOverride: (...args: unknown[]) => mockCreateOverride(...args),
      deleteOverride: (...args: unknown[]) => mockDeleteOverride(...args),
      addCullKeyword: (...args: unknown[]) => mockAddCull(...args),
      removeCullKeyword: (...args: unknown[]) => mockRemoveCull(...args),
    },
  }
})

function basePayload(overrides: Partial<FrameSubstanceResponse> = {}): FrameSubstanceResponse {
  return {
    image_key: '2024-01-01_photo.jpg',
    has_detection_run: true,
    verdict: 'void',
    unknown_reason: null,
    detector_version: 'v1',
    judged_at: '2024-01-01T00:00:00+00:00',
    is_stale: false,
    has_override: false,
    flagged: true,
    has_cull_keyword: false,
    instrument: {
      kind: 'pixel_detector',
      verdict: 'void',
      tier: 'A',
      advisory: false,
    },
    restore_tier: 'A',
    catalog_write_available: true,
    catalog_write_unavailable_reason: null,
    ...overrides,
  }
}

function renderSection() {
  return render(
    <Suspense fallback={null}>
      <FrameSubstanceSection imageKey="2024-01-01_photo.jpg" />
    </Suspense>,
  )
}

describe('FrameSubstanceSection', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    mockGet.mockReset()
    mockCreateOverride.mockReset()
    mockDeleteOverride.mockReset()
    mockAddCull.mockReset()
    mockRemoveCull.mockReset()
  })

  afterEach(() => {
    cleanup()
    deleteMatching(() => true)
  })

  it('shows no-run message when unjudged', async () => {
    mockGet.mockResolvedValue(
      basePayload({
        verdict: null,
        has_detection_run: false,
        flagged: false,
        instrument: null,
        restore_tier: null,
      }),
    )
    renderSection()
    expect(
      await screen.findByText(/Not judged yet/i),
    ).toBeInTheDocument()
  })

  it('warns Tier A restore needs rescore and not Tier B', async () => {
    mockGet.mockResolvedValue(basePayload())
    const { unmount } = renderSection()
    expect(await screen.findByText(/next scoring run/i)).toBeInTheDocument()
    unmount()
    cleanup()
    deleteMatching(() => true)

    mockGet.mockResolvedValue(
      basePayload({
        verdict: 'illegible',
        instrument: {
          kind: 'pixel_detector',
          verdict: 'illegible',
          tier: 'B',
          advisory: false,
        },
        restore_tier: 'B',
      }),
    )
    renderSection()
    await screen.findByText(/illegible frame/i)
    expect(screen.queryByText(/next scoring run/i)).not.toBeInTheDocument()
  })

  it('labels excusal channel as advisory', async () => {
    mockGet.mockResolvedValue(
      basePayload({
        verdict: 'ok',
        flagged: false,
        instrument: {
          kind: 'excusal_channel',
          verdict: null,
          tier: null,
          advisory: true,
        },
        restore_tier: null,
      }),
    )
    renderSection()
    expect(
      await screen.findByText(/Advisory excusal hint/i),
    ).toBeInTheDocument()
  })

  it('disables cull controls when catalog unavailable', async () => {
    mockGet.mockResolvedValue(
      basePayload({
        catalog_write_available: false,
        catalog_write_unavailable_reason: 'Close Lightroom before writing to catalog.',
      }),
    )
    renderSection()
    const button = await screen.findByRole('button', { name: /Mark for cull/i })
    expect(button).toBeDisabled()
    expect(screen.getByText(/Close Lightroom/i)).toBeInTheDocument()
  })

  it('calls override API on restore', async () => {
    mockGet.mockResolvedValue(basePayload())
    mockCreateOverride.mockResolvedValue({ image_key: '2024-01-01_photo.jpg', has_override: true })
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /Restore to ranking/i }))
    await waitFor(() => expect(mockCreateOverride).toHaveBeenCalledWith('2024-01-01_photo.jpg'))
  })
})
