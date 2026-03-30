import { describe, it, expect } from 'vitest'
import { thumbnailUrl, fullImageUrl } from '../imageUrl'

describe('thumbnailUrl', () => {
  it('builds catalog thumbnail URL', () => {
    expect(thumbnailUrl('catalog', 'IMG_001.dng'))
      .toBe('/api/images/catalog/IMG_001.dng/thumbnail')
  })

  it('builds instagram thumbnail URL', () => {
    expect(thumbnailUrl('instagram', 'abc123'))
      .toBe('/api/images/instagram/abc123/thumbnail')
  })

  it('encodes special characters in the key', () => {
    expect(thumbnailUrl('catalog', 'path/to/img 001.dng'))
      .toBe('/api/images/catalog/path%2Fto%2Fimg%20001.dng/thumbnail')
  })
})

describe('fullImageUrl', () => {
  it('builds catalog full URL', () => {
    expect(fullImageUrl('catalog', 'IMG_001.dng'))
      .toBe('/api/images/catalog/IMG_001.dng/full')
  })

  it('builds instagram full URL', () => {
    expect(fullImageUrl('instagram', 'abc123'))
      .toBe('/api/images/instagram/abc123/full')
  })

  it('encodes special characters in the key', () => {
    expect(fullImageUrl('instagram', 'a/b c'))
      .toBe('/api/images/instagram/a%2Fb%20c/full')
  })
})
