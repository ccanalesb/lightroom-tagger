import { describe, it, expect, beforeEach } from 'vitest'
import { deleteMatching, getEntry, setEntry, type CacheEntry } from '../cache'
import { invalidate, invalidateAll } from '../invalidate'

function pending(): CacheEntry {
  return { status: 'pending', promise: Promise.resolve() }
}

beforeEach(() => {
  deleteMatching(() => true)
})

describe('invalidate', () => {
  it('invalidate removes entry for exact key', () => {
    const k = JSON.stringify(['x', 1])
    setEntry(k, pending())
    invalidate(['x', 1])
    expect(getEntry(k)).toBeUndefined()
  })

  it('invalidateAll removes only keys matching prefix', () => {
    setEntry('["users",1]', pending())
    setEntry('["users",1,"posts"]', pending())
    setEntry('["users",2]', pending())
    setEntry('["orgs",1]', pending())
    invalidateAll(['users', 1])
    expect(getEntry('["users",1]')).toBeUndefined()
    expect(getEntry('["users",1,"posts"]')).toBeUndefined()
    expect(getEntry('["users",2]')).toBeDefined()
    expect(getEntry('["orgs",1]')).toBeDefined()
  })
})
