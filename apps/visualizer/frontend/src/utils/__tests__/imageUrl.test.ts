import { describe, it, expect } from 'vitest'
import { thumbnailUrl, fullImageUrl } from '../imageUrl'

describe('thumbnailUrl', () => {
  it('should build catalog thumbnail URL', () => {
    expect(thumbnailUrl('catalog', 'IMG_001.dng'))
      .toBe('/api/images/catalog/IMG_001.dng/thumbnail')
  })

  it('should build instagram thumbnail URL', () => {
    expect(thumbnailUrl('instagram', 'abc123'))
      .toBe('/api/images/instagram/abc123/thumbnail')
  })

  it('should encode special characters in the key', () => {
    expect(thumbnailUrl('catalog', 'path/to/img 001.dng'))
      .toBe('/api/images/catalog/path%2Fto%2Fimg%20001.dng/thumbnail')
  })
})

describe('fullImageUrl', () => {
  it('should build catalog full URL', () => {
    expect(fullImageUrl('catalog', 'IMG_001.dng'))
      .toBe('/api/images/catalog/IMG_001.dng/full')
  })

  it('should build instagram full URL', () => {
    expect(fullImageUrl('instagram', 'abc123'))
      .toBe('/api/images/instagram/abc123/full')
  })

  it('should encode special characters in the key', () => {
    expect(fullImageUrl('instagram', 'a/b c'))
      .toBe('/api/images/instagram/a%2Fb%20c/full')
  })
})
