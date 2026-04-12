import { useState } from 'react'
import type { CatalogImage, IdentityBestPhotoItem } from '../../services/api'
import { CatalogImageModal } from '../catalog/CatalogImageModal'
import { IDENTITY_LABEL_AGGREGATE, IDENTITY_LABEL_PERSPECTIVES_COVERED, MSG_LOADING } from '../../constants/strings'

export type TopPhotosStripProps = {
  items: IdentityBestPhotoItem[]
  loading: boolean
  error: string | null
  emptyMessage: string | null
}

function bestPhotoToCatalogStub(row: IdentityBestPhotoItem): CatalogImage {
  return {
    id: null,
    key: row.image_key,
    filename: row.filename,
    filepath: '',
    date_taken: row.date_taken,
    rating: typeof row.rating === 'number' ? row.rating : 0,
    pick: false,
    color_label: '',
    keywords: [],
    title: '',
    caption: '',
    copyright: '',
    width: 0,
    height: 0,
    instagram_posted: Boolean(row.instagram_posted),
  }
}

export function TopPhotosStrip({ items, loading, error, emptyMessage }: TopPhotosStripProps) {
  const [selected, setSelected] = useState<CatalogImage | null>(null)

  if (loading) {
    return (
      <p className="text-sm text-text-secondary" role="status" aria-live="polite">
        {MSG_LOADING}
      </p>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-error" role="alert">
        {error}
      </p>
    )
  }

  if (emptyMessage) {
    return (
      <p className="text-sm text-text-secondary" role="status">
        {emptyMessage}
      </p>
    )
  }

  if (items.length === 0) {
    return null
  }

  return (
    <>
      <div className="-mx-1 flex gap-3 overflow-x-auto pb-2 pt-1">
        {items.map((row) => {
          const dateDisplay = row.date_taken ? new Date(row.date_taken).toLocaleDateString() : '—'
          return (
            <div
              key={row.image_key}
              className="w-[200px] shrink-0 overflow-hidden rounded-card border border-border bg-bg shadow-card"
            >
              <button
                type="button"
                onClick={() => setSelected(bestPhotoToCatalogStub(row))}
                className="block w-full text-left focus:outline-none focus:ring-2 focus:ring-accent focus:ring-inset"
              >
                <div className="relative aspect-[4/3] bg-surface">
                  <img
                    src={`/api/images/catalog/${encodeURIComponent(row.image_key)}/thumbnail`}
                    alt={row.filename}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </div>
              </button>
              <div className="space-y-1 p-2">
                <p className="truncate text-xs font-medium text-text">{row.filename}</p>
                <p className="text-[10px] text-text-tertiary">{dateDisplay}</p>
                <div className="flex flex-wrap gap-1">
                  <span className="rounded-base bg-accent-light px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                    {IDENTITY_LABEL_AGGREGATE}: {row.aggregate_score.toFixed(2)}
                  </span>
                  <span className="rounded-full border border-border px-1.5 py-0.5 text-[10px] text-text-secondary">
                    {IDENTITY_LABEL_PERSPECTIVES_COVERED}: {row.perspectives_covered}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      {selected ? <CatalogImageModal image={selected} onClose={() => setSelected(null)} /> : null}
    </>
  )
}
