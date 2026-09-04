/**
 * The ranking sort the best-photos and post-next views share.
 */

/** Lexicographic compare, so the tiebreakers below read the same way. */
export const cmpStr = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);

interface Rankable {
  image_key: string;
  ranking_percentile: number;
  date_taken?: string;
}

/**
 * Sort by corroboration-vetoed ranking percentile, then date, then key.
 *
 * Three stable passes in reverse precedence rather than one comparator: each
 * pass preserves the order the previous one left, so the last sort applied is
 * the primary key. Written this way because the pre-sort order — the insertion
 * order of the score index — is itself the final tiebreaker, and a single
 * comparator would have to restate it.
 *
 * Sorts in place and returns the same array.
 */
export function sortByRanking<T extends Rankable>(
  items: T[],
  sortByDate: 'newest' | 'oldest' | null,
): T[] {
  const dateDescending = sortByDate !== 'oldest';
  items.sort((a, b) => cmpStr(String(a.image_key), String(b.image_key)));
  items.sort((a, b) => {
    const c = cmpStr(a.date_taken ?? '', b.date_taken ?? '');
    return dateDescending ? -c : c;
  });
  items.sort((a, b) => b.ranking_percentile - a.ranking_percentile);
  return items;
}
