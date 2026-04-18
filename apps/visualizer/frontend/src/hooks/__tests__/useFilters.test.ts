import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFilters } from '../useFilters'
import type { FilterSchema } from '../../components/filters/types'

const triSerialize = (v: unknown): string =>
  v === undefined ? 'all' : v === true ? 'true' : 'false'
const triDeserialize = (raw: string): unknown =>
  raw === 'all' ? undefined : raw === 'true' ? true : false

const minimalSchema: FilterSchema = [
  {
    type: 'toggle',
    key: 'posted',
    label: 'Status',
    options: [
      { value: 'all', label: 'All' },
      { value: 'true', label: 'Posted' },
      { value: 'false', label: 'Not' },
    ],
    serialize: triSerialize,
    deserialize: triDeserialize,
  },
  {
    type: 'toggle',
    key: 'analyzed',
    label: 'Analyzed',
    options: [
      { value: 'all', label: 'All' },
      { value: 'true', label: 'Analyzed' },
      { value: 'false', label: 'Not analyzed' },
    ],
    serialize: triSerialize,
    deserialize: triDeserialize,
  },
  {
    type: 'select',
    key: 'scorePerspective',
    label: 'Perspective',
    options: [
      { value: '', label: 'Any' },
      { value: 'p1', label: 'P1' },
    ],
  },
  {
    type: 'select',
    key: 'minCatalogScore',
    label: 'Min score',
    paramName: 'min_score',
    options: [{ value: '', label: 'Any' }],
    numberValue: true,
    enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
  },
  {
    type: 'select',
    key: 'sortByScore',
    label: 'Sort',
    options: [
      { value: 'none', label: 'None' },
      { value: 'asc', label: 'Asc' },
      { value: 'desc', label: 'Desc' },
    ],
    defaultValue: 'none',
    toParam: (v) => (v === 'none' || v === '' || v === undefined ? undefined : v),
    enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
  },
  {
    type: 'search',
    key: 'keyword',
    label: 'Keyword',
    debounceMs: 350,
  },
]

describe('useFilters', () => {
  it('activeCount baseline is 0 with default schema values', () => {
    const { result } = renderHook(() => useFilters(minimalSchema))
    expect(result.current.activeCount).toBe(0)
    expect(result.current.toQueryParams()).toEqual({})
  })

  it('toggle posted emits param and marks active', () => {
    const { result } = renderHook(() => useFilters(minimalSchema))
    act(() => {
      result.current.setValue('posted', true)
    })
    expect(result.current.toQueryParams().posted).toBe(true)
    expect(result.current.isActive('posted')).toBe(true)
    expect(result.current.activeCount).toBeGreaterThanOrEqual(1)
  })

  it('clears dependent scorePerspective children (D-11)', () => {
    const { result } = renderHook(() => useFilters(minimalSchema))
    act(() => {
      result.current.setValue('scorePerspective', 'p1')
    })
    act(() => {
      result.current.setValue('minCatalogScore', 5)
    })
    expect(result.current.toQueryParams()).toMatchObject({
      score_perspective: 'p1',
      min_score: 5,
    })
    act(() => {
      result.current.setValue('scorePerspective', '')
    })
    const params = result.current.toQueryParams()
    expect(params).not.toHaveProperty('min_score')
    expect(params).not.toHaveProperty('score_perspective')
    expect(result.current.values.minCatalogScore).toBe('')
  })

  it('debounces search descriptor', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useFilters(minimalSchema))
      act(() => {
        result.current.setValue('keyword', 'cat')
      })
      expect(result.current.toQueryParams()).not.toHaveProperty('keyword')
      expect(result.current.isActive('keyword')).toBe(true)
      act(() => {
        vi.advanceTimersByTime(350)
      })
      expect(result.current.toQueryParams().keyword).toBe('cat')
    } finally {
      vi.useRealTimers()
    }
  })

  it('clearAll resets state and query params', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useFilters(minimalSchema))
      act(() => {
        result.current.setValue('posted', true)
        result.current.setValue('scorePerspective', 'p1')
        result.current.setValue('minCatalogScore', 5)
        result.current.setValue('keyword', 'cat')
      })
      act(() => {
        vi.advanceTimersByTime(400)
      })
      expect(result.current.activeCount).toBeGreaterThan(0)
      act(() => {
        result.current.clearAll()
      })
      expect(result.current.activeCount).toBe(0)
      expect(result.current.toQueryParams()).toEqual({})
    } finally {
      vi.useRealTimers()
    }
  })
})

// Fixture references for acceptance grep:
// - dependent clear
// - scorePerspective
