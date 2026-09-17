import { useBackendHealthStore } from '../stores/backendHealthStore'

/** Default HTTP timeout for API requests (ms). */
export const API_REQUEST_TIMEOUT_MS = 15_000

export class RequestTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`Request timed out after ${Math.round(timeoutMs / 1000)}s`)
    this.name = 'RequestTimeoutError'
  }
}

/**
 * `fetch` with an AbortSignal deadline. Rejects with {@link RequestTimeoutError}
 * when the deadline elapses before the response headers arrive.
 */
export async function fetchWithTimeout(
  url: string,
  options?: RequestInit,
  timeoutMs = API_REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  const outerSignal = options?.signal
  if (outerSignal) {
    if (outerSignal.aborted) {
      window.clearTimeout(timeoutId)
      controller.abort()
    } else {
      outerSignal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  try {
    const response = await fetch(url, { ...options, signal: controller.signal })
    useBackendHealthStore.getState().reportHttpSuccess()
    return response
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      useBackendHealthStore.getState().reportHttpTimeout()
      throw new RequestTimeoutError(timeoutMs)
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }
}
