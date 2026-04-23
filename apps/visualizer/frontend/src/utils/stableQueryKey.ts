/** Deterministic JSON for cache keys (sorted object keys). */
export function stableSerializeRecord(obj: Record<string, unknown>): string {
  const keys = Object.keys(obj).sort()
  const out: Record<string, unknown> = {}
  for (const k of keys) out[k] = obj[k]
  return JSON.stringify(out)
}
