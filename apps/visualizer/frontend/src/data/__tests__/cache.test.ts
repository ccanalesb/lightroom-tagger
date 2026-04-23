import { describe, it, expect, beforeEach } from 'vitest'
import {
  deleteEntry,
  deleteMatching,
  getEntry,
  setEntry,
  type CacheEntry,
} from '../cache'

beforeEach(() => {
  deleteMatching(() => true)
})

describe('cache', () => {
  it('setEntry / getEntry round-trip', () => {
    const entry: CacheEntry = {
      status: 'fulfilled',
      promise: Promise.resolve(),
      value: 42,
    }
    setEntry('k', entry)
    expect(getEntry('k')).toBe(entry)
  })

  it('deleteEntry removes key', () => {
    setEntry('x', { status: 'pending', promise: Promise.resolve() })
    deleteEntry('x')
    expect(getEntry('x')).toBeUndefined()
  })

  it('deleteMatching removes only matching keys', () => {
    setEntry('a', { status: 'pending', promise: Promise.resolve() })
    setEntry('ab', { status: 'pending', promise: Promise.resolve() })
    setEntry('b', { status: 'pending', promise: Promise.resolve() })
    deleteMatching((k) => k.startsWith('a'))
    expect(getEntry('a')).toBeUndefined()
    expect(getEntry('ab')).toBeUndefined()
    expect(getEntry('b')).toBeDefined()
  })
})
