import type { SelectFilterDescriptor } from '../types'
import { CONTROL } from '../styles'

export type SelectFilterProps = {
  descriptor: SelectFilterDescriptor
  value: unknown
  onChange: (value: unknown) => void
  disabled?: boolean
}

function displayValue(value: unknown): string {
  if (value === '' || value === undefined || value === null) return ''
  return String(value)
}

export function SelectFilter({ descriptor, value, onChange, disabled }: SelectFilterProps) {
  const className = [CONTROL, descriptor.className].filter(Boolean).join(' ')
  return (
    <select
      value={displayValue(value)}
      onChange={(e) => {
        const raw = e.target.value
        if (descriptor.numberValue) {
          onChange(raw === '' ? '' : Number(raw))
        } else {
          onChange(raw)
        }
      }}
      disabled={disabled}
      aria-label={descriptor.label}
      className={className}
    >
      {descriptor.options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}
