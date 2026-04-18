import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  DEFAULT_SEARCH_DEBOUNCE_MS,
  descriptorDefault,
  isDescriptorEnabled,
  type FilterDescriptor,
  type FilterSchema,
} from '../components/filters/types'

export type UseFiltersReturn = {
  values: Record<string, unknown>
  rawValues: Record<string, unknown>
  setValue: (key: string, value: unknown) => void
  setValues: (patch: Record<string, unknown>) => void
  clearAll: () => void
  activeCount: number
  toQueryParams: () => Record<string, unknown>
  isActive: (key: string) => boolean
}

function keyToSnakeCase(key: string): string {
  return key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase()
}

function buildDefaults(schema: FilterSchema): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const d of schema) out[d.key] = descriptorDefault(d)
  return out
}

/** D-11: enforce enabledBy gates by resetting disabled descriptors to defaults. Loops until stable. */
function applyDependentClears(
  schema: FilterSchema,
  input: Record<string, unknown>,
): Record<string, unknown> {
  let current = input
  for (let i = 0; i < schema.length + 1; i += 1) {
    let changed = false
    const next: Record<string, unknown> = { ...current }
    for (const d of schema) {
      if (!isDescriptorEnabled(d, next)) {
        const def = descriptorDefault(d)
        if (next[d.key] !== def) {
          next[d.key] = def
          changed = true
        }
      }
    }
    if (!changed) return next
    current = next
  }
  return current
}

function isDateRangeEmpty(v: unknown): boolean {
  if (!v || typeof v !== 'object') return true
  const r = v as { from?: unknown; to?: unknown }
  const from = typeof r.from === 'string' ? r.from.trim() : ''
  const to = typeof r.to === 'string' ? r.to.trim() : ''
  return from === '' && to === ''
}

function paramsFromDescriptor(
  descriptor: FilterDescriptor,
  value: unknown,
): Record<string, unknown> | undefined {
  if (descriptor.toParam) {
    const result = descriptor.toParam(value)
    if (result === undefined) return undefined
    if (result !== null && typeof result === 'object' && !Array.isArray(result)) {
      return { ...(result as Record<string, unknown>) }
    }
    const key = descriptor.paramName ?? keyToSnakeCase(descriptor.key)
    return { [key]: result }
  }

  switch (descriptor.type) {
    case 'toggle': {
      if (value === undefined) return undefined
      const key = descriptor.paramName ?? keyToSnakeCase(descriptor.key)
      return { [key]: value }
    }
    case 'select': {
      if (value === '' || value === undefined || value === null) return undefined
      const key = descriptor.paramName ?? keyToSnakeCase(descriptor.key)
      if (descriptor.numberValue) return { [key]: Number(value) }
      return { [key]: value }
    }
    case 'dateRange': {
      if (isDateRangeEmpty(value)) return undefined
      const r = value as { from?: string; to?: string }
      const fromKey = descriptor.fromParamName ?? 'date_from'
      const toKey = descriptor.toParamName ?? 'date_to'
      const out: Record<string, unknown> = {}
      const from = typeof r.from === 'string' ? r.from.trim() : ''
      const to = typeof r.to === 'string' ? r.to.trim() : ''
      if (from) out[fromKey] = from
      if (to) out[toKey] = to
      return out
    }
    case 'search': {
      const raw = typeof value === 'string' ? value.trim() : ''
      if (raw === '') return undefined
      const key = descriptor.paramName ?? keyToSnakeCase(descriptor.key)
      return { [key]: raw }
    }
    default: {
      const _exhaustive: never = descriptor
      return _exhaustive
    }
  }
}

function descriptorIsActive(
  descriptor: FilterDescriptor,
  committed: Record<string, unknown>,
  raw: Record<string, unknown>,
): boolean {
  if (!isDescriptorEnabled(descriptor, committed)) return false
  if (descriptor.type === 'search') {
    const rv = raw[descriptor.key]
    return typeof rv === 'string' ? rv.trim() !== '' : Boolean(rv)
  }
  const def = descriptorDefault(descriptor)
  const cur = committed[descriptor.key]
  if (descriptor.type === 'dateRange') {
    const d = (def ?? { from: '', to: '' }) as { from: string; to: string }
    const c = (cur ?? { from: '', to: '' }) as { from?: string; to?: string }
    return (c.from ?? '') !== d.from || (c.to ?? '') !== d.to
  }
  return cur !== def
}

export function useFilters(schema: FilterSchema): UseFiltersReturn {
  const schemaRef = useRef(schema)
  schemaRef.current = schema

  const [rawValues, setRawValues] = useState<Record<string, unknown>>(() =>
    buildDefaults(schema),
  )
  const [committedValues, setCommittedValues] = useState<Record<string, unknown>>(() =>
    buildDefaults(schema),
  )

  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout> | undefined>>({})

  const descriptorByKey = useMemo(() => {
    const m = new Map<string, FilterDescriptor>()
    for (const d of schema) m.set(d.key, d)
    return m
  }, [schema])

  useEffect(() => {
    return () => {
      for (const k of Object.keys(debounceTimers.current)) {
        const t = debounceTimers.current[k]
        if (t) clearTimeout(t)
      }
      debounceTimers.current = {}
    }
  }, [])

  const commitSearchKey = useCallback((key: string, value: unknown) => {
    setCommittedValues((prev) => {
      const next = { ...prev, [key]: value }
      return applyDependentClears(schemaRef.current, next)
    })
  }, [])

  const setValues = useCallback(
    (patch: Record<string, unknown>) => {
      setRawValues((prevRaw) => {
        const mergedRaw = { ...prevRaw, ...patch }
        const nextRaw = applyDependentClears(schemaRef.current, mergedRaw)

        const committedPatch: Record<string, unknown> = {}
        for (const k of Object.keys(patch)) {
          const d = descriptorByKey.get(k)
          if (!d) continue
          if (d.type === 'search') {
            const existing = debounceTimers.current[k]
            if (existing) clearTimeout(existing)
            const ms = d.debounceMs ?? DEFAULT_SEARCH_DEBOUNCE_MS
            const value = nextRaw[k]
            debounceTimers.current[k] = setTimeout(() => {
              debounceTimers.current[k] = undefined
              commitSearchKey(k, value)
            }, ms)
          } else {
            committedPatch[k] = nextRaw[k]
          }
        }

        // Dependent-clear effects on non-search keys must also reach committed.
        for (const d of schemaRef.current) {
          if (d.type === 'search') continue
          if (prevRaw[d.key] !== nextRaw[d.key]) {
            committedPatch[d.key] = nextRaw[d.key]
          }
        }

        // Any search keys that got cleared by dependent gate should also cancel pending debounce
        // and commit the cleared default immediately.
        for (const d of schemaRef.current) {
          if (d.type !== 'search') continue
          const def = descriptorDefault(d)
          if (!isDescriptorEnabled(d, nextRaw) && nextRaw[d.key] !== prevRaw[d.key]) {
            const t = debounceTimers.current[d.key]
            if (t) {
              clearTimeout(t)
              debounceTimers.current[d.key] = undefined
            }
            nextRaw[d.key] = def
            committedPatch[d.key] = def
          }
        }

        if (Object.keys(committedPatch).length > 0) {
          setCommittedValues((prevCommitted) => {
            const merged = { ...prevCommitted, ...committedPatch }
            return applyDependentClears(schemaRef.current, merged)
          })
        }

        return nextRaw
      })
    },
    [commitSearchKey, descriptorByKey],
  )

  const setValue = useCallback(
    (key: string, value: unknown) => {
      setValues({ [key]: value })
    },
    [setValues],
  )

  const clearAll = useCallback(() => {
    for (const k of Object.keys(debounceTimers.current)) {
      const t = debounceTimers.current[k]
      if (t) clearTimeout(t)
      debounceTimers.current[k] = undefined
    }
    const defaults = buildDefaults(schemaRef.current)
    setRawValues(defaults)
    setCommittedValues(defaults)
  }, [])

  const toQueryParams = useCallback((): Record<string, unknown> => {
    const out: Record<string, unknown> = {}
    for (const d of schemaRef.current) {
      if (!isDescriptorEnabled(d, committedValues)) continue
      const params = paramsFromDescriptor(d, committedValues[d.key])
      if (!params) continue
      for (const k of Object.keys(params)) out[k] = params[k]
    }
    return out
  }, [committedValues])

  const activeCount = useMemo(() => {
    let n = 0
    for (const d of schema) {
      if (descriptorIsActive(d, committedValues, rawValues)) n += 1
    }
    return n
  }, [schema, committedValues, rawValues])

  const isActive = useCallback(
    (key: string): boolean => {
      const d = descriptorByKey.get(key)
      if (!d) return false
      return descriptorIsActive(d, committedValues, rawValues)
    },
    [descriptorByKey, committedValues, rawValues],
  )

  return {
    values: committedValues,
    rawValues,
    setValue,
    setValues,
    clearAll,
    activeCount,
    toQueryParams,
    isActive,
  }
}
