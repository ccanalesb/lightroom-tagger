import type { components } from './api.gen'
import type { CatalogImage, ImageDescription, InstagramImage } from '../services/api'

type GenMatch = components['schemas']['MatchesListResponse.595c1c1.Match']
type GenMatchGroup = components['schemas']['MatchesListResponse.595c1c1.MatchGroup']

/** Wire fields may be null; UI code treats absent keys the same as null. */
type OptionalizeNulls<T> = {
  [K in keyof T as null extends T[K] ? K : never]?: T[K] | undefined
} & {
  [K in keyof T as null extends T[K] ? never : K]: T[K]
}

type GenMatchCore = Omit<
  GenMatch,
  'instagram_image' | 'catalog_image' | 'catalog_description' | 'insta_description'
>

/** Generated from backend OpenAPI — see ADR-0013. */
export type Match = OptionalizeNulls<GenMatchCore> & {
  instagram_image?: InstagramImage | null
  catalog_image?: CatalogImage | null
  catalog_description?: ImageDescription | null
  insta_description?: ImageDescription | null
}

type GenMatchGroupCore = Omit<GenMatchGroup, 'instagram_image' | 'candidates' | 'all_rejected'>

export type MatchGroup = OptionalizeNulls<GenMatchGroupCore> & {
  candidates: Match[]
  instagram_image?: InstagramImage | null
  all_rejected?: boolean
}

type GenMatchesListResponse = components['schemas']['MatchesListResponse.595c1c1']

/** Client-facing list payload — nested images use concrete UI row types. */
export type MatchesListResponse = Omit<GenMatchesListResponse, 'match_groups' | 'matches'> & {
  match_groups: MatchGroup[]
  matches: Match[]
}
export type MatchValidateResponse = components['schemas']['MatchValidateResponse.595c1c1']
export type MatchRejectSuccessResponse = components['schemas']['MatchRejectSuccessResponse.595c1c1']
