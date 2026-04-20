export type DateRangeValue = { from: string; to: string }

export type SelectOption = { value: string; label: string }

/** A tri-state toggle row. The framework derives `serialize` / `deserialize`
 *  and the chip label from these rows, so consumers don't hand-wire codecs. */
export type ToggleOption = { value: boolean | undefined; label: string }

/** Parent gate: when `when` returns false, control is disabled and value is ignored for activeCount / toQueryParams (D-03, D-09). */
export type EnabledBy = {
  filterKey: string
  when: (parentValue: unknown) => boolean
}

type BaseDescriptor = {
  key: string
  label: string
  chipLabel?: string
  formatValue?: (value: unknown) => string
  defaultValue?: unknown
  paramName?: string
  toParam?: (value: unknown) => unknown | undefined
  enabledBy?: EnabledBy
}

export type ToggleFilterDescriptor = BaseDescriptor & {
  type: 'toggle'
  /** Three rows for the tri-state control. Each row carries its own value
   *  (`undefined | true | false`) and label. The framework derives both the
   *  `<select>` codec and the chip label from these rows, so consumers don't
   *  need `serialize` / `deserialize` / `formatValue`. */
  options: ToggleOption[]
  /** Committed value: undefined = "all", true/false map to the two arms (posted / analyzed). */
  defaultValue?: boolean | undefined
  /** Optional override for non-standard toggles. The framework default works
   *  for any tri-state built from `options`. */
  serialize?: (value: unknown) => string
  deserialize?: (raw: string) => unknown
}

export type SelectFilterDescriptor = BaseDescriptor & {
  type: 'select'
  options: SelectOption[]
  /** Merged onto the `<select>` element (e.g. `min-w-[8rem]` for score perspective — plan 04). */
  className?: string
  /** When true, empty string option maps to numeric state (D-04). CatalogTab minRating / minCatalogScore. */
  numberValue?: boolean
  defaultValue?: string | number | ''
}

export type DateRangeFilterDescriptor = BaseDescriptor & {
  type: 'dateRange'
  fromParamName?: string
  toParamName?: string
  defaultValue?: DateRangeValue
}

export type SearchFilterDescriptor = BaseDescriptor & {
  type: 'search'
  inputMode?: 'text' | 'search'
  placeholder?: string
  ariaLabel?: string
  debounceMs?: number
  className?: string
  defaultValue?: string
}

export type FilterDescriptor =
  | ToggleFilterDescriptor
  | SelectFilterDescriptor
  | DateRangeFilterDescriptor
  | SearchFilterDescriptor

export type FilterSchema = FilterDescriptor[]

/** Default debounce for search when `debounceMs` omitted (D-08). */
export const DEFAULT_SEARCH_DEBOUNCE_MS = 350

export function defaultFormatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function isDescriptorEnabled(
  descriptor: FilterDescriptor,
  values: Record<string, unknown>,
): boolean {
  if (!descriptor.enabledBy) return true
  return descriptor.enabledBy.when(values[descriptor.enabledBy.filterKey])
}

export function descriptorDefault(descriptor: FilterDescriptor): unknown {
  if (descriptor.defaultValue !== undefined) return descriptor.defaultValue
  switch (descriptor.type) {
    case 'toggle':
      return undefined
    case 'select':
      return ''
    case 'dateRange':
      return { from: '', to: '' }
    case 'search':
      return ''
    default: {
      const _exhaustive: never = descriptor
      return _exhaustive
    }
  }
}
