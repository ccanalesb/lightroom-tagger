import { deleteEntry, deleteMatching } from './cache'

export function invalidate(key: readonly unknown[]): void {
  deleteEntry(JSON.stringify(key))
}

export function invalidateAll(prefix: readonly unknown[]): void {
  const p = JSON.stringify(prefix).slice(0, -1)
  deleteMatching((k) => k.startsWith(p))
}
