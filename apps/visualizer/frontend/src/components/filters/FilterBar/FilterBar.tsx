import type { ReactNode } from 'react'
import type { FilterSchema, FilterDescriptor } from '../types'
import { descriptorDefault, defaultFormatValue, isDescriptorEnabled } from '../types'
import type { UseFiltersReturn } from '../../../hooks/useFilters'
import { ToggleFilter } from '../ToggleFilter'
import { SelectFilter } from '../SelectFilter'
import { DateRangeFilter } from '../DateRangeFilter'
import { SearchFilter } from '../SearchFilter'
import { FilterChip } from '../FilterChip'
import { Button } from '../../ui/Button/Button'
import { FILTER_CLEAR_ALL, FILTER_CHIP_REMOVE_ARIA } from '../../../constants/strings'

const ROW = 'flex flex-wrap gap-3 items-end'
const COL = 'flex flex-col gap-1.5'
const LABEL = 'text-xs font-medium text-text-tertiary'

function chipSourceValue(descriptor: FilterDescriptor, filters: UseFiltersReturn): unknown {
  if (descriptor.type === 'search') {
    return filters.rawValues[descriptor.key]
  }
  return filters.values[descriptor.key]
}

/** Framework default for date-range chips: `2024-01-01 → 2024-12-31`, or
 *  one-sided variants. */
function formatDateRangeValue(value: unknown): string {
  if (!value || typeof value !== 'object') return ''
  const v = value as { from?: unknown; to?: unknown }
  const from = typeof v.from === 'string' ? v.from : ''
  const to = typeof v.to === 'string' ? v.to : ''
  if (from && to) return `${from} → ${to}`
  if (from) return `from ${from}`
  if (to) return `to ${to}`
  return ''
}

/** Derive the chip label from `descriptor.options` by value match. Returns
 *  `null` when no option matches, so the caller can fall back. */
function labelFromOptions(
  options: ReadonlyArray<{ value: unknown; label: string }>,
  value: unknown,
): string | null {
  const match = options.find((o) => o.value === value)
  return match ? match.label : null
}

/**
 * Framework default chip formatter: each filter type knows how to render its
 * own value without the consumer supplying `formatValue`.
 *
 * `descriptor.formatValue` remains available as an escape hatch for schemas
 * that need custom rendering (e.g. look up a perspective's display name by
 * slug, which the options list can't express statically).
 */
function defaultChipLabel(descriptor: FilterDescriptor, value: unknown): string {
  switch (descriptor.type) {
    case 'toggle': {
      const fromOptions = labelFromOptions(descriptor.options, value)
      return fromOptions ?? defaultFormatValue(value)
    }
    case 'select': {
      // Empty-string / undefined values represent "no selection" and never
      // reach the chip row (isActive filters them out), so any mismatch
      // here is a genuine schema/value drift — fall back to string form.
      const fromOptions = labelFromOptions(descriptor.options, value)
      if (fromOptions !== null) return fromOptions
      // Compare by string too, since <select> values are strings but some
      // schemas carry numbers in the committed value (numberValue: true).
      const asString = typeof value === 'number' ? String(value) : null
      if (asString !== null) {
        const stringMatch = labelFromOptions(descriptor.options, asString)
        if (stringMatch !== null) return stringMatch
      }
      return defaultFormatValue(value)
    }
    case 'dateRange':
      return formatDateRangeValue(value)
    case 'search':
      return defaultFormatValue(value)
    default: {
      const _never: never = descriptor
      return _never
    }
  }
}

export type FilterBarProps = {
  schema: FilterSchema
  filters: UseFiltersReturn
  summary?: ReactNode
  disabled?: boolean
}

export function FilterBar({ schema, filters, summary, disabled }: FilterBarProps) {
  const chipRow =
    filters.activeCount > 0 ? (
      <div className="flex flex-wrap gap-2 mb-3">
        {schema
          .filter((d) => filters.isActive(d.key))
          .map((d) => {
            const source = chipSourceValue(d, filters)
            const display = d.formatValue ? d.formatValue(source) : defaultChipLabel(d, source)
            const chipLabel = d.chipLabel ?? d.label
            return (
              <FilterChip
                key={d.key}
                text={`${chipLabel}: ${display}`}
                removeAriaLabel={FILTER_CHIP_REMOVE_ARIA(chipLabel)}
                disabled={disabled}
                onRemove={() => filters.setValue(d.key, descriptorDefault(d))}
              />
            )
          })}
      </div>
    ) : null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">{summary}</div>
        {filters.activeCount > 0 && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={disabled}
            onClick={filters.clearAll}
          >
            {FILTER_CLEAR_ALL}
          </Button>
        )}
      </div>
      {chipRow}
      <div className={ROW}>
        {schema.map((d) => {
          const controlDisabled = Boolean(disabled) || !isDescriptorEnabled(d, filters.values)
          switch (d.type) {
            case 'toggle':
              return (
                <div key={d.key} className={COL}>
                  <span className={LABEL}>{d.label}</span>
                  <ToggleFilter
                    descriptor={d}
                    value={filters.values[d.key]}
                    onChange={(v) => filters.setValue(d.key, v)}
                    disabled={controlDisabled}
                  />
                </div>
              )
            case 'select':
              return (
                <div key={d.key} className={COL}>
                  <span className={LABEL}>{d.label}</span>
                  <SelectFilter
                    descriptor={d}
                    value={filters.values[d.key]}
                    onChange={(v) => filters.setValue(d.key, v)}
                    disabled={controlDisabled}
                  />
                </div>
              )
            case 'dateRange':
              return (
                <DateRangeFilter
                  key={d.key}
                  descriptor={d}
                  value={filters.values[d.key]}
                  onChange={(next) => filters.setValue(d.key, next)}
                  disabled={controlDisabled}
                />
              )
            case 'search':
              return (
                <div key={d.key} className={COL}>
                  <span className={LABEL}>{d.label}</span>
                  <SearchFilter
                    descriptor={d}
                    rawValue={filters.rawValues[d.key]}
                    onChange={(v) => filters.setValue(d.key, v)}
                    disabled={controlDisabled}
                  />
                </div>
              )
            default: {
              const _never: never = d
              return _never
            }
          }
        })}
      </div>
    </div>
  )
}
