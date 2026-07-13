import { invalidate, invalidateAll, patchMatching } from '../data'
import type {
  CatalogImage,
  CatalogImageInput,
  CatalogSimilarityGroup,
  CatalogSimilarityGroupsResponse,
  IdentityPerPerspectiveScore,
  ImageDetailResponse,
  ImageView,
} from '../types/catalog'
import type {
  ConfigCatalogGetResponse,
  ConfigCatalogPutResponse,
  ConfigInstagramDumpGetResponse,
  ConfigInstagramDumpPutResponse,
  ConfigStackDetectionGetResponse,
  ConfigStackDetectionPutResponse,
} from '../types/config'
import type {
  DescriptionGenerateResponse,
  DescriptionGetResponse,
  DescriptionItem,
  DescriptionsListResponse,
  ImageDescription,
  ImageDescriptionComposition,
  ImageDescriptionPerspectives,
  ImageDescriptionTechnical,
} from '../types/descriptions'
import type { InstagramImage, InstagramImageInput, InstagramListResponse } from '../types/instagram'
import type { Job, JobsGetOptions, JobsHealth, JobsListResponse } from '../types/job'
import type { Match, MatchGroup, MatchesListResponse } from '../types/matches'
import type {
  PerspectiveDetail,
  PerspectiveScore,
  PerspectiveSummary,
} from '../types/perspectives'
import type {
  DescriptionModel,
  DescriptionModelsResponse,
  Provider,
  ProviderDefaults,
  ProviderModel,
} from '../types/providers'
import type {
  ChatSearchMessage,
  ChatSearchRequest,
  ChatSearchResponse,
  ChatSearchResultImage,
} from '../types/search'
import type {
  ImageScoreRow,
  ScoresCurrentResponse,
  ScoresHistoryResponse,
} from '../types/scores'
import type {
  StackMergeResponse,
  StackRepresentativeResponse,
  StackSplitMemberResponse,
} from '../types/stacks'
import { API_DEFAULT_URL } from '../constants/strings'

export type {
  DescriptionGenerateResponse,
  DescriptionGetResponse,
  DescriptionItem,
  DescriptionsListResponse,
  ImageDescription,
  ImageDescriptionComposition,
  ImageDescriptionPerspectives,
  ImageDescriptionTechnical,
  ImageScoreRow,
  ScoresCurrentResponse,
  ScoresHistoryResponse,
}
export type {
  CatalogImage,
  CatalogImageInput,
  CatalogSimilarityGroup,
  CatalogSimilarityGroupsResponse,
  ChatSearchMessage,
  ChatSearchRequest,
  ChatSearchResponse,
  ChatSearchResultImage,
  IdentityPerPerspectiveScore,
  ImageDetailResponse,
  ImageView,
  InstagramImage,
  InstagramImageInput,
  Job,
  JobsGetOptions,
  JobsHealth,
  JobsListResponse,
  StackMergeResponse,
  StackRepresentativeResponse,
  StackSplitMemberResponse,
}
export type { Match, MatchGroup, MatchesListResponse }
export type {
  DescriptionModel,
  DescriptionModelsResponse,
  PerspectiveDetail,
  PerspectiveScore,
  PerspectiveSummary,
  Provider,
  ProviderDefaults,
  ProviderModel,
}

const API_URL = import.meta.env.VITE_API_URL || API_DEFAULT_URL

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body && typeof (body as { error?: unknown }).error === 'string') {
        detail = (body as { error: string }).error
      }
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail)
  }

  return response.json()
}

async function requestVoid(path: string, options?: RequestInit): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body && typeof (body as { error?: unknown }).error === 'string') {
        detail = (body as { error: string }).error
      }
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail)
  }
}

export const PerspectivesAPI = {
  list: (params?: { active_only?: boolean }) => {
    const sp = new URLSearchParams()
    if (params?.active_only) sp.set('active_only', 'true')
    const qs = sp.toString()
    return request<PerspectiveSummary[]>(`/perspectives/${qs ? `?${qs}` : ''}`)
  },

  get: (slug: string) =>
    request<PerspectiveDetail>(`/perspectives/${encodeURIComponent(slug)}`),

  create: async (body: {
    slug: string
    display_name: string
    prompt_markdown: string
    description?: string
    active?: boolean
  }) => {
    const result = await request<PerspectiveDetail>('/perspectives/', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    invalidateAll(['perspectives'])
    return result
  },

  update: async (slug: string, body: Record<string, unknown>) => {
    const result = await request<PerspectiveDetail>(`/perspectives/${encodeURIComponent(slug)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
    invalidateAll(['perspectives'])
    return result
  },

  remove: async (slug: string) => {
    await requestVoid(`/perspectives/${encodeURIComponent(slug)}`, { method: 'DELETE' })
    invalidateAll(['perspectives'])
  },

  resetDefault: async (slug: string) => {
    const result = await request<PerspectiveDetail>(
      `/perspectives/${encodeURIComponent(slug)}/reset-default`,
      { method: 'POST' },
    )
    invalidateAll(['perspectives'])
    return result
  },
}

export const JobsAPI = {
  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.status) sp.set('status', params.status)
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    const qs = sp.toString()
    return request<JobsListResponse>(`/jobs/${qs ? `?${qs}` : ''}`)
  },

  get: (id: string, options?: JobsGetOptions) => {
    const sp = new URLSearchParams()
    if (options?.logs_limit !== undefined) {
      sp.set('logs_limit', String(options.logs_limit))
    }
    const qs = sp.toString()
    return request<Job>(`/jobs/${id}${qs ? `?${qs}` : ''}`)
  },

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  create: async (type: string, metadata?: Record<string, any>) => {
    const job = await request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    })
    invalidateAll(['jobs.list'])
    invalidateAll(['jobs.health'])
    return job
  },

  getActive: () =>
    request<Job[]>('/jobs/active'),

  cancel: async (id: string) => {
    await requestVoid(`/jobs/${id}`, { method: 'DELETE' })
    // jobs.list is patched in-place via the job_updated socket event so we
    // don't invalidate here (that would wipe the cache and trigger Suspense).
    invalidateAll(['jobs.health'])
  },

  retry: async (id: string) => {
    const job = await request<Job>(`/jobs/${id}/retry`, { method: 'POST' })
    // jobs.list patched via socket; detail is updated via setLocalJob in the
    // modal — invalidating the detail cache would cause a Suspense flash there.
    invalidateAll(['jobs.health'])
    return job
  },

  health: () =>
    request<JobsHealth>('/jobs/health'),
}

export const ConfigAPI = {
  getCatalog: () =>
    request<ConfigCatalogGetResponse>('/config/catalog'),

  putCatalog: async (catalogPath: string) => {
    const result = await request<ConfigCatalogPutResponse>('/config/catalog', {
      method: 'PUT',
      body: JSON.stringify({ catalog_path: catalogPath }),
    })
    invalidateAll(['images.catalog'])
    invalidateAll(['catalog.cache.stats'])
    invalidateAll(['jobs.health'])
    invalidateAll(['dashboard'])
    invalidateAll(['analytics'])
    return result
  },

  getInstagramDump: () =>
    request<ConfigInstagramDumpGetResponse>('/config/instagram-dump'),

  putInstagramDump: async (instagramDumpPath: string) => {
    const result = await request<ConfigInstagramDumpPutResponse>(
      '/config/instagram-dump',
      {
        method: 'PUT',
        body: JSON.stringify({ instagram_dump_path: instagramDumpPath }),
      },
    )
    invalidateAll(['images.instagram'])
    invalidateAll(['jobs.health'])
    return result
  },

  getStackDetection: () =>
    request<ConfigStackDetectionGetResponse>('/config/stack-detection'),

  putStackDetection: async (stackBurstDeltaMs: number) => {
    const result = await request<ConfigStackDetectionPutResponse>(
      '/config/stack-detection',
      {
        method: 'PUT',
        body: JSON.stringify({ stack_burst_delta_ms: stackBurstDeltaMs }),
      },
    )
    invalidateAll(['jobs.health'])
    return result
  },
}

/** Query params shared by catalog list and CLIP similar (backend mirrors filters). */
export type CatalogListQueryParams = {
  posted?: boolean
  analyzed?: boolean | null
  month?: string
  keyword?: string
  min_rating?: number
  date_from?: string
  date_to?: string
  color_label?: string
  description_search?: string
  score_perspective?: string
  min_score?: number
  sort_by_score?: 'asc' | 'desc'
  sort_by_date?: 'newest' | 'oldest'
  limit?: number
  offset?: number
}

function appendCatalogListSearchParams(
  searchParams: URLSearchParams,
  params: CatalogListQueryParams | undefined,
) {
  if (!params) return
  if (params.posted !== undefined) {
    searchParams.set('posted', params.posted ? 'true' : 'false')
  }
  if (params.analyzed === true) {
    searchParams.set('analyzed', 'true')
  } else if (params.analyzed === false) {
    searchParams.set('analyzed', 'false')
  }
  if (params.month) searchParams.set('month', params.month)
  if (params.keyword) searchParams.set('keyword', params.keyword)
  if (params.min_rating !== undefined) {
    searchParams.set('min_rating', String(params.min_rating))
  }
  if (params.date_from) searchParams.set('date_from', params.date_from)
  if (params.date_to) searchParams.set('date_to', params.date_to)
  if (params.color_label) searchParams.set('color_label', params.color_label)
  if (params.description_search) {
    searchParams.set('description_search', params.description_search)
  }
  if (params.score_perspective) searchParams.set('score_perspective', params.score_perspective)
  if (params.min_score !== undefined) searchParams.set('min_score', String(params.min_score))
  if (params.sort_by_score) searchParams.set('sort_by_score', params.sort_by_score)
  if (params.sort_by_date) searchParams.set('sort_by_date', params.sort_by_date)
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
  if (params.offset !== undefined) searchParams.set('offset', String(params.offset))
}

export const SystemAPI = {
  status: () =>
    request<{ status: string }>('/status'),

  stats: () =>
    request<Stats>('/stats'),

  visionModels: () =>
    request<{
      models: { name: string; default: boolean; provider_id?: string }[]
      fallback: boolean
    }>('/vision-models'),

  cacheStatus: () =>
    request<CacheStatus>('/cache/status'),

  cachePipelineStatus: () =>
    request<CachePipelineStatus>('/cache/pipeline-status'),
}

export const ImagesAPI = {
  listInstagram: (params?: {
    limit?: number
    offset?: number
    date_folder?: string
    date_from?: string
    date_to?: string
    sort_by_date?: 'newest' | 'oldest'
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset))
    if (params?.date_folder) searchParams.set('date_folder', params.date_folder)
    if (params?.date_from) searchParams.set('date_from', params.date_from)
    if (params?.date_to) searchParams.set('date_to', params.date_to)
    if (params?.sort_by_date) searchParams.set('sort_by_date', params.sort_by_date)
    return request<InstagramListResponse>(`/images/instagram?${searchParams.toString()}`)
  },

  getInstagramMonths: () =>
    request<{ months: string[] }>('/images/instagram/months'),

  getCatalogMonths: () =>
    request<{ months: string[] }>('/images/catalog/months'),

  /** Catalog browse; use listCatalog(params) with optional filters. */
  listCatalog: (params?: CatalogListQueryParams) => {
    const searchParams = new URLSearchParams()
    appendCatalogListSearchParams(searchParams, params)
    const qs = searchParams.toString()
    return request<{ total: number; images: CatalogImage[] }>(
      `/images/catalog${qs ? `?${qs}` : ''}`
    )
  },

  /**
   * Single-image detail for the consolidated image-view modal. Always fetched
   * on modal open so tiles can pass just `image_type` + `key` without worrying
   * about partial list-row data (see consolidate-image-metadata plan).
   */
  getImageDetail: (
    image_type: 'catalog' | 'instagram',
    image_key: string,
    params?: { score_perspective?: string },
  ) => {
    const qs = params?.score_perspective
      ? `?score_perspective=${encodeURIComponent(params.score_perspective)}`
      : ''
    return request<ImageDetailResponse>(
      `/images/${image_type}/${encodeURIComponent(image_key)}${qs}`,
    )
  },

  listCatalogSimilarityGroups: (params?: { limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    const qs = sp.toString()
    return request<CatalogSimilarityGroupsResponse>(
      `/images/catalog-similarity-groups${qs ? `?${qs}` : ''}`,
    )
  },

  getStackMembers: (stackId: number) =>
    request<{ items: CatalogImage[] }>(`/images/stacks/${stackId}/members`),

  splitStackMember: async (stackId: number, imageKey: string) => {
    const result = await request<StackSplitMemberResponse>(
      `/images/stacks/${stackId}/split-member`,
      {
        method: 'POST',
        body: JSON.stringify({ image_key: imageKey }),
      },
    )
    invalidateAll(['images.catalog'])
    invalidateAll(['images.detail'])
    invalidateAll(['dashboard'])
    invalidateAll(['identity'])
    return result
  },

  mergeStacks: async (targetStackId: number, sourceStackId: number) => {
    const result = await request<StackMergeResponse>(`/images/stacks/${targetStackId}/merge`, {
      method: 'POST',
      body: JSON.stringify({ source_stack_id: sourceStackId }),
    })
    invalidateAll(['images.catalog'])
    invalidateAll(['images.detail'])
    invalidateAll(['dashboard'])
    invalidateAll(['identity'])
    return result
  },

  setStackRepresentative: async (stackId: number, imageKey: string) => {
    const result = await request<StackRepresentativeResponse>(
      `/images/stacks/${stackId}/representative`,
      {
        method: 'POST',
        body: JSON.stringify({ image_key: imageKey }),
      },
    )
    invalidateAll(['images.catalog'])
    invalidateAll(['images.detail'])
    invalidateAll(['dashboard'])
    invalidateAll(['identity'])
    return result
  },

  chatSearch: (payload: ChatSearchRequest) =>
    request<ChatSearchResponse>('/images/search/chat-search', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}

export const MatchingAPI = {
  list: (
    limit?: number,
    offset?: number,
    params?: { sort_by_date?: 'newest' | 'oldest' },
  ) => {
    const sp = new URLSearchParams()
    sp.set('limit', String(limit ?? 50))
    sp.set('offset', String(offset ?? 0))
    if (params?.sort_by_date) sp.set('sort_by_date', params.sort_by_date)
    return request<MatchesListResponse>(`/images/matches?${sp.toString()}`)
  },
  validate: async (catalogKey: string, instaKey: string) => {
    const result = await request<{ validated: boolean }>(
      `/images/matches/${encodeURIComponent(catalogKey)}/${encodeURIComponent(instaKey)}/validate`,
      { method: 'PATCH' },
    )
    // Patch cache in-place so Suspense is not triggered in the currently-mounted
    // MatchesTab. The component also applies an optimistic update via setMatchGroups.
    // The cache is invalidated on unmount so the next visit fetches fresh data.
    const matchesPrefix = JSON.stringify(['matching.groups']).slice(0, -1)
    patchMatching(
      (k) => k.startsWith(matchesPrefix),
      (raw) => {
        const resp = raw as { match_groups?: MatchGroup[] }
        if (!resp?.match_groups) return raw
        return {
          ...resp,
          match_groups: resp.match_groups.map((group) => {
            if (group.instagram_key !== instaKey) return group
            const candidates = group.candidates.map((c) =>
              c.catalog_key === catalogKey && c.instagram_key === instaKey
                ? { ...c, validated_at: new Date().toISOString() }
                : c,
            )
            return { ...group, candidates, has_validated: candidates.some((c) => !!c.validated_at) }
          }),
        }
      },
    )
    invalidateAll(['images.instagram'])
    invalidateAll(['images.catalog'])
    invalidateAll(['images.detail'])
    invalidateAll(['dashboard'])
    return result
  },
  reject: async (catalogKey: string, instaKey: string) => {
    const result = await request<{ rejected: boolean }>(
      `/images/matches/${encodeURIComponent(catalogKey)}/${encodeURIComponent(instaKey)}/reject`,
      { method: 'PATCH' },
    )
    // Patch cache in-place — same rationale as validate above.
    const matchesPrefix = JSON.stringify(['matching.groups']).slice(0, -1)
    patchMatching(
      (k) => k.startsWith(matchesPrefix),
      (raw) => {
        const resp = raw as { match_groups?: MatchGroup[] }
        if (!resp?.match_groups) return raw
        return {
          ...resp,
          match_groups: resp.match_groups.flatMap((group) => {
            if (group.instagram_key !== instaKey) return [group]
            const remaining = group.candidates.filter(
              (c) => !(c.catalog_key === catalogKey && c.instagram_key === instaKey),
            )
            if (remaining.length === 0) {
              return [{ ...group, candidates: [], candidate_count: 0, best_score: 0, has_validated: false, all_rejected: true }]
            }
            return [{
              ...group,
              candidates: remaining,
              candidate_count: remaining.length,
              best_score: Math.max(...remaining.map((c) => c.score)),
              has_validated: remaining.some((c) => !!c.validated_at),
            }]
          }),
        }
      },
    )
    invalidateAll(['images.instagram'])
    invalidateAll(['images.catalog'])
    invalidateAll(['images.detail'])
    invalidateAll(['dashboard'])
    return result
  },
}

export interface PaginationMeta {
  offset: number
  limit: number
  current_page: number
  total_pages: number
  has_more: boolean
}

export const DescriptionsAPI = {
  get: (imageKey: string) =>
    request<DescriptionGetResponse>(
      `/descriptions/${encodeURIComponent(imageKey)}`
    ),
  list: (params?: { image_type?: string; described_only?: boolean; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.image_type) sp.set('image_type', params.image_type)
    if (params?.described_only) sp.set('described_only', 'true')
    if (params?.limit) sp.set('limit', String(params.limit))
    if (params?.offset) sp.set('offset', String(params.offset))
    return request<DescriptionsListResponse>(
      `/descriptions/?${sp.toString()}`
    )
  },
  generate: async (
    imageKey: string,
    imageType: string,
    force = false,
    model?: string,
    providerId?: string,
    providerModel?: string,
  ) => {
    const result = await request<DescriptionGenerateResponse>(
      `/descriptions/${encodeURIComponent(imageKey)}/generate`,
      {
        method: 'POST',
        body: JSON.stringify({
          image_type: imageType,
          force,
          ...(model && { model }),
          ...(providerId && { provider_id: providerId }),
          ...(providerModel && { provider_model: providerModel }),
        }),
      },
    )
    invalidate(['descriptions', imageKey])
    invalidateAll(['images.detail', imageType, imageKey])
    return result
  },
}

export type DescriptionListResult = Awaited<ReturnType<typeof DescriptionsAPI.list>>

export const ScoresAPI = {
  getCurrent: (imageKey: string, params?: { image_type?: 'catalog' | 'instagram' }) => {
    const sp = new URLSearchParams()
    if (params?.image_type) sp.set('image_type', params.image_type)
    const qs = sp.toString()
    return request<ScoresCurrentResponse>(
      `/scores/${encodeURIComponent(imageKey)}${qs ? `?${qs}` : ''}`,
    )
  },

  getHistory: (
    imageKey: string,
    params: { perspective_slug: string; image_type?: 'catalog' | 'instagram' },
  ) => {
    const sp = new URLSearchParams()
    sp.set('perspective_slug', params.perspective_slug)
    if (params.image_type) sp.set('image_type', params.image_type)
    return request<ScoresHistoryResponse>(
      `/scores/${encodeURIComponent(imageKey)}/history?${sp.toString()}`,
    )
  },
}

// --- Analytics (Phase 7 /api/analytics) ---

export type AnalyticsGranularity = 'day' | 'week' | 'month'

export interface PostingFrequencyBucket {
  bucket_start: string
  count: number
}

export interface PostingFrequencyMeta {
  timestamp_source?: string
  granularity?: string
  timezone_assumption?: string
  date_from?: string
  date_to?: string
  bucket_expression?: string
}

export interface PostingFrequencyResponse {
  buckets: PostingFrequencyBucket[]
  meta: PostingFrequencyMeta
}

export interface HeatmapCell {
  dow: number
  hour: number
  count: number
}

export interface PostingHeatmapMeta {
  dow_labels?: string[]
  timezone_assumption?: string
  timezone_note?: string
  date_from?: string
  date_to?: string
}

export interface PostingHeatmapResponse {
  cells: HeatmapCell[]
  meta: PostingHeatmapMeta
}

export interface CaptionHashtagMeta {
  timezone_assumption?: string
  hashtag_pattern?: string
  timestamp_scope?: string
}

export interface TopHashtagRow {
  tag: string
  count: number
}

export interface TopWordRow {
  word: string
  count: number
}

export interface CaptionStatsResponse {
  post_count: number
  with_caption_count: number
  avg_caption_len: number
  median_caption_len: number | null
  top_hashtags: TopHashtagRow[]
  posts_with_hashtags: number
  avg_hashtags_per_post: number
  top_words: TopWordRow[]
  meta: CaptionHashtagMeta
}

/** Lightweight row from `/api/analytics/unposted-catalog` (subset of catalog list). */
export interface UnpostedCatalogItem {
  key: string
  filename: string
  date_taken: string
  rating: number
}

export interface UnpostedCatalogResponse {
  total: number
  images: UnpostedCatalogItem[]
  pagination: PaginationMeta
}

export const AnalyticsAPI = {
  getPostingFrequency: (params: {
    date_from: string
    date_to: string
    granularity?: AnalyticsGranularity
  }) => {
    const sp = new URLSearchParams()
    sp.set('date_from', params.date_from)
    sp.set('date_to', params.date_to)
    sp.set('granularity', params.granularity ?? 'day')
    return request<PostingFrequencyResponse>(`/analytics/posting-frequency?${sp.toString()}`)
  },

  getPostingHeatmap: (params: { date_from: string; date_to: string }) => {
    const sp = new URLSearchParams()
    sp.set('date_from', params.date_from)
    sp.set('date_to', params.date_to)
    return request<PostingHeatmapResponse>(`/analytics/posting-heatmap?${sp.toString()}`)
  },

  getCaptionStats: (params: { date_from: string; date_to: string }) => {
    const sp = new URLSearchParams()
    sp.set('date_from', params.date_from)
    sp.set('date_to', params.date_to)
    return request<CaptionStatsResponse>(`/analytics/caption-stats?${sp.toString()}`)
  },

  /** Catalog images with `instagram_posted = 0` (server-filtered). */
  getUnpostedCatalog: (params?: {
    date_from?: string
    date_to?: string
    min_rating?: number
    month?: string
    limit?: number
    offset?: number
  }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    if (params?.min_rating !== undefined) sp.set('min_rating', String(params.min_rating))
    if (params?.month) sp.set('month', params.month)
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    const qs = sp.toString()
    return request<UnpostedCatalogResponse>(`/analytics/unposted-catalog${qs ? `?${qs}` : ''}`)
  },
}

// --- Identity (Phase 8) — GET /api/identity/best-photos, /api/identity/style-fingerprint, /api/identity/suggestions

export interface IdentityBestPhotoItem {
  image_key: string
  image_type?: 'catalog' | 'instagram'
  aggregate_score: number
  perspectives_covered: number
  eligible?: boolean
  per_perspective: IdentityPerPerspectiveScore[]
  filename: string
  date_taken: string
  rating: number
  instagram_posted: boolean
  stack_id?: number | null
  stack_member_count?: number | null
  is_stack_representative?: boolean | null
}

export interface IdentityBestPhotosMeta {
  active_perspectives?: string[]
  weighting?: string
  min_perspectives_used?: number
  coverage_rule?: string
  total_catalog_images?: number
  eligible_count?: number
  scored_any_count?: number
  coverage_note?: string
}

export interface IdentityBestPhotosResponse {
  items: IdentityBestPhotoItem[]
  total: number
  meta: IdentityBestPhotosMeta
}

export interface StyleFingerprintPerPerspective {
  perspective_slug: string
  mean_score: number | null
  median_score: number | null
  count_scores: number
}

export interface StyleFingerprintMeta {
  tokenization_note?: string
  perspectives_included?: string[]
  weighting?: string
  scores_are_advisory?: string
}

export interface StyleFingerprintResponse {
  per_perspective: StyleFingerprintPerPerspective[]
  aggregate_distribution: Record<string, number>
  aggregate_distribution_note?: string
  top_rationale_tokens: { token: string; count: number }[]
  evidence: Record<string, string[]>
  evidence_note?: string
  meta: StyleFingerprintMeta
}

export interface PostNextCandidate {
  image_key: string
  image_type?: 'catalog' | 'instagram'
  filename: string
  date_taken: string
  rating: number
  aggregate_score: number
  perspectives_covered: number
  per_perspective: IdentityPerPerspectiveScore[]
  reasons: string[]
  reason_codes: string[]
}

export interface PostNextSuggestionsMeta {
  weighting?: string
  min_perspectives_used?: number
  coverage_rule?: string
  timezone_assumption?: string
  high_score_rule?: string
  posted_semantics?: string
  cadence_gap?: boolean
  cadence_note?: string
}

export interface PostNextSuggestionsResponse {
  candidates: PostNextCandidate[]
  total: number
  meta: PostNextSuggestionsMeta
  empty_state: string | null
}

export const IdentityAPI = {
  getBestPhotos: (params?: {
    limit?: number
    offset?: number
    min_perspectives?: number
    sort_by_date?: 'newest' | 'oldest'
    posted?: boolean
  }) => {
    const sp = new URLSearchParams()
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    if (params?.min_perspectives !== undefined) {
      sp.set('min_perspectives', String(params.min_perspectives))
    }
    if (params?.sort_by_date) sp.set('sort_by_date', params.sort_by_date)
    if (params?.posted !== undefined) sp.set('posted', params.posted ? 'true' : 'false')
    const qs = sp.toString()
    return request<IdentityBestPhotosResponse>(`/identity/best-photos${qs ? `?${qs}` : ''}`)
  },

  getStyleFingerprint: () => request<StyleFingerprintResponse>('/identity/style-fingerprint'),

  getSuggestions: (params?: {
    limit?: number
    offset?: number
    lookback_days_recent?: number
    lookback_days_baseline?: number
    sort_by_date?: 'newest' | 'oldest'
  }) => {
    const sp = new URLSearchParams()
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    if (params?.lookback_days_recent !== undefined) {
      sp.set('lookback_days_recent', String(params.lookback_days_recent))
    }
    if (params?.lookback_days_baseline !== undefined) {
      sp.set('lookback_days_baseline', String(params.lookback_days_baseline))
    }
    if (params?.sort_by_date) sp.set('sort_by_date', params.sort_by_date)
    const qs = sp.toString()
    return request<PostNextSuggestionsResponse>(`/identity/suggestions${qs ? `?${qs}` : ''}`)
  },
}

export interface Stats {
  catalog_images: number
  instagram_images: number
  posted_to_instagram: number
  matches_found: number
  db_path: string
}

export interface CacheStatus {
  total_images: number
  cached_images: number
  missing: number
  cache_size_mb: number
  cache_dir: string
}

/** Single bucket payload from ``/api/cache/pipeline-status``. */
export interface CachePipelineRun {
  job_id: string
  type: string
  status: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
}

/** All pipeline-status buckets — one entry per CatalogCacheTab trigger.
 *
 * Each value is ``null`` when no matching job has ever run. Keys are stable
 * and aligned with the UI buttons; ``embed_catalog_and_instagram`` matches
 * jobs created with ``image_type: 'catalog_and_instagram'``.
 */
export interface CachePipelineStatus {
  catalog_sync: CachePipelineRun | null
  embed_catalog: CachePipelineRun | null
  embed_catalog_and_instagram: CachePipelineRun | null
  stack_detect: CachePipelineRun | null
  catalog_similarity: CachePipelineRun | null
  catalog_cache_build: CachePipelineRun | null
  prepare_catalog: CachePipelineRun | null
}

export const ProvidersAPI = {
  list: () => request<Provider[]>('/providers/'),
  listDescriptionModels: () =>
    request<DescriptionModelsResponse>('/providers/models/description'),
  health: (providerId: string) =>
    request<{ reachable: boolean; error?: string }>(
      `/providers/${encodeURIComponent(providerId)}/health`,
    ),
  listModels: (providerId: string) =>
    request<ProviderModel[]>(`/providers/${providerId}/models`),
  getFallbackOrder: () =>
    request<{ order: string[] }>('/providers/fallback-order'),
  getDefaults: () =>
    request<ProviderDefaults>('/providers/defaults'),
  updateFallbackOrder: async (order: string[]) => {
    const result = await request<{ order: string[] }>('/providers/fallback-order', {
      method: 'PUT',
      body: JSON.stringify({ order }),
    })
    invalidateAll(['providers.list'])
    return result
  },
  updateDefaults: async (defaults: Partial<ProviderDefaults>) => {
    const result = await request<ProviderDefaults>('/providers/defaults', {
      method: 'PUT',
      body: JSON.stringify(defaults),
    })
    invalidateAll(['providers.list'])
    invalidate(['providers.defaults'])
    return result
  },
  addModel: async (
    providerId: string,
    model: { id: string; name: string; vision: boolean },
  ) => {
    const result = await request<ProviderModel>(`/providers/${providerId}/models`, {
      method: 'POST',
      body: JSON.stringify(model),
    })
    invalidateAll(['providers.list'])
    return result
  },
  removeModel: async (providerId: string, modelId: string) => {
    const result = await request<{ deleted: boolean }>(
      `/providers/${providerId}/models/${encodeURIComponent(modelId)}`,
      { method: 'DELETE' },
    )
    invalidateAll(['providers.list'])
    return result
  },
  reorderModels: async (providerId: string, order: string[]) => {
    const result = await request<{ success: boolean }>(`/providers/${providerId}/models/order`, {
      method: 'PUT',
      body: JSON.stringify({ order }),
    })
    invalidateAll(['providers.list'])
    return result
  },
}
