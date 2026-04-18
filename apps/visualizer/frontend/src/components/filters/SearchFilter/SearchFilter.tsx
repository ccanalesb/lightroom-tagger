import { Input } from '../../ui/Input'
import type { SearchFilterDescriptor } from '../types'

export type SearchFilterProps = {
  descriptor: SearchFilterDescriptor
  rawValue: unknown
  onChange: (value: string) => void
  disabled?: boolean
}

export function SearchFilter({ descriptor, rawValue, onChange, disabled }: SearchFilterProps) {
  return (
    <Input
      type={descriptor.inputMode === 'text' ? 'text' : 'search'}
      placeholder={descriptor.placeholder ?? 'Search…'}
      value={String(rawValue ?? '')}
      onChange={(e) => onChange(e.target.value)}
      className={descriptor.className ?? 'h-9 min-w-[8rem] w-36'}
      aria-label={descriptor.ariaLabel ?? descriptor.label}
      disabled={disabled}
    />
  )
}
