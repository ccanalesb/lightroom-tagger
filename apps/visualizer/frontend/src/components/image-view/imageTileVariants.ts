export type ImageTileVariant = 'grid' | 'strip' | 'list' | 'compact'

export interface ImageTileVariantClasses {
  root: string
  button: string
  thumb: string
  body: string
  title: string
  subtitle: string
  meta: string
}

/**
 * Tailwind class bundle per tile variant. Kept in its own file so
 * `ImageTile.tsx` only holds the component markup.
 */
export function imageTileVariantClasses(variant: ImageTileVariant): ImageTileVariantClasses {
  switch (variant) {
    case 'grid':
      return {
        root: 'cursor-pointer',
        button: '',
        thumb: 'aspect-square',
        body: 'p-3',
        title: 'text-sm',
        subtitle: 'text-xs',
        meta: 'text-xs',
      }
    case 'strip':
      return {
        root: 'w-[200px] shrink-0',
        button: '',
        thumb: 'aspect-[4/3]',
        body: 'p-2',
        title: 'text-xs',
        subtitle: 'text-[10px]',
        meta: 'text-[10px]',
      }
    case 'list':
      return {
        root: 'cursor-pointer',
        button: '',
        thumb: 'h-28',
        body: 'p-3',
        title: 'text-sm',
        subtitle: 'text-xs',
        meta: 'text-xs',
      }
    case 'compact':
      return {
        root: 'cursor-pointer',
        button: '',
        thumb: 'aspect-[4/3]',
        body: 'p-3',
        title: 'text-sm',
        subtitle: 'text-xs',
        meta: 'text-xs',
      }
  }
}
