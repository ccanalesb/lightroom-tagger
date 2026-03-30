export type ImageType = 'catalog' | 'instagram'

function imageUrl(type: ImageType, key: string, variant: 'thumbnail' | 'full'): string {
  return `/api/images/${type}/${encodeURIComponent(key)}/${variant}`
}

export const thumbnailUrl = (type: ImageType, key: string): string =>
  imageUrl(type, key, 'thumbnail')

export const fullImageUrl = (type: ImageType, key: string): string =>
  imageUrl(type, key, 'full')
