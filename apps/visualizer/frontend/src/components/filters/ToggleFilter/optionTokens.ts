import type { ToggleOption } from '../types'

/**
 * Codec helpers that translate between a `ToggleFilter`'s
 * `ToggleOption.value` and the string tokens used by the underlying
 * `<select>` DOM element.
 *
 * Tokens are position-based (`__opt_0__`, `__opt_1__`, …) rather than
 * value-based so that option values don't need to be stringifiable or
 * unique — the framework owns the DOM round-trip and consumers declare
 * rows with their real `{ value, label }` pairs.
 */

/** Position-based synthetic `<option value>` token. */
export function tokenForIndex(i: number): string {
  return `__opt_${i}__`
}

/**
 * Inverse of `tokenForIndex`. Returns `null` for any string that isn't
 * a well-formed `__opt_N__` token so callers can fall through to a
 * sensible default (typically `options[0].value`).
 */
export function indexOfToken(raw: string): number | null {
  const m = /^__opt_(\d+)__$/.exec(raw)
  if (!m) return null
  return Number(m[1])
}

/**
 * Look up the position of the option whose `value` is structurally
 * equal (`===`) to the given value. Falls back to `0` (the first row)
 * when no match is found, so the `<select>` always has a valid index.
 */
export function indexOfValue(options: ToggleOption[], value: unknown): number {
  const idx = options.findIndex((o) => o.value === value)
  return idx >= 0 ? idx : 0
}
