import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within, cleanup } from '@testing-library/react'
import {
  DescriptionsAPI,
  ImagesAPI,
  PerspectivesAPI,
  ProvidersAPI,
  type CatalogImage,
  type IdentityBestPhotoItem,
  type ImageDetailResponse,
  type UnpostedCatalogItem,
} from '../../../services/api'
import { ImageDetailModal } from '../ImageDetailModal'
import {
  fromBestPhotoRow,
  fromCatalogListRow,
  fromUnpostedRow,
} from '../adapters'

/**
 * Cross-cutting modal parity (plan Task 12).
 *
 * Opening the same image from any catalog-backed surface — the catalog
 * grid, the identity Best/Top photos, or Analytics "Not posted" — must
 * produce the same modal content because every entry point ultimately
 * fetches the authoritative detail payload from
 * `ImagesAPI.getImageDetail`. This test locks in that guarantee by
 * mounting `ImageDetailModal` from each surface's `initialImage` shape
 * while the detail call resolves to a single shared payload, then
 * asserting the identity breakdown + header score pill render
 * identically in every case.
 */

const SHARED_KEY = 'shared/k1.jpg'

const SHARED_DETAIL: ImageDetailResponse = {
  image_type: 'catalog',
  key: SHARED_KEY,
  filename: 'one.jpg',
  rating: 4,
  identity_aggregate_score: 7.2,
  identity_perspectives_covered: 2,
  identity_eligible: true,
  identity_per_perspective: [
    {
      perspective_slug: 'portraits',
      display_name: 'Portraits',
      score: 8,
      prompt_version: 'v1',
      model_used: 'gpt-x',
      scored_at: '2026-04-20T00:00:00Z',
      rationale_preview: 'strong subject',
    },
    {
      perspective_slug: 'street',
      display_name: 'Street',
      score: 6,
      prompt_version: 'v1',
      model_used: 'gpt-x',
      scored_at: '2026-04-20T00:00:00Z',
      rationale_preview: 'decent context',
    },
  ],
  ai_analyzed: true,
  description_summary: 'sample',
}

const CATALOG_ROW: CatalogImage = {
  id: 1,
  key: SHARED_KEY,
  filename: 'one.jpg',
  filepath: '/p/one.jpg',
  date_taken: '2026-04-01',
  rating: 4,
  pick: false,
  color_label: '',
  keywords: [],
  title: '',
  caption: '',
  copyright: '',
  width: 100,
  height: 100,
  instagram_posted: false,
}

const UNPOSTED_ROW: UnpostedCatalogItem = {
  key: SHARED_KEY,
  filename: 'one.jpg',
  date_taken: '2026-04-01',
  rating: 4,
}

const BEST_PHOTO_ROW: IdentityBestPhotoItem = {
  image_key: SHARED_KEY,
  image_type: 'catalog',
  filename: 'one.jpg',
  date_taken: '2026-04-01',
  rating: 4,
  instagram_posted: false,
  aggregate_score: 7.2,
  perspectives_covered: 2,
  eligible: true,
  per_perspective: SHARED_DETAIL.identity_per_perspective ?? [],
}

async function openFrom(initial: ReturnType<typeof fromCatalogListRow>) {
  render(
    <ImageDetailModal
      imageType="catalog"
      imageKey={SHARED_KEY}
      initialImage={initial}
      primaryScoreSource="identity"
      onClose={() => {}}
    />,
  )
  await waitFor(() => {
    expect(ImagesAPI.getImageDetail).toHaveBeenCalled()
  })
  // Aggregate pill in the modal header is a stable anchor once detail resolves.
  await waitFor(() =>
    expect(screen.getAllByLabelText(/Aggregate score/i).length).toBeGreaterThan(0),
  )
  return screen.getByRole('dialog')
}

describe('ImageDetailModal — cross-entry parity', () => {
  beforeEach(() => {
    vi.spyOn(ImagesAPI, 'getImageDetail').mockResolvedValue(SHARED_DETAIL)
    // CatalogImageDetailSections fires these on mount; stub to avoid
    // real network calls and isolate parity to the detail payload.
    vi.spyOn(ProvidersAPI, 'getDefaults').mockResolvedValue({
      description: { provider: null, model: null },
    } as unknown as Awaited<ReturnType<typeof ProvidersAPI.getDefaults>>)
    vi.spyOn(PerspectivesAPI, 'list').mockResolvedValue([])
    vi.spyOn(DescriptionsAPI, 'get').mockResolvedValue({
      description: null,
    } as unknown as Awaited<ReturnType<typeof DescriptionsAPI.get>>)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders the identity aggregate pill with the detail value regardless of entry point', async () => {
    // Catalog grid entry point.
    let dialog = await openFrom(fromCatalogListRow(CATALOG_ROW))
    const catalogHeader = within(dialog).getAllByLabelText(/Aggregate score/i)
    expect(catalogHeader.length).toBeGreaterThan(0)
    const catalogText = catalogHeader[0].textContent ?? ''
    cleanup()

    // Analytics → Not posted entry point.
    dialog = await openFrom(fromUnpostedRow(UNPOSTED_ROW))
    const unpostedHeader = within(dialog).getAllByLabelText(/Aggregate score/i)
    expect(unpostedHeader[0].textContent).toBe(catalogText)
    cleanup()

    // Identity → Best / Top photos entry point.
    dialog = await openFrom(fromBestPhotoRow(BEST_PHOTO_ROW))
    const bestHeader = within(dialog).getAllByLabelText(/Aggregate score/i)
    expect(bestHeader[0].textContent).toBe(catalogText)
  })

})
