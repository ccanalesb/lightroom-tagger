import type { ReactNode } from 'react'

/**
 * Shared tile-grid density used across every image-list surface
 * (Instagram, Catalog, Matches, Unposted, Best Photos). Keeps page
 * density visually consistent and DRY — if we want to tune columns
 * later we change one constant.
 */
export const TILE_GRID_CLASS =
  'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'

interface TileGridProps {
  children: ReactNode
  className?: string
}

export function TileGrid({ children, className }: TileGridProps) {
  return (
    <div className={className ? `${TILE_GRID_CLASS} ${className}` : TILE_GRID_CLASS}>
      {children}
    </div>
  )
}
