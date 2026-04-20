import { useMemo } from 'react'
import type { ToggleFilterDescriptor, ToggleOption } from '../types'
import { CONTROL } from '../styles'
import { indexOfToken, indexOfValue, tokenForIndex } from './optionTokens'

export type ToggleFilterProps = {
  descriptor: ToggleFilterDescriptor
  value: unknown
  onChange: (value: unknown) => void
  disabled?: boolean
}

/**
 * Tri-state toggle control. The codec (value ↔ `<select>` string) is derived
 * entirely from `descriptor.options`, so consumers never write serialize /
 * deserialize for the common case.
 *
 * The descriptor's optional `serialize` / `deserialize` are honored as an
 * escape hatch for multi-state toggles whose rows don't fit the boolean
 * tri-state shape.
 */
export function ToggleFilter({ descriptor, value, onChange, disabled }: ToggleFilterProps) {
  const hasOverride = descriptor.serialize !== undefined && descriptor.deserialize !== undefined

  const codec = useMemo(() => {
    if (hasOverride) {
      return {
        serialize: descriptor.serialize as (v: unknown) => string,
        deserialize: descriptor.deserialize as (raw: string) => unknown,
        // In override mode the caller's serialize() is the authoritative
        // mapping from a row's value to its DOM string, so we re-use it for
        // each <option>'s `value` attribute too.
        optionValue: (opt: ToggleOption) =>
          (descriptor.serialize as (v: unknown) => string)(opt.value),
      }
    }
    return {
      serialize: (v: unknown) => tokenForIndex(indexOfValue(descriptor.options, v)),
      deserialize: (raw: string) => {
        const i = indexOfToken(raw)
        if (i === null) return descriptor.options[0]?.value
        return descriptor.options[i]?.value
      },
      optionValue: (_opt: ToggleOption, i: number = 0) => tokenForIndex(i),
    }
  }, [hasOverride, descriptor.options, descriptor.serialize, descriptor.deserialize])

  return (
    <select
      value={codec.serialize(value)}
      onChange={(e) => onChange(codec.deserialize(e.target.value))}
      disabled={disabled}
      aria-label={descriptor.label}
      className={CONTROL}
    >
      {descriptor.options.map((opt, i) => {
        const v = codec.optionValue(opt, i)
        return (
          <option key={v} value={v}>
            {opt.label}
          </option>
        )
      })}
    </select>
  )
}
