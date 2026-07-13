import type {
  IdentityBestPhotoItem,
  IdentityBestPhotosMeta,
  PostNextSuggestionsMeta,
  StyleFingerprintMeta,
  StyleFingerprintResponse,
} from '../services/api'

/** OpenAPI nullable meta — all keys present (generated contract shape). */
export const EMPTY_BEST_PHOTOS_META: IdentityBestPhotosMeta = {
  active_perspectives: null,
  weighting: null,
  min_perspectives_used: null,
  coverage_rule: null,
  total_catalog_images: null,
  eligible_count: null,
  scored_any_count: null,
  coverage_note: null,
}

export const EMPTY_STYLE_FINGERPRINT_META: StyleFingerprintMeta = {
  tokenization_note: null,
  perspectives_included: null,
  weighting: null,
  scores_are_advisory: null,
}

export const EMPTY_STYLE_FINGERPRINT_RESPONSE: StyleFingerprintResponse = {
  per_perspective: [],
  aggregate_distribution: { '1-3': 0, '4-6': 0, '7-10': 0 },
  aggregate_distribution_note: null,
  top_rationale_tokens: [],
  evidence: {},
  evidence_note: null,
  meta: EMPTY_STYLE_FINGERPRINT_META,
}

export const EMPTY_POST_NEXT_META: PostNextSuggestionsMeta = {
  weighting: null,
  min_perspectives_used: null,
  coverage_rule: null,
  timezone_assumption: null,
  high_score_rule: null,
  posted_semantics: null,
  cadence_gap: null,
  cadence_note: null,
}

/** Minimal nullable identity row fields required by generated OpenAPI types. */
export const NULLABLE_BEST_PHOTO_FIELDS = {
  image_type: null,
  stack_id: null,
  stack_member_count: null,
  is_stack_representative: null,
} as const satisfies Partial<IdentityBestPhotoItem>
