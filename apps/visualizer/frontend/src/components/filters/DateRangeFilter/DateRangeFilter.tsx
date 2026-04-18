import type { DateRangeFilterDescriptor, DateRangeValue } from '../types'
import { CONTROL } from '../styles'

export type DateRangeFilterProps = {
  descriptor: DateRangeFilterDescriptor
  value: unknown
  onChange: (next: DateRangeValue) => void
  disabled?: boolean
}

function coerce(value: unknown): DateRangeValue {
  if (value && typeof value === 'object') {
    const v = value as { from?: unknown; to?: unknown }
    return {
      from: typeof v.from === 'string' ? v.from : '',
      to: typeof v.to === 'string' ? v.to : '',
    }
  }
  return { from: '', to: '' }
}

const COL = 'flex flex-col gap-1.5'
const LABEL = 'text-xs font-medium text-text-tertiary'

export function DateRangeFilter({ descriptor, value, onChange, disabled }: DateRangeFilterProps) {
  const v = coerce(value)
  return (
    <>
      <div className={COL}>
        <span className={LABEL}>From</span>
        <input
          type="date"
          value={v.from}
          disabled={disabled}
          aria-label={`${descriptor.label} from`}
          className={CONTROL}
          onChange={(e) => onChange({ ...v, from: e.target.value })}
        />
      </div>
      <div className={COL}>
        <span className={LABEL}>To</span>
        <input
          type="date"
          value={v.to}
          disabled={disabled}
          aria-label={`${descriptor.label} to`}
          className={CONTROL}
          onChange={(e) => onChange({ ...v, to: e.target.value })}
        />
      </div>
    </>
  )
}
