import { describe, it, expect, beforeEach, vi } from 'vitest'
import { deleteMatching } from '../cache'
import { invalidate } from '../invalidate'
import { query } from '../query'

beforeEach(() => {
  deleteMatching(() => true)
  vi.clearAllMocks()
})

function catchThrown(fn: () => void): unknown {
  try {
    fn()
    return undefined
  } catch (e) {
    return e
  }
}

describe('query', () => {
  it('first call throws promise', () => {
    const fetcher = vi.fn(() => new Promise<number>(() => {}))
    const thrown = catchThrown(() => query(['first-throw'], fetcher))
    expect(thrown).toBeInstanceOf(Promise)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('pending throws same promise', () => {
    const fetcher = vi.fn(() => new Promise<number>(() => {}))
    const a = catchThrown(() => query(['same-promise'], fetcher)) as Promise<unknown>
    const b = catchThrown(() => query(['same-promise'], fetcher)) as Promise<unknown>
    expect(a).toBe(b)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('after resolve returns value', async () => {
    const fetcher = vi.fn(() => Promise.resolve(99))
    const p = catchThrown(() => query(['resolve'], fetcher)) as Promise<unknown>
    await expect(p).resolves.toBe(99)
    expect(query(['resolve'], fetcher)).toBe(99)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('after reject throws error', async () => {
    const err = new Error('nope')
    const fetcher = vi.fn(() => Promise.reject(err))
    const p = catchThrown(() => query(['reject'], fetcher)) as Promise<unknown>
    await expect(p).rejects.toBe(err)
    expect(() => query(['reject'], fetcher)).toThrow(err)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('after invalidate refetches', async () => {
    let n = 0
    const fetcher = vi.fn(() => Promise.resolve(++n))
    const p1 = catchThrown(() => query(['inv'], fetcher)) as Promise<unknown>
    await p1
    expect(query(['inv'], fetcher)).toBe(1)
    invalidate(['inv'])
    const p2 = catchThrown(() => query(['inv'], fetcher)) as Promise<unknown>
    await p2
    expect(query(['inv'], fetcher)).toBe(2)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
