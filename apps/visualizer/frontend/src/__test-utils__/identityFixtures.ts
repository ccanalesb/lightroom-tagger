import type {
  IdentityBestPhotosMeta,
  MirrorMeta,
  MirrorResponse,
  PostNextSuggestionsMeta,
} from '../services/api'

/** OpenAPI nullable meta — all keys present (generated contract shape). */
export const EMPTY_BEST_PHOTOS_META: IdentityBestPhotosMeta = {
  active_perspectives: null,
  weighting: null,
  ranking_key: null,
  min_perspectives_used: null,
  coverage_rule: null,
  total_catalog_images: null,
  eligible_count: null,
  scored_any_count: null,
  coverage_note: null,
}

export const EMPTY_MIRROR_META: MirrorMeta = {
  active_perspectives: null,
  total_catalog_images: null,
  voting_rule: null,
  crowning_rule: null,
  low_coverage_threshold: null,
  exemplar_initial_limit: null,
  exemplar_page_size: null,
  descriptor_min_count: null,
  scores_are_advisory: null,
  fallback_active: null,
}

export const EMPTY_MIRROR_RESPONSE: MirrorResponse = {
  population: 0,
  sections: [],
  other_lenses: [],
  meta: EMPTY_MIRROR_META,
}

export const EMPTY_POST_NEXT_META: PostNextSuggestionsMeta = {
  weighting: null,
  ranking_key: null,
  min_perspectives_used: null,
  coverage_rule: null,
  high_score_rule: null,
}

/** Minimal nullable identity row fields required by generated OpenAPI types. */
export const NULLABLE_BEST_PHOTO_FIELDS = {
  image_type: null,
  stack_id: null,
  stack_member_count: null,
  is_stack_representative: null,
} as const satisfies Partial<import('../services/api').IdentityBestPhotoItem>
