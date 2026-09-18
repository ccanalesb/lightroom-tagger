import { describe, it, expect } from 'vitest'
import { normalizeCatalogPath } from '../useCatalogPicker'

describe('normalizeCatalogPath', () => {
  it('leaves a plain path alone', () => {
    expect(normalizeCatalogPath('/Users/me/lightroom/Foo.lrcat')).toBe(
      '/Users/me/lightroom/Foo.lrcat',
    )
  })

  it("strips the single quotes Finder adds around paths with spaces", () => {
    expect(normalizeCatalogPath("'/Users/me/Pictures/Lightroom Catalog.lrcat'")).toBe(
      '/Users/me/Pictures/Lightroom Catalog.lrcat',
    )
  })

  it('strips double quotes too', () => {
    expect(normalizeCatalogPath('"/Users/me/Foo.lrcat"')).toBe('/Users/me/Foo.lrcat')
  })

  it('trims surrounding whitespace and trailing newlines', () => {
    expect(normalizeCatalogPath('  /Users/me/Foo.lrcat\n')).toBe('/Users/me/Foo.lrcat')
  })

  it('leaves an unbalanced quote in place', () => {
    expect(normalizeCatalogPath("'/Users/me/Foo.lrcat")).toBe("'/Users/me/Foo.lrcat")
  })

  it('does not strip quotes that are only internal', () => {
    expect(normalizeCatalogPath("/Users/me/it's/Foo.lrcat")).toBe("/Users/me/it's/Foo.lrcat")
  })

  it('survives a lone quote character', () => {
    expect(normalizeCatalogPath("'")).toBe("'")
  })

  it('returns empty for blank input', () => {
    expect(normalizeCatalogPath('   ')).toBe('')
  })
})
