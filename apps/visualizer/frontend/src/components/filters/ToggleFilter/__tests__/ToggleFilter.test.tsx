import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ToggleFilter } from '../ToggleFilter'
import type { ToggleFilterDescriptor } from '../../types'

/**
 * These tests lock in the framework's auto-wiring contract for tri-state
 * toggles: a descriptor declaring `options` with `{ value: boolean | undefined, label }`
 * rows needs no `serialize` / `deserialize`, and emits the boolean/undefined
 * row value on change.
 */

const postedDescriptor: ToggleFilterDescriptor = {
  type: 'toggle',
  key: 'posted',
  label: 'Status',
  options: [
    { value: undefined, label: 'All' },
    { value: true, label: 'Posted' },
    { value: false, label: 'Not Posted' },
  ],
}

describe('ToggleFilter (framework-default codec)', () => {
  it('renders each option label and reflects the current committed value', () => {
    render(<ToggleFilter descriptor={postedDescriptor} value={true} onChange={vi.fn()} />)
    const select = screen.getByLabelText('Status') as HTMLSelectElement
    const selected = select.options[select.selectedIndex]
    expect(selected.textContent).toBe('Posted')
  })

  it('emits undefined when the "all" row is selected (no serialize declared)', () => {
    const onChange = vi.fn()
    render(<ToggleFilter descriptor={postedDescriptor} value={true} onChange={onChange} />)
    const select = screen.getByLabelText('Status') as HTMLSelectElement
    // Pick the All row by visible label, not by token.
    const allOption = Array.from(select.options).find((o) => o.textContent === 'All')!
    fireEvent.change(select, { target: { value: allOption.value } })
    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('emits the boolean value of the row when a non-default row is selected', () => {
    const onChange = vi.fn()
    render(<ToggleFilter descriptor={postedDescriptor} value={undefined} onChange={onChange} />)
    const select = screen.getByLabelText('Status') as HTMLSelectElement
    const notPosted = Array.from(select.options).find((o) => o.textContent === 'Not Posted')!
    fireEvent.change(select, { target: { value: notPosted.value } })
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it('honors caller-supplied serialize/deserialize as an escape hatch', () => {
    const onChange = vi.fn()
    const override: ToggleFilterDescriptor = {
      ...postedDescriptor,
      serialize: (v) => (v === undefined ? 'all' : v === true ? 'yes' : 'no'),
      deserialize: (raw) => (raw === 'all' ? undefined : raw === 'yes' ? true : false),
    }
    render(<ToggleFilter descriptor={override} value={undefined} onChange={onChange} />)
    const select = screen.getByLabelText('Status') as HTMLSelectElement
    // Override mode uses caller's tokens as <option value>.
    fireEvent.change(select, { target: { value: 'yes' } })
    expect(onChange).toHaveBeenCalledWith(true)
  })
})
