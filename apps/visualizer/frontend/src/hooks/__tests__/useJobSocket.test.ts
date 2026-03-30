import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useJobSocket } from '../useJobSocket'

const mockSocket = {
  on: vi.fn(),
  off: vi.fn(),
}

const mockConnect = vi.fn()
const mockDisconnect = vi.fn()

vi.mock('../../stores/socketStore', () => ({
  useSocketStore: vi.fn((selector) => {
    const state = {
      socket: mockSocket,
      connected: true,
      connect: mockConnect,
      disconnect: mockDisconnect,
    }
    return selector(state)
  }),
}))

describe('useJobSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('connects on mount and disconnects on unmount', () => {
    const { unmount } = renderHook(() => useJobSocket({}))
    expect(mockConnect).toHaveBeenCalledOnce()
    unmount()
    expect(mockDisconnect).toHaveBeenCalledOnce()
  })

  it('registers job_created and job_updated listeners', () => {
    const onCreated = vi.fn()
    const onUpdated = vi.fn()
    renderHook(() => useJobSocket({ onJobCreated: onCreated, onJobUpdated: onUpdated }))

    const onCalls = mockSocket.on.mock.calls
    const eventNames = onCalls.map(([name]: [string]) => name)
    expect(eventNames).toContain('job_created')
    expect(eventNames).toContain('job_updated')
  })

  it('cleans up listeners on unmount', () => {
    const { unmount } = renderHook(() => useJobSocket({ onJobCreated: vi.fn() }))
    unmount()
    const offCalls = mockSocket.off.mock.calls
    const eventNames = offCalls.map(([name]: [string]) => name)
    expect(eventNames).toContain('job_created')
    expect(eventNames).toContain('job_updated')
  })

  it('returns connected state', () => {
    const { result } = renderHook(() => useJobSocket({}))
    expect(result.current.connected).toBe(true)
  })
})
