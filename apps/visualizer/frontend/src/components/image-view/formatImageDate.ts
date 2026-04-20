import type { ImageView } from '../../services/api'
import { DATE_ESTIMATED_SUFFIX, DATE_NO_DATE } from '../../constants/strings'

/**
 * Display-safe date label for an `ImageView`.
 *
 * Resolution order:
 *   1. `created_at` (authoritative timestamp) → localized date/time.
 *   2. `date_folder` (Instagram dump falls back to a month folder like
 *      `"202403"`) → `YYYY/MM (estimated)`.
 *   3. `DATE_NO_DATE` sentinel.
 *
 * Extracted from `InstagramImageDetailSections` so other surfaces (match
 * modal, post-next, analytics) can share one definition of "what date do
 * we show" instead of re-implementing the fallback inline.
 */
export function formatImageDate(image: ImageView): string {
  if (image.created_at) return new Date(image.created_at).toLocaleString()
  if (image.date_folder) {
    return `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} ${DATE_ESTIMATED_SUFFIX}`
  }
  return DATE_NO_DATE
}
