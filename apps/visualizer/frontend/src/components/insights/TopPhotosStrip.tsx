import { useState } from 'react'
import type { IdentityBestPhotoItem } from '../../services/api'
import { ImageDetailModal, ImageTile, fromBestPhotoRow } from '../image-view'
import { MSG_LOADING } from '../../constants/strings'

export type TopPhotosStripProps = {
  items: IdentityBestPhotoItem[]
  loading: boolean
  error: string | null
  emptyMessage: string | null
}

export function TopPhotosStrip({ items, loading, error, emptyMessage }: TopPhotosStripProps) {
  const [selected, setSelected] = useState<IdentityBestPhotoItem | null>(null)

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
        {items.map((row) => (
          <ImageTile
            key={row.image_key}
            image={fromBestPhotoRow(row)}
            variant="strip"
            primaryScoreSource="identity"
            onClick={() => setSelected(row)}
          />
        ))}
      </div>
      {selected ? (
        <ImageDetailModal
          imageType={(selected.image_type as 'catalog' | 'instagram') ?? 'catalog'}
          imageKey={selected.image_key}
          initialImage={fromBestPhotoRow(selected)}
          primaryScoreSource="identity"
          onClose={() => setSelected(null)}
        />
      ) : null}
    </>
  )
}
