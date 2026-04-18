import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterBar } from '../FilterBar'
import type { FilterSchema } from '../types'
import type { UseFiltersReturn } from '../../../hooks/useFilters'

const schema: FilterSchema = [
  {
    type: 'select',
    key: 'parent',
    label: 'Parent',
    options: [
      { value: '', label: 'Any' },
      { value: 'x', label: 'X' },
    ],
  },
  {
    type: 'select',
    key: 'child',
    label: 'Child',
    options: [
      { value: '', label: 'Any' },
      { value: '1', label: 'One' },
    ],
    enabledBy: { filterKey: 'parent', when: (v) => Boolean(v) },
  },
  {
    type: 'search',
    key: 'keyword',
    label: 'Keyword',
    chipLabel: 'Keyword',
  },
]

function makeFilters(partial: Partial<UseFiltersReturn>): UseFiltersReturn {
  return {
    values: {},
    rawValues: {},
    setValue: vi.fn(),
    setValues: vi.fn(),
    clearAll: vi.fn(),
    activeCount: 0,
    toQueryParams: () => ({}),
    isActive: () => false,
    ...partial,
  }
}

describe('FilterBar', () => {
  it('renders chip when a filter is active and ✕ invokes setValue with descriptor default', () => {
    const setValue = vi.fn()
    const filters = makeFilters({
      activeCount: 1,
      values: { keyword: 'cat' },
      rawValues: { keyword: 'cat' },
      isActive: (k) => k === 'keyword',
      setValue,
    })
    render(<FilterBar schema={schema} filters={filters} />)
    expect(screen.getByText(/Keyword: cat/i)).toBeInTheDocument()
    const removeBtn = screen.getByRole('button', { name: /Remove Keyword filter/i })
    fireEvent.click(removeBtn)
    expect(setValue).toHaveBeenCalledWith('keyword', '')
  })

  it('disables dependent child select when parent gate fails', () => {
    const filters = makeFilters({
      values: { parent: '', child: '1' },
      rawValues: { parent: '', child: '1' },
    })
    render(<FilterBar schema={schema} filters={filters} />)
    const childSelect = screen.getByLabelText('Child') as HTMLSelectElement
    expect(childSelect).toBeDisabled()
    const parentSelect = screen.getByLabelText('Parent') as HTMLSelectElement
    expect(parentSelect).not.toBeDisabled()
  })

  it('does not render Clear all when activeCount is zero', () => {
    const filters = makeFilters({ activeCount: 0 })
    render(<FilterBar schema={schema} filters={filters} />)
    expect(screen.queryByRole('button', { name: /Clear all/i })).not.toBeInTheDocument()
  })

  it('Clear all button invokes filters.clearAll', () => {
    const clearAll = vi.fn()
    const filters = makeFilters({ activeCount: 2, clearAll })
    render(<FilterBar schema={schema} filters={filters} />)
    fireEvent.click(screen.getByRole('button', { name: /Clear all/i }))
    expect(clearAll).toHaveBeenCalledTimes(1)
  })
})
