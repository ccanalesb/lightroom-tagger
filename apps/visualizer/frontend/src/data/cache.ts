export type CacheEntryStatus = 'pending' | 'fulfilled' | 'rejected'

export interface CacheEntry {
  status: CacheEntryStatus
  promise: Promise<unknown>
  value?: unknown
  error?: unknown
}

const store = new Map<string, CacheEntry>()

export function getEntry(key: string): CacheEntry | undefined {
  return store.get(key)
}

export function setEntry(key: string, entry: CacheEntry): void {
  store.set(key, entry)
}

export function deleteEntry(key: string): void {
  store.delete(key)
}

export function deleteMatching(predicate: (key: string) => boolean): void {
  const keys: string[] = []
  for (const k of store.keys()) {
    if (predicate(k)) keys.push(k)
  }
  for (const k of keys) {
    store.delete(k)
  }
}
