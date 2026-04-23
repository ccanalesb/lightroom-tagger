import { getEntry, setEntry, type CacheEntry } from './cache'

export function query<T>(key: readonly unknown[], fetcher: () => Promise<T>): T {
  const k = JSON.stringify(key)
  let entry = getEntry(k)
  if (!entry) {
    const created: CacheEntry = {
      status: 'pending',
      promise: null as unknown as Promise<unknown>,
    }
    const promise = fetcher()
      .then((v) => {
        created.status = 'fulfilled'
        created.value = v
        return v
      })
      .catch((e) => {
        created.status = 'rejected'
        created.error = e
        throw e
      })
    created.promise = promise
    setEntry(k, created)
    throw promise
  }
  if (entry.status === 'pending') {
    throw entry.promise
  }
  if (entry.status === 'fulfilled') {
    return entry.value as T
  }
  throw entry.error
}
