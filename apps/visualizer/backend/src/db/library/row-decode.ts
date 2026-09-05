/**
 * Shared decoding for SQLite rows whose columns hold JSON text.
 */

export type Row = Record<string, unknown>;

/**
 * Decode the named JSON columns on a copy of `row`.
 *
 * A value that fails to parse is left as the raw string rather than raising.
 */
export function decodeJsonColumns<T extends Row>(row: T, columns: readonly string[]): T {
  const out = { ...row };
  for (const col of columns) {
    const val = out[col];
    if (typeof val !== 'string') continue;
    try {
      (out as Row)[col] = JSON.parse(val);
    } catch {
      // Leave the raw string in place.
    }
  }
  return out;
}
