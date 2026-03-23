import { Job } from '../types/job'
import { API_DEFAULT_URL } from '../constants/strings'

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
      pagination: {
        offset: number;
        limit: number;
        current_page: number;
        total_pages: number;
        has_more: boolean;
      }
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
    request<{ total: number; matches: Match[] }>(
      `/images/matches?limit=${limit || 50}&offset=${offset || 0}`
    ),
}

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

export interface InstagramImage {
  post_url?: string  // Optional - not available in dump
  local_path: string
  filename: string
  instagram_folder: string
  source_folder: string  // posts, archived_posts, etc.
  image_hash?: string  // Visual perceptual hash for duplicate detection
  phash?: string
  description?: string
  key: string
  crawled_at: string
  image_index: number
  total_in_post: number
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

export interface Match {
  instagram_key: string
  catalog_key: string
  score: number
  vision_result?: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
  vision_score?: number
  phash_score?: number
  desc_similarity?: number
  total_score?: number
  instagram_image?: InstagramImage
  catalog_image?: CatalogImage
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