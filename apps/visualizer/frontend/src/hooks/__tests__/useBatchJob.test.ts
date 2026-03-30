import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useBatchJob } from '../useBatchJob'

const mockCreate = vi.fn()

vi.mock('../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mockCreate(...args),
  },
}))

describe('useBatchJob', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should start in idle state', () => {
    const { result } = renderHook(() => useBatchJob())
    expect(result.current.job).toBeNull()
    expect(result.current.error).toBeNull()
    expect(result.current.isRunning).toBe(false)
  })

  it('should transition to running on start', async () => {
    mockCreate.mockResolvedValueOnce({ id: 'j1', status: 'pending', type: 'test' })
    const { result } = renderHook(() => useBatchJob())

    await act(async () => {
      await result.current.start('test_type', { key: 'value' })
    })

    expect(result.current.job).toEqual({ id: 'j1', status: 'pending', type: 'test' })
    expect(result.current.isRunning).toBe(true)
    expect(result.current.error).toBeNull()
  })

  it('should capture error on failed start', async () => {
    mockCreate.mockRejectedValueOnce(new Error('Server error'))
    const { result } = renderHook(() => useBatchJob())

    await act(async () => {
      await result.current.start('test_type', {})
    })

    expect(result.current.error).toBe('Server error')
    expect(result.current.isRunning).toBe(false)
  })

  it('should update job via onJobUpdate', async () => {
    mockCreate.mockResolvedValueOnce({ id: 'j1', status: 'pending', type: 'test' })
    const { result } = renderHook(() => useBatchJob())

    await act(async () => {
      await result.current.start('test_type', {})
    })

    act(() => {
      result.current.onJobUpdate({ id: 'j1', status: 'completed', type: 'test' } as never)
    })

    expect(result.current.job?.status).toBe('completed')
    expect(result.current.isRunning).toBe(false)
  })

  it('should ignore updates for other job ids', async () => {
    mockCreate.mockResolvedValueOnce({ id: 'j1', status: 'pending', type: 'test' })
    const { result } = renderHook(() => useBatchJob())

    await act(async () => {
      await result.current.start('test_type', {})
    })

    act(() => {
      result.current.onJobUpdate({ id: 'other', status: 'completed', type: 'test' } as never)
    })

    expect(result.current.job?.status).toBe('pending')
    expect(result.current.isRunning).toBe(true)
  })

  it('should clear job and error on dismiss', async () => {
    mockCreate.mockResolvedValueOnce({ id: 'j1', status: 'completed', type: 'test' })
    const { result } = renderHook(() => useBatchJob())

    await act(async () => {
      await result.current.start('test_type', {})
    })

    act(() => result.current.dismiss())

    expect(result.current.job).toBeNull()
    expect(result.current.error).toBeNull()
  })
})
