import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type AnalyticsGranularity = 'day' | 'week' | 'month'
export type PostingFrequencyBucket =
  components['schemas']['PostingFrequencyResponse.21fa20e.PostingFrequencyBucket']
export type PostingFrequencyMeta =
  components['schemas']['PostingFrequencyResponse.21fa20e.PostingFrequencyMeta']
export type PostingFrequencyResponse =
  components['schemas']['PostingFrequencyResponse.21fa20e']
export type HeatmapCell =
  components['schemas']['PostingHeatmapResponse.21fa20e.HeatmapCell']
export type PostingHeatmapMeta =
  components['schemas']['PostingHeatmapResponse.21fa20e.PostingHeatmapMeta']
export type PostingHeatmapResponse =
  components['schemas']['PostingHeatmapResponse.21fa20e']
export type CaptionHashtagMeta =
  components['schemas']['CaptionStatsResponse.21fa20e.CaptionHashtagMeta']
export type TopHashtagRow =
  components['schemas']['CaptionStatsResponse.21fa20e.TopHashtagRow']
export type TopWordRow =
  components['schemas']['CaptionStatsResponse.21fa20e.TopWordRow']
export type CaptionStatsResponse =
  components['schemas']['CaptionStatsResponse.21fa20e']
export type UnpostedCatalogItem =
  components['schemas']['UnpostedCatalogResponse.21fa20e.UnpostedCatalogItem']
export type UnpostedCatalogResponse =
  components['schemas']['UnpostedCatalogResponse.21fa20e']
