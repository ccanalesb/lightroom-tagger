/**
 * Tiny source marker for catalog vs Instagram images (e.g. “CAT” / “IG”) on
 * tiles and lists. Stays compact (`text-[10px]`) while using the shared `Badge`
 * shell.
 */
import { Badge } from './Badge'

const IMAGE_TYPE_LABELS = {
  catalog: 'CAT',
  instagram: 'IG',
} as const

const CATALOG_CLASS =
  '!text-[10px] !font-medium !px-1.5 !py-0.5 !bg-blue-100 !text-blue-700 dark:!bg-blue-900/30 dark:!text-blue-100 !border-blue-200 dark:!border-blue-800'

const INSTAGRAM_CLASS =
  '!text-[10px] !font-medium !px-1.5 !py-0.5 !bg-pink-100 !text-pink-700 dark:!bg-pink-900/30 dark:!text-pink-100 !border-pink-200 dark:!border-pink-800'

export function ImageTypeBadge({ type }: { type: 'catalog' | 'instagram' }) {
  const className = type === 'catalog' ? CATALOG_CLASS : INSTAGRAM_CLASS
  return (
    <Badge variant="default" className={className}>
      {IMAGE_TYPE_LABELS[type]}
    </Badge>
  )
}
