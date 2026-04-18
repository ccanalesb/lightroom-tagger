import type { ToggleFilterDescriptor } from '../types'
import { CONTROL } from '../styles'

export type ToggleFilterProps = {
  descriptor: ToggleFilterDescriptor
  value: unknown
  onChange: (value: unknown) => void
  disabled?: boolean
}

function defaultSerialize(value: unknown): string {
  if (value === undefined) return 'all'
  if (value === true) return 'true'
  if (value === false) return 'false'
  return String(value)
}

function defaultDeserialize(raw: string): unknown {
  if (raw === 'all') return undefined
  if (raw === 'true') return true
  if (raw === 'false') return false
  return raw
}

export function ToggleFilter({ descriptor, value, onChange, disabled }: ToggleFilterProps) {
  const serialize = descriptor.serialize ?? defaultSerialize
  const deserialize = descriptor.deserialize ?? defaultDeserialize
  return (
    <select
      value={serialize(value)}
      onChange={(e) => onChange(deserialize(e.target.value))}
      disabled={disabled}
      aria-label={descriptor.label}
      className={CONTROL}
    >
      {descriptor.options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}
