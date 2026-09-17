import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { RequestTimeoutError, fetchWithTimeout } from '../fetchWithTimeout'

describe('fetchWithTimeout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('resolves when fetch completes before the deadline', async () => {
    const response = new Response('ok')
    const fetchMock = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchWithTimeout('/api/status', undefined, 5_000)

    expect(result).toBe(response)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/status',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('rejects with RequestTimeoutError when the deadline elapses', async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        })
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const pending = fetchWithTimeout('/api/slow', undefined, 1_000)
    const timeoutAssertion = expect(pending).rejects.toThrow(RequestTimeoutError)
    const messageAssertion = expect(pending).rejects.toThrow('Request timed out after 1s')
    await vi.advanceTimersByTimeAsync(1_000)
    await timeoutAssertion
    await messageAssertion
  })
})
