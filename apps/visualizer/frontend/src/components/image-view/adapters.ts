/**
 * Adapters that normalize API row shapes into the canonical `ImageView`
 * superset used by the consolidated image-view module.
 *
 * Rules (consolidate-image-metadata plan):
 *   - Pure shape mapping, never invent data.
 *   - **Never zero out scores** for list rows that don't carry them —
 *     leave those fields `undefined` so tiles can render the right pill
 *     (or none) and the modal can authoritatively fill them via the
 *     detail endpoint.
 *   - The `GET /api/images/<type>/<key>` detail endpoint already returns
 *     the `ImageView` superset (`ImageDetailResponse = ImageView`), so no
 *     adapter is needed for that path — consumers assign the response
 *     directly. List adapters below omit identity fields.
 */

import type {
  CatalogImage,
  ImageView,
  IdentityBestPhotoItem,
  InstagramImage,
  Match,
  PostNextCandidate,
  UnpostedCatalogItem,
} from '../../services/api'

export function fromCatalogListRow(row: CatalogImage): ImageView {
  return {
    image_type: 'catalog',
    key: row.key,
    id: row.id,
    filename: row.filename,
    filepath: row.filepath,
    date_taken: row.date_taken,
    rating: row.rating,
    pick: row.pick,
    color_label: row.color_label,
    keywords: row.keywords,
    title: row.title,
    caption: row.caption,
    copyright: row.copyright,
    width: row.width,
    height: row.height,
    instagram_posted: row.instagram_posted,
    instagram_url: row.instagram_url,
    image_hash: row.image_hash,
    ai_analyzed: row.ai_analyzed,
    description_summary: row.description_summary,
    description_best_perspective: row.description_best_perspective,
    description_perspectives: row.description_perspectives ?? null,
    catalog_perspective_score: row.catalog_perspective_score,
    catalog_score_perspective: row.catalog_score_perspective ?? null,
    // Identity fields intentionally omitted — list does not carry them.
  }
}

export function fromUnpostedRow(row: UnpostedCatalogItem): ImageView {
  return {
    image_type: 'catalog',
    key: row.key,
    filename: row.filename,
    date_taken: row.date_taken,
    rating: row.rating,
    instagram_posted: false,
    // No scores / description on the unposted list row; detail fetch fills them.
  }
}

export function fromBestPhotoRow(row: IdentityBestPhotoItem): ImageView {
  return {
    image_type: row.image_type ?? 'catalog',
    key: row.image_key,
    filename: row.filename,
    date_taken: row.date_taken,
    rating: row.rating,
    instagram_posted: row.instagram_posted,
    // Identity fields are authoritative on this endpoint.
    identity_aggregate_score: row.aggregate_score,
    identity_perspectives_covered: row.perspectives_covered,
    identity_eligible: row.eligible,
    identity_per_perspective: row.per_perspective,
  }
}

export function fromPostNextRow(row: PostNextCandidate): ImageView {
  return {
    image_type: row.image_type ?? 'catalog',
    key: row.image_key,
    filename: row.filename,
    date_taken: row.date_taken,
    rating: row.rating,
    // Identity fields are authoritative on this endpoint.
    identity_aggregate_score: row.aggregate_score,
    identity_perspectives_covered: row.perspectives_covered,
    identity_per_perspective: row.per_perspective,
  }
}

export function fromInstagramRow(row: InstagramImage): ImageView {
  return {
    image_type: 'instagram',
    key: row.key,
    filename: row.filename,
    local_path: row.local_path,
    created_at: row.created_at,
    post_url: row.post_url,
    caption: row.caption,
    description_summary: row.description ?? null,
    image_hash: row.image_hash,
    // No identity / catalog score fields for Instagram rows.
  }
}

/**
 * Matches carry partial `InstagramImage` / `CatalogImage` rows inside each
 * `Match`. Neither side carries identity or catalog-perspective scores, so
 * we only map the shape we have and let `ImageDetailModal` re-fetch the
 * authoritative payload on click (same contract as every other surface).
 */
export function fromMatchSide(match: Match, side: 'instagram' | 'catalog'): ImageView {
  if (side === 'instagram') {
    const embedded = match.instagram_image
    if (embedded) return fromInstagramRow(embedded)
    return {
      image_type: 'instagram',
      key: match.instagram_key,
      filename: filenameFromKey(match.instagram_key),
    }
  }
  const embedded = match.catalog_image
  if (embedded) return fromCatalogListRow(embedded)
  return {
    image_type: 'catalog',
    key: match.catalog_key,
    filename: filenameFromKey(match.catalog_key),
  }
}

function filenameFromKey(key: string): string {
  const tail = key.split('/').pop() ?? key
  return tail.split('_').pop() ?? tail
}
