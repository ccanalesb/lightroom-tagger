import { describe, it, expect } from 'vitest'
import type {
  CatalogImage,
  IdentityBestPhotoItem,
  InstagramImage,
  PostNextCandidate,
  UnpostedCatalogItem,
} from '../../../services/api'
import {
  fromBestPhotoRow,
  fromCatalogListRow,
  fromInstagramRow,
  fromPostNextRow,
  fromUnpostedRow,
} from '../adapters'

describe('image-view adapters', () => {
  it('fromCatalogListRow does NOT zero identity fields when they are absent', () => {
    const row: CatalogImage = {
      id: 1,
      key: 'k',
      filename: 'f.jpg',
      filepath: '/tmp/f.jpg',
      date_taken: '2024-01-01',
      rating: 5,
      pick: false,
      color_label: '',
      keywords: ['a'],
      title: 't',
      caption: 'c',
      copyright: '',
      width: 100,
      height: 100,
      instagram_posted: false,
    }
    const out = fromCatalogListRow(row)
    expect(out.image_type).toBe('catalog')
    expect(out.key).toBe('k')
    // Critical: list rows don't carry identity data. Adapter must leave them
    // undefined so the modal can fill them via the detail endpoint rather
    // than rendering them as "0 / not scored".
    expect(out.identity_aggregate_score).toBeUndefined()
    expect(out.identity_per_perspective).toBeUndefined()
    expect(out.identity_perspectives_covered).toBeUndefined()
  })

  it('fromUnpostedRow maps sparse row and leaves scores undefined', () => {
    const row: UnpostedCatalogItem = {
      key: 'u1',
      filename: 'u1.jpg',
      date_taken: '2024-03-01',
      rating: 4,
    }
    const out = fromUnpostedRow(row)
    expect(out).toMatchObject({
      image_type: 'catalog',
      key: 'u1',
      filename: 'u1.jpg',
      instagram_posted: false,
    })
    expect(out.identity_aggregate_score).toBeUndefined()
    expect(out.catalog_perspective_score).toBeUndefined()
  })

  it('fromBestPhotoRow carries identity fields authoritatively', () => {
    const row: IdentityBestPhotoItem = {
      image_key: 'bk',
      aggregate_score: 8.25,
      perspectives_covered: 3,
      eligible: true,
      per_perspective: [
        {
          perspective_slug: 'street',
          display_name: 'Street',
          score: 9,
          prompt_version: 'v1',
          model_used: 'm',
          scored_at: 't',
          rationale_preview: '',
        },
      ],
      filename: 'bk.jpg',
      date_taken: '2024-02-02',
      rating: 5,
      instagram_posted: false,
    }
    const out = fromBestPhotoRow(row)
    expect(out.image_type).toBe('catalog')
    expect(out.key).toBe('bk')
    expect(out.identity_aggregate_score).toBe(8.25)
    expect(out.identity_perspectives_covered).toBe(3)
    expect(out.identity_eligible).toBe(true)
    expect(out.identity_per_perspective).toHaveLength(1)
  })

  it('fromPostNextRow maps identity fields (no eligible flag on this row)', () => {
    const row: PostNextCandidate = {
      image_key: 'pn',
      filename: 'pn.jpg',
      date_taken: '2024-04-04',
      rating: 4,
      aggregate_score: 7.1,
      perspectives_covered: 2,
      per_perspective: [],
      reasons: ['x'],
      reason_codes: ['high_score_unposted'],
    }
    const out = fromPostNextRow(row)
    expect(out.identity_aggregate_score).toBe(7.1)
    expect(out.identity_perspectives_covered).toBe(2)
    expect(out.identity_per_perspective).toEqual([])
    expect(out.identity_eligible).toBeUndefined()
  })

  it('fromInstagramRow keeps image_type=instagram and omits identity fields', () => {
    const row: InstagramImage = {
      key: 'ig-1',
      local_path: '/tmp/ig.jpg',
      filename: 'ig.jpg',
      instagram_folder: '2024-05',
      source_folder: 'posts',
      date_folder: '202405',
      crawled_at: '',
      image_index: 1,
      total_in_post: 1,
      caption: 'hi',
      description: 'ai-desc',
    }
    const out = fromInstagramRow(row)
    expect(out.image_type).toBe('instagram')
    expect(out.description_summary).toBe('ai-desc')
    expect(out.ai_analyzed).toBe(true)
    expect(out.identity_aggregate_score).toBeUndefined()
    expect(out.catalog_perspective_score).toBeUndefined()
  })

  it('fromInstagramRow sets ai_analyzed true when description is non-empty after trim', () => {
    const base: Omit<InstagramImage, 'description'> = {
      key: 'ig-2',
      local_path: '/tmp/x.jpg',
      filename: 'x.jpg',
      instagram_folder: '2024-05',
      source_folder: 'posts',
      date_folder: '202405',
      crawled_at: '',
      image_index: 1,
      total_in_post: 1,
      caption: '',
    }
    const out = fromInstagramRow({ ...base, description: '  hello  ' })
    expect(out.ai_analyzed).toBe(true)
    expect(out.description_summary).toBe('  hello  ')
  })

  it('fromInstagramRow sets ai_analyzed false when description is missing or blank', () => {
    const base: Omit<InstagramImage, 'description'> = {
      key: 'ig-3',
      local_path: '/tmp/y.jpg',
      filename: 'y.jpg',
      instagram_folder: '2024-05',
      source_folder: 'posts',
      date_folder: '202405',
      crawled_at: '',
      image_index: 1,
      total_in_post: 1,
      caption: '',
    }
    expect(fromInstagramRow({ ...base }).ai_analyzed).toBe(false)
    expect(fromInstagramRow({ ...base, description: '' }).ai_analyzed).toBe(false)
    expect(fromInstagramRow({ ...base, description: '   ' }).ai_analyzed).toBe(false)
  })
})
