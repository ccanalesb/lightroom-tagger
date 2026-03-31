import { Job } from '../types/job'
import { API_DEFAULT_URL } from '../constants/strings'

export type { Job }

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
    throw new Error(`${response.status} ${response.statusText}`)
  }

  return response.json()
}

export const JobsAPI = {
  list: (status?: string) =>
    request<Job[]>(status? `/jobs/?status=${status}` : '/jobs/'),

  get: (id: string) =>
    request<Job>(`/jobs/${id}`),

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  create: (type: string, metadata?: Record<string, any>) =>
    request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    }),

  getActive: () =>
    request<Job[]>('/jobs/active'),

  cancel: (id: string) =>
    request<void>(`/jobs/${id}`, { method: 'DELETE' }),
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
}

export const ImagesAPI = {
  listInstagram: (params?: { limit?: number; offset?: number; date_folder?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset))
    if (params?.date_folder) searchParams.set('date_folder', params.date_folder)
    return request<{
      total: number;
      images: InstagramImage[];
      pagination: PaginationMeta;
    }>(`/images/instagram?${searchParams.toString()}`)
  },

  getInstagramMonths: () =>
    request<{ months: string[] }>('/images/instagram/months'),

  listCatalog: (posted?: boolean, limit?: number, offset?: number) => {
    const params = new URLSearchParams()
    if (posted !== undefined) params.set('posted', String(posted))
    if (limit) params.set('limit', String(limit))
    if (offset) params.set('offset', String(offset))
    return request<{ total: number; images: CatalogImage[] }>(
      `/images/catalog?${params.toString()}`
    )
  },
}

export const MatchingAPI = {
  list: (limit?: number, offset?: number) =>
    request<{
      total: number
      total_groups?: number
      total_matches?: number
      match_groups: MatchGroup[]
      matches: Match[]
    }>(`/images/matches?limit=${limit || 50}&offset=${offset || 0}`),
  validate: (catalogKey: string, instaKey: string) =>
    request<{ validated: boolean }>(
      `/images/matches/${encodeURIComponent(catalogKey)}/${encodeURIComponent(instaKey)}/validate`,
      { method: 'PATCH' },
    ),
  reject: (catalogKey: string, instaKey: string) =>
    request<{ rejected: boolean }>(
      `/images/matches/${encodeURIComponent(catalogKey)}/${encodeURIComponent(instaKey)}/reject`,
      { method: 'PATCH' },
    ),
}

export interface DescriptionItem {
  image_key: string
  image_type: 'catalog' | 'instagram'
  filename?: string
  date_ref?: string
  summary?: string
  best_perspective?: string
  desc_model?: string
  described_at?: string
  has_description: number
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
    request<{ description: ImageDescription | null }>(
      `/descriptions/${encodeURIComponent(imageKey)}`
    ),
  list: (params?: { image_type?: string; described_only?: boolean; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.image_type) sp.set('image_type', params.image_type)
    if (params?.described_only) sp.set('described_only', 'true')
    if (params?.limit) sp.set('limit', String(params.limit))
    if (params?.offset) sp.set('offset', String(params.offset))
    return request<{ total: number; items: DescriptionItem[]; pagination: PaginationMeta }>(
      `/descriptions/?${sp.toString()}`
    )
  },
  generate: (
    imageKey: string,
    imageType: string,
    force = false,
    model?: string,
    providerId?: string,
    providerModel?: string,
  ) =>
    request<{ generated: boolean; description: ImageDescription | null }>(
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
    ),
}

export type DescriptionListResult = Awaited<ReturnType<typeof DescriptionsAPI.list>>

export const DumpMediaAPI = {
  list: (filters?: { processed?: boolean; matched?: boolean; limit?: number; offset?: number }) => {
    const params = new URLSearchParams()
    if (filters?.processed !== undefined) params.set('processed', String(filters.processed))
    if (filters?.matched !== undefined) params.set('matched', String(filters.matched))
    if (filters?.limit) params.set('limit', String(filters.limit))
    if (filters?.offset) params.set('offset', String(filters.offset))
    return request<{ total: number; media: DumpMedia[] }>(`/images/dump-media?${params.toString()}`)
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

export interface InstagramImage {
  post_url?: string // Optional - not available in dump
  local_path: string
  filename: string
  instagram_folder: string
  source_folder: string // posts, archived_posts, etc.
  image_hash?: string // Visual perceptual hash for duplicate detection
  phash?: string
  description?: string
  key: string
  crawled_at: string
  image_index: number
  total_in_post: number
  processed?: boolean
  matched_catalog_key?: string
  matched_model?: string
  exif_data?: {
    latitude?: number
    longitude?: number
    date_time_original?: string
    device_id?: string
    lens_model?: string
    iso?: number
    aperture?: string
    shutter_speed?: string
  }
}

export interface CatalogImage {
  id: number
  filename: string
  filepath: string
  date_taken: string
  rating: number
  pick: boolean
  color_label: string
  keywords: string[]
  title: string
  caption: string
  copyright: string
  width: number
  height: number
  instagram_posted: boolean
  instagram_url?: string
  image_hash?: string
}

export interface PerspectiveScore {
  analysis: string
  score: number
}

export interface ImageDescription {
  image_key: string
  image_type: string
  summary: string
  composition: {
    layers?: string[]
    techniques?: string[]
    problems?: string[]
    depth?: string
    balance?: string
  }
  perspectives: {
    street?: PerspectiveScore
    documentary?: PerspectiveScore
    publisher?: PerspectiveScore
  }
  technical: {
    dominant_colors?: string[]
    mood?: string
    lighting?: string
    time_of_day?: string
  }
  subjects: string[]
  best_perspective: string
  model_used: string
  described_at?: string
}

export interface Match {
  instagram_key: string
  catalog_key: string
  score: number
  vision_result?: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
  /** Model explanation when available (from JSON vision response). */
  vision_reasoning?: string
  vision_score?: number
  phash_score?: number
  desc_similarity?: number
  total_score?: number
  model_used?: string
  validated_at?: string
  rank?: number
  instagram_image?: InstagramImage
  catalog_image?: CatalogImage
  catalog_description?: ImageDescription
  insta_description?: ImageDescription
}

export interface MatchGroup {
  instagram_key: string
  instagram_image?: InstagramImage
  candidates: Match[]
  best_score: number
  candidate_count: number
  has_validated: boolean
}

export interface DumpMedia {
  media_key: string
  file_path: string
  filename?: string
  caption?: string
  created_at?: string
  processed: boolean
  matched_catalog_key?: string
  vision_result?: 'SAME' | 'DIFFERENT' | 'UNCERTAIN' | 'NO_MATCH' | 'ERROR'
  vision_score?: number
}

export interface Provider {
  id: string
  name: string
  available: boolean
}

export interface ProviderModel {
  id: string
  name: string
  vision: boolean
  source: 'config' | 'discovered' | 'user'
}

export interface ProviderDefaults {
  vision_comparison: { provider: string; model: string | null }
  description: { provider: string; model: string | null }
}

export const ProvidersAPI = {
  list: () => request<Provider[]>('/providers/'),
  listModels: (providerId: string) =>
    request<ProviderModel[]>(`/providers/${providerId}/models`),
  getFallbackOrder: () =>
    request<{ order: string[] }>('/providers/fallback-order'),
  getDefaults: () =>
    request<ProviderDefaults>('/providers/defaults'),
  updateFallbackOrder: (order: string[]) =>
    request<{ order: string[] }>('/providers/fallback-order', {
      method: 'PUT',
      body: JSON.stringify({ order }),
    }),
  updateDefaults: (defaults: Partial<ProviderDefaults>) =>
    request<ProviderDefaults>('/providers/defaults', {
      method: 'PUT',
      body: JSON.stringify(defaults),
    }),
  addModel: (
    providerId: string,
    model: { id: string; name: string; vision: boolean },
  ) =>
    request<ProviderModel>(`/providers/${providerId}/models`, {
      method: 'POST',
      body: JSON.stringify(model),
    }),
  removeModel: (providerId: string, modelId: string) =>
    request<{ deleted: boolean }>(
      `/providers/${providerId}/models/${encodeURIComponent(modelId)}`,
      { method: 'DELETE' },
    ),
}
